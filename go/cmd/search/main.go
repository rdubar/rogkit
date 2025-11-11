package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode"

	"github.com/rdubar/rogkit/go/internal/finder"
)

type multiValue []string

func (m *multiValue) String() string {
	if m == nil {
		return ""
	}
	return strings.Join(*m, ",")
}

func (m *multiValue) Set(value string) error {
	*m = append(*m, value)
	return nil
}

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: search [options] term1 [term2 ...]

Search recursively for files whose contents contain all supplied terms.

Each positional argument becomes an independent term. Wrap phrases in double quotes
so they are treated as a single term. By default matching is case-insensitive unless
any term contains an uppercase character (smart case). Use --case-sensitive or
--ignore-case to explicitly control the behaviour.

Examples:
  search TODO
  search fixme panic
  search --path ~/projects --limit 50 foo "bar baz"
  search --no-ignore password

Options:
`)
	flag.PrintDefaults()
}

type matchConfig struct {
	rawTerms        []string
	normalized      []string
	caseInsensitive bool
}

func buildMatchConfig(terms []string, ignoreCase bool) (matchConfig, error) {
	normalized := make([]string, 0, len(terms))
	for _, term := range terms {
		base := strings.TrimSpace(term)
		if base == "" {
			return matchConfig{}, errors.New("empty search term")
		}
		if ignoreCase {
			base = strings.ToLower(base)
		}
		normalized = append(normalized, base)
	}

	return matchConfig{
		rawTerms:        terms,
		normalized:      normalized,
		caseInsensitive: ignoreCase,
	}, nil
}

func (cfg matchConfig) matches(r io.Reader) (bool, error) {
	content, err := io.ReadAll(r)
	if err != nil {
		return false, err
	}

	var haystack string
	if cfg.caseInsensitive {
		haystack = strings.ToLower(string(content))
	} else {
		haystack = string(content)
	}

	for _, needle := range cfg.normalized {
		if !strings.Contains(haystack, needle) {
			return false, nil
		}
	}
	return true, nil
}

func main() {
	flag.Usage = usage

	var roots multiValue
	var pathPatterns multiValue
	var includeExts multiValue
	var excludeExts multiValue

	var (
		ignoreCase     bool
		caseSensitive  bool
		includeHidden  bool
		showTime       bool
		relativePaths  bool
		withSize       bool
		verbose        bool
		maxDepth       int
		noIgnore       bool
		includeIgnored bool
		countOnly      bool
		showAll        bool
		limit          int
		showErrors     bool
	)

	flag.Var(&roots, "path", "Root directory to search (repeatable)")
	flag.Var(&roots, "p", "Shorthand for --path")
	flag.Var(&pathPatterns, "filter", "Restrict content search to files whose paths match these patterns (glob or substring, repeatable)")
	flag.Var(&includeExts, "ext", "Only include files with this extension (repeatable, no leading dot required)")
	flag.Var(&excludeExts, "exclude-ext", "Exclude files with this extension (repeatable)")
	flag.BoolVar(&countOnly, "count", false, "Only print the total number of matches")
	flag.BoolVar(&ignoreCase, "ignore-case", false, "Force case-insensitive matching")
	flag.BoolVar(&caseSensitive, "case-sensitive", false, "Force case-sensitive matching (overrides --ignore-case)")
	flag.BoolVar(&includeHidden, "include-hidden", false, "Include hidden files and directories")
	flag.BoolVar(&includeHidden, "hidden", false, "Shorthand for --include-hidden")
	flag.BoolVar(&showTime, "time", false, "Display how long the search took")
	flag.BoolVar(&relativePaths, "relative", false, "Print paths relative to their root")
	flag.BoolVar(&withSize, "with-size", false, "Include the file size (bytes) in the output")
	flag.IntVar(&maxDepth, "max-depth", -1, "Limit search depth relative to the root (-1 for unlimited)")
	flag.BoolVar(&noIgnore, "no-ignore", false, "Include files ignored by .gitignore/.fdignore/.ignore files")
	flag.BoolVar(&includeIgnored, "include-ignored", false, "Alias for --no-ignore")
	flag.BoolVar(&verbose, "verbose", false, "Print summary information")
	flag.BoolVar(&verbose, "v", false, "Shorthand for --verbose")
	flag.BoolVar(&showAll, "all", false, "Display every match (overrides --limit)")
	flag.IntVar(&limit, "limit", 20, "Maximum number of matches to display (use --all to show every match)")
	flag.BoolVar(&showErrors, "show-errors", false, "Display files that could not be read")

	flag.Parse()

	if includeIgnored {
		noIgnore = true
	}

	if len(roots) == 0 {
		roots = append(roots, ".")
	}

	terms := flag.Args()
	if len(terms) == 0 {
		fmt.Fprintln(os.Stderr, "error: provide at least one search term\n")
		usage()
		os.Exit(1)
	}

	contentIgnoreCase := resolveIgnoreCase(terms, ignoreCase, caseSensitive)

	matchCfg, err := buildMatchConfig(terms, contentIgnoreCase)
	if err != nil {
		fmt.Fprintf(os.Stderr, "search: %v\n", err)
		os.Exit(1)
	}

	opts := finder.Options{
		Roots:         roots,
		Patterns:      pathPatterns,
		IgnoreCase:    resolveIgnoreCase(pathPatterns, ignoreCase, caseSensitive),
		IncludeHidden: includeHidden,
		IncludeExt:    includeExts,
		ExcludeExt:    excludeExts,
		MaxDepth:      maxDepth,
		RespectIgnore: !noIgnore,
	}

	var start time.Time
	if verbose && showTime {
		start = time.Now()
	}

	var (
		matches   int64
		printed   int
		errorList []string
	)

	stats, walkErr := finder.Walk(opts, func(res finder.Result) error {
		file, err := os.Open(res.Path)
		if err != nil {
			errorList = append(errorList, fmt.Sprintf("open %s: %v", res.Path, err))
			return nil
		}
		defer file.Close()

		ok, err := matchCfg.matches(file)
		if err != nil {
			errorList = append(errorList, fmt.Sprintf("read %s: %v", res.Path, err))
			return nil
		}
		if !ok {
			return nil
		}

		matches++
		if countOnly {
			return nil
		}
		if !showAll && limit >= 0 && printed >= limit {
			return nil
		}

		output := res.Path
		if relativePaths {
			if rel, err := filepath.Rel(res.Root, res.Path); err == nil {
				output = rel
			}
		}
		if withSize {
			fmt.Printf("%12d  %s\n", res.Info.Size(), output)
		} else {
			fmt.Println(output)
		}
		printed++
		return nil
	})
	if walkErr != nil {
		fmt.Fprintf(os.Stderr, "search: %v\n", walkErr)
		os.Exit(1)
	}

	if countOnly {
		fmt.Println(matches)
	}

	if verbose {
		if showTime {
			elapsed := time.Since(start)
			fmt.Fprintf(os.Stderr, "Scanned %d files across %d roots (%d matches) in %s\n",
				stats.FilesScanned, stats.RootsScanned, matches, elapsed.Round(time.Millisecond))
		} else if !countOnly {
			fmt.Fprintf(os.Stderr, "Matched %d file(s) (scanned %d)\n", matches, stats.FilesScanned)
		}
	}

	if showErrors && len(errorList) > 0 {
		fmt.Fprintln(os.Stderr, "Errors:")
		for _, msg := range errorList {
			fmt.Fprintf(os.Stderr, "  %s\n", msg)
		}
	}
}

func resolveIgnoreCase(patterns []string, ignoreCase bool, caseSensitive bool) bool {
	if caseSensitive {
		return false
	}
	if ignoreCase {
		return true
	}
	return smartCase(patterns)
}

func smartCase(patterns []string) bool {
	if len(patterns) == 0 {
		return false
	}
	for _, pattern := range patterns {
		for _, r := range pattern {
			if unicode.IsLetter(r) && unicode.IsUpper(r) {
				return false
			}
		}
	}
	return true
}

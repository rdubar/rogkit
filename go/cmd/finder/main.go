package main

import (
	"flag"
	"fmt"
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
	fmt.Fprintf(os.Stderr, `Usage: finder [options]

Traverse directories and list files that match patterns.

By default finder respects .gitignore, .fdignore, and .ignore files. Use --include-ignored to
search files that would normally be skipped.

Examples:
  finder --search '*.go'
  finder --path ~/projects --search config --ignore-case

Options:
`)
	flag.PrintDefaults()
}

func main() {
	flag.Usage = usage

	var roots multiValue
	var searches multiValue
	var includeExts multiValue
	var excludeExts multiValue

	var (
		countOnly      bool
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
	)

	flag.Var(&roots, "path", "Root directory to search (repeatable)")
	flag.Var(&roots, "p", "Shorthand for --path")
	flag.Var(&searches, "search", "Pattern to match (glob or substring, repeatable)")
	flag.Var(&searches, "s", "Shorthand for --search")
	flag.Var(&includeExts, "ext", "Only include files with this extension (repeatable, no leading dot required)")
	flag.Var(&excludeExts, "exclude-ext", "Exclude files with this extension (repeatable)")
	flag.BoolVar(&countOnly, "count", false, "Only print the total number of matches")
	flag.BoolVar(&countOnly, "c", false, "Shorthand for --count")
	flag.BoolVar(&ignoreCase, "ignore-case", false, "Perform case-insensitive matching")
	flag.BoolVar(&ignoreCase, "i", false, "Shorthand for --ignore-case")
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

	flag.Parse()

	if includeIgnored {
		noIgnore = true
	}

	args := flag.Args()
	if len(searches) == 0 && len(args) > 0 {
		searches = append(searches, args[0])
		args = args[1:]
	}

	// Treat remaining positional arguments as roots.
	for _, arg := range args {
		if arg == "" {
			continue
		}
		roots = append(roots, arg)
	}

	if len(roots) == 0 {
		roots = append(roots, ".")
	}

	opts := finder.Options{
		Roots:         roots,
		Patterns:      searches,
		IgnoreCase:    resolveIgnoreCase(searches, ignoreCase, caseSensitive),
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

	stats, err := finder.Walk(opts, func(res finder.Result) error {
		if countOnly {
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
		return nil
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "finder: %v\n", err)
		os.Exit(1)
	}

	if countOnly {
		fmt.Println(stats.FilesMatched)
	}

	if verbose && showTime {
		elapsed := time.Since(start)
		fmt.Fprintf(os.Stderr, "Scanned %d files across %d roots (%d matches) in %s\n",
			stats.FilesScanned, stats.RootsScanned, stats.FilesMatched, elapsed.Round(time.Millisecond))
	} else if verbose && !countOnly {
		fmt.Fprintf(os.Stderr, "Matched %d file(s) (scanned %d)\n", stats.FilesMatched, stats.FilesScanned)
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

package main

import (
	"bufio"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode"

	"github.com/rdubar/rogkit/go/internal/finder"
	"github.com/rdubar/rogkit/go/internal/util"
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
	fmt.Fprintf(os.Stderr, `Usage: replacer --find TEXT [options]

Search recursively for TEXT starting at --path (default "."). Runs in dry-run mode
by default; pass --write to apply replacements. Combine with --confirm to approve
each change interactively.

Options:
`)
	flag.PrintDefaults()
}

type matchEngine struct {
	needle          string
	replacement     string
	caseInsensitive bool
	write           bool
}

func newMatchEngine(find, replace string, caseInsensitive, write bool) (matchEngine, error) {
	needle := strings.TrimSpace(find)
	if needle == "" {
		return matchEngine{}, errors.New("empty --find value")
	}
	if !write && replace == "" {
		// pure search
		return matchEngine{
			needle:          find,
			replacement:     replace,
			caseInsensitive: caseInsensitive,
			write:           false,
		}, nil
	}
	return matchEngine{
		needle:          find,
		replacement:     replace,
		caseInsensitive: caseInsensitive,
		write:           write,
	}, nil
}

func (m matchEngine) process(data []byte) (bool, []byte, int) {
	if len(m.needle) == 0 {
		return false, nil, 0
	}

	original := string(data)
	searchSpace := original
	needle := m.needle

	if m.caseInsensitive {
		searchSpace = strings.ToLower(original)
		needle = strings.ToLower(needle)
	}

	if !strings.Contains(searchSpace, needle) {
		return false, nil, 0
	}

	if !m.write {
		return true, nil, countOccurrences(searchSpace, needle)
	}

	if m.caseInsensitive {
		replaced, replacements := replaceAllCaseInsensitive(original, m.needle, m.replacement)
		return true, []byte(replaced), replacements
	}

	replacements := strings.Count(original, m.needle)
	replaced := strings.ReplaceAll(original, m.needle, m.replacement)
	return true, []byte(replaced), replacements
}

type summary struct {
	textFilesChecked    int
	matchingFiles       int
	occurrencesFound    int
	filesChanged        int
	occurrencesReplaced int
	confirmDeclined     int
	errors              []errorEntry
	duration            time.Duration
	matchedPaths        []string
	changedPaths        []string
}

type errorEntry struct {
	path string
	err  error
}

func main() {
	flag.Usage = usage

	var roots multiValue
	var filters multiValue
	var includeExts multiValue
	var excludeExts multiValue

	var (
		findArg        string
		replaceArg     string
		writeChanges   bool
		confirmEach    bool
		listMatches    bool
		ignoreCase     bool
		caseSensitive  bool
		includeHidden  bool
		relativePaths  bool
		showTime       bool
		verbose        bool
		maxDepth       int
		noIgnore       bool
		includeIgnored bool
	)

	flag.Var(&roots, "path", "Root directory to search (repeatable)")
	flag.Var(&roots, "p", "Shorthand for --path")
	flag.Var(&filters, "filter", "Restrict processing to files whose paths match these patterns (glob or substring, repeatable)")
	flag.Var(&includeExts, "ext", "Only include files with this extension (repeatable, no leading dot required)")
	flag.Var(&excludeExts, "exclude-ext", "Exclude files with this extension (repeatable)")
	flag.StringVar(&findArg, "find", "", "Text to find (required)")
	flag.StringVar(&replaceArg, "replace", "", "Replacement text (dry-run unless --write)")
	flag.BoolVar(&writeChanges, "write", false, "Write changes to disk (default: dry-run)")
	flag.BoolVar(&confirmEach, "confirm", false, "Confirm each replacement interactively (implies --write)")
	flag.BoolVar(&listMatches, "list", false, "List matching (and changed) file paths")
	flag.BoolVar(&ignoreCase, "ignore-case", false, "Force case-insensitive content matching")
	flag.BoolVar(&caseSensitive, "case-sensitive", false, "Force case-sensitive matching (overrides --ignore-case)")
	flag.BoolVar(&includeHidden, "include-hidden", false, "Include hidden files and directories")
	flag.BoolVar(&includeHidden, "hidden", false, "Shorthand for --include-hidden")
	flag.BoolVar(&relativePaths, "relative", false, "Print paths relative to their search root")
	flag.BoolVar(&showTime, "time", false, "Display how long the search took (with --verbose)")
	flag.BoolVar(&verbose, "verbose", false, "Print summary information to stderr")
	flag.BoolVar(&verbose, "v", false, "Shorthand for --verbose")
	flag.IntVar(&maxDepth, "max-depth", -1, "Limit search depth relative to the root (-1 for unlimited)")
	flag.BoolVar(&noIgnore, "no-ignore", false, "Include files ignored by .gitignore/.fdignore/.ignore files")
	flag.BoolVar(&includeIgnored, "include-ignored", false, "Alias for --no-ignore")

	flag.Parse()

	if len(os.Args) == 1 {
		usage()
		os.Exit(1)
	}

	if includeIgnored {
		noIgnore = true
	}

	if confirmEach {
		writeChanges = true
	}

	if !writeChanges && replaceArg != "" {
		fmt.Fprintln(os.Stderr, "info: running in dry-run mode; no files will be modified (use --write to apply changes)")
	}

	if writeChanges && replaceArg == "" {
		fmt.Fprintln(os.Stderr, "error: --write requires --replace text")
		usage()
		os.Exit(1)
	}

	if confirmEach && replaceArg == "" {
		fmt.Fprintln(os.Stderr, "error: --confirm requires --replace text")
		usage()
		os.Exit(1)
	}

	if len(roots) == 0 {
		roots = append(roots, ".")
	}

	contentIgnoreCase := resolveIgnoreCase([]string{findArg}, ignoreCase, caseSensitive)

	engine, err := newMatchEngine(findArg, replaceArg, contentIgnoreCase, writeChanges)
	if err != nil {
		fmt.Fprintf(os.Stderr, "replacer: %v\n", err)
		os.Exit(1)
	}

	opts := finder.Options{
		Roots:         roots,
		Patterns:      filters,
		IgnoreCase:    resolveIgnoreCase(filters, ignoreCase, caseSensitive),
		IncludeHidden: includeHidden,
		IncludeExt:    includeExts,
		ExcludeExt:    excludeExts,
		MaxDepth:      maxDepth,
		RespectIgnore: !noIgnore,
	}

	start := time.Now()

	var (
		sum          summary
		promptReader *bufio.Scanner
	)

	if confirmEach {
		promptReader = bufio.NewScanner(os.Stdin)
	}

	stats, walkErr := finder.Walk(opts, func(res finder.Result) error {
		if !util.IsTextFile(res.Path) {
			return nil
		}
		sum.textFilesChecked++

		data, err := os.ReadFile(res.Path)
		if err != nil {
			sum.errors = append(sum.errors, errorEntry{path: res.Path, err: err})
			return nil
		}

		match, replaced, occurrences := engine.process(data)
		if !match {
			return nil
		}

		displayPath := res.Path
		if relativePaths {
			if rel, err := filepath.Rel(res.Root, res.Path); err == nil {
				displayPath = rel
			}
		}

		sum.matchingFiles++
		sum.occurrencesFound += occurrences
		if listMatches {
			sum.matchedPaths = append(sum.matchedPaths, displayPath)
		}

		if !engine.write {
			return nil
		}

		if occurrences == 0 || replaced == nil {
			return nil
		}

		if confirmEach {
			fmt.Printf("Replace %d occurrence(s) in %s? [y/N]: ", occurrences, displayPath)
			if !promptYes(promptReader) {
				sum.confirmDeclined++
				return nil
			}
		}

		if err := writeFilePreserveMode(res.Path, replaced); err != nil {
			sum.errors = append(sum.errors, errorEntry{path: res.Path, err: err})
			return nil
		}

		sum.filesChanged++
		sum.occurrencesReplaced += occurrences
		if listMatches {
			sum.changedPaths = append(sum.changedPaths, displayPath)
		}
		if confirmEach {
			fmt.Printf("Replaced %d occurrence(s) in %s\n", occurrences, displayPath)
		}
		return nil
	})

	elapsed := time.Since(start)

	if walkErr != nil {
		sum.errors = append(sum.errors, errorEntry{path: strings.Join(roots, ","), err: walkErr})
	}

	printSummary(sum, stats, engine.write, confirmEach, verbose, showTime, elapsed)

	if listMatches && len(sum.matchedPaths) > 0 {
		fmt.Println()
		fmt.Println("Matched files:")
		for _, path := range sum.matchedPaths {
			fmt.Printf("  %s\n", path)
		}
	}

	if listMatches && engine.write && len(sum.changedPaths) > 0 {
		fmt.Println()
		fmt.Println("Modified files:")
		for _, path := range sum.changedPaths {
			fmt.Printf("  %s\n", path)
		}
	}

	if len(sum.errors) > 0 {
		fmt.Fprintln(os.Stderr, "\nErrors:")
		for _, entry := range sum.errors {
			fmt.Fprintf(os.Stderr, "  %s: %v\n", entry.path, entry.err)
		}
		os.Exit(1)
	}
}

func printSummary(sum summary, stats finder.Stats, wrote, confirmed, verbose, showTime bool, elapsed time.Duration) {
	fmt.Println()
	fmt.Println("Summary")
	fmt.Println("-------")
	fmt.Printf("Roots scanned:        %d\n", stats.RootsScanned)
	fmt.Printf("Files scanned:        %d\n", stats.FilesScanned)
	fmt.Printf("Text files checked:   %d\n", sum.textFilesChecked)
	fmt.Printf("Matching files:       %d\n", sum.matchingFiles)
	fmt.Printf("Match occurrences:    %d\n", sum.occurrencesFound)
	if wrote {
		fmt.Printf("Files modified:       %d\n", sum.filesChanged)
		fmt.Printf("Replacements applied: %d\n", sum.occurrencesReplaced)
		if confirmed {
			fmt.Printf("Skipped (confirm):    %d\n", sum.confirmDeclined)
		}
	} else {
		fmt.Println("Files modified:       0 (dry run)")
		fmt.Println("Replacements applied: 0")
	}

	if !wrote {
		fmt.Println("\nDry run complete. Re-run with --write to apply replacements.")
	}

	if verbose && showTime {
		fmt.Fprintf(os.Stderr, "\nElapsed: %s\n", elapsed.Round(time.Millisecond))
	}
}

func writeFilePreserveMode(path string, data []byte) error {
	info, err := os.Stat(path)
	if err != nil {
		return err
	}
	mode := info.Mode()

	tmpPath := path + ".rogkit.tmp"
	if err := os.WriteFile(tmpPath, data, mode.Perm()); err != nil {
		return err
	}

	if err := os.Rename(tmpPath, path); err != nil {
		_ = os.Remove(tmpPath)
		return err
	}

	return nil
}

func promptYes(scanner *bufio.Scanner) bool {
	if scanner == nil {
		return false
	}
	if !scanner.Scan() {
		return false
	}
	answer := strings.TrimSpace(scanner.Text())
	return strings.EqualFold(answer, "y") || strings.EqualFold(answer, "yes")
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

func countOccurrences(haystack, needle string) int {
	if needle == "" {
		return 0
	}
	count := 0
	index := 0
	for {
		pos := strings.Index(haystack[index:], needle)
		if pos == -1 {
			break
		}
		count++
		index += pos + len(needle)
	}
	return count
}

func replaceAllCaseInsensitive(s, old, new string) (string, int) {
	if old == "" {
		return s, 0
	}
	lowerS := strings.ToLower(s)
	lowerOld := strings.ToLower(old)

	var builder strings.Builder
	builder.Grow(len(s))

	index := 0
	replacements := 0
	for index < len(s) {
		pos := strings.Index(lowerS[index:], lowerOld)
		if pos == -1 {
			builder.WriteString(s[index:])
			break
		}
		start := index + pos
		builder.WriteString(s[index:start])
		builder.WriteString(new)
		index = start + len(old)
		replacements++
	}

	return builder.String(), replacements
}

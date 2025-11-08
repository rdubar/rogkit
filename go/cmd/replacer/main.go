package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/rdubar/rogkit/go/internal/util"
)

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: replacer --find TEXT [options]

Search recursively for TEXT starting at --path (default ".") and optionally replace it.

Options:
`)
	flag.PrintDefaults()
}

func main() {
	flag.Usage = usage

	root := flag.String("path", ".", "Root directory to search")
	find := flag.String("find", "", "Text to find (required)")
	replace := flag.String("replace", "", "Replacement text (optional)")
	confirm := flag.Bool("confirm", false, "Confirm each replacement interactively")
	showMatches := flag.Bool("list", false, "List matching (and replaced) file paths")
	flag.Parse()

	if len(os.Args) == 1 {
		usage()
		os.Exit(1)
	}

	if strings.TrimSpace(*find) == "" {
		fmt.Fprintln(os.Stderr, "error: --find argument is required\n")
		usage()
		os.Exit(1)
	}

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error resolving path: %v\n", err)
		os.Exit(1)
	}

	summary := process(absRoot, *find, *replace, *confirm, *showMatches)

	fmt.Printf("Scanned %d files in %s\n", summary.totalScanned, summary.duration.Truncate(time.Millisecond))
	fmt.Printf("Matches: %d\n", summary.matches)
	if *replace != "" {
		fmt.Printf("Replacements: %d\n", summary.replacements)
	}
	if len(summary.errors) > 0 {
		fmt.Printf("Errors: %d\n", len(summary.errors))
		for _, e := range summary.errors {
			fmt.Fprintf(os.Stderr, "error: %s (%v)\n", e.path, e.err)
		}
	}
	fmt.Printf("Total time: %s\n", summary.duration.Truncate(time.Millisecond))

	if *showMatches && len(summary.matchedPaths) > 0 {
		fmt.Println("Matching files:")
		for _, path := range summary.matchedPaths {
			fmt.Printf("  %s\n", path)
		}
	}

	if *showMatches && len(summary.replacedPaths) > 0 {
		fmt.Println("Replaced files:")
		for _, path := range summary.replacedPaths {
			fmt.Printf("  %s\n", path)
		}
	}
}

type summary struct {
	totalScanned  int
	matches       int
	replacements  int
	errors        []errorEntry
	duration      time.Duration
	matchedPaths  []string
	replacedPaths []string
}

type errorEntry struct {
	path string
	err  error
}

func process(root, find, replace string, confirm, collectMatches bool) summary {
	start := time.Now()

	var out summary
	var promptReader *bufio.Scanner

	doReplace := replace != ""
	if confirm {
		promptReader = bufio.NewScanner(os.Stdin)
	}

	err := filepath.WalkDir(root, func(path string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			out.errors = append(out.errors, errorEntry{path: path, err: walkErr})
			if d != nil && d.IsDir() && util.ShouldSkip(path) {
				return filepath.SkipDir
			}
			return nil
		}

		if d.IsDir() {
			if util.ShouldSkip(path) && path != root {
				return filepath.SkipDir
			}
			return nil
		}

		if util.ShouldSkip(path) {
			return nil
		}

		out.totalScanned++

		if !util.IsTextFile(path) {
			return nil
		}

		data, err := os.ReadFile(path)
		if err != nil {
			out.errors = append(out.errors, errorEntry{path: path, err: err})
			return nil
		}

		if !strings.Contains(string(data), find) {
			return nil
		}

		out.matches++

		if collectMatches {
			out.matchedPaths = append(out.matchedPaths, path)
		}

		if !doReplace {
			return nil
		}

		replaceContent := strings.ReplaceAll(string(data), find, replace)
		if replaceContent == string(data) {
			return nil
		}

		if confirm {
			fmt.Printf("Replace in %s? [y/N]: ", path)
			if !promptYes(promptReader) {
				return nil
			}
		}

		if err := writeFilePreserveMode(path, []byte(replaceContent)); err != nil {
			out.errors = append(out.errors, errorEntry{path: path, err: err})
			return nil
		}

		out.replacements++
		if collectMatches {
			out.replacedPaths = append(out.replacedPaths, path)
		}
		if confirm {
			fmt.Printf("Replaced: %s\n", path)
		}
		return nil
	})

	out.duration = time.Since(start)

	if err != nil {
		out.errors = append(out.errors, errorEntry{path: root, err: err})
	}

	return out
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

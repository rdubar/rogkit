package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

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
	fmt.Fprintf(os.Stderr, `Usage: fastfind [options]

Traverse directories using an optimized godirwalk-based searcher.

Examples:
  fastfind --search '*.go'
  fastfind --path ~/projects --timer

Options:
`)
	flag.PrintDefaults()
}

func main() {
	flag.Usage = usage

	var roots multiValue
	var searches multiValue

	var (
		countOnly     bool
		ignoreCase    bool
		includeHidden bool
		timer         bool
		verbose       bool
		maxDepth      int
		noIgnore      bool
	)

	flag.Var(&roots, "path", "Root directory to search (repeatable)")
	flag.Var(&roots, "p", "Shorthand for --path")
	flag.Var(&searches, "search", "Pattern to match (glob or substring, repeatable)")
	flag.Var(&searches, "s", "Shorthand for --search")
	flag.BoolVar(&countOnly, "count", false, "Only print the total number of matches")
	flag.BoolVar(&countOnly, "c", false, "Shorthand for --count")
	flag.BoolVar(&ignoreCase, "ignore-case", false, "Perform case-insensitive matching")
	flag.BoolVar(&ignoreCase, "i", false, "Shorthand for --ignore-case")
	flag.BoolVar(&includeHidden, "include-hidden", false, "Include hidden files and directories")
	flag.BoolVar(&includeHidden, "hidden", false, "Shorthand for --include-hidden")
	flag.BoolVar(&timer, "timer", false, "Report how long the search took")
	flag.BoolVar(&verbose, "verbose", false, "Print summary information")
	flag.BoolVar(&verbose, "v", false, "Shorthand for --verbose")
	flag.IntVar(&maxDepth, "max-depth", -1, "Limit search depth relative to the root (-1 for unlimited)")
	flag.BoolVar(&noIgnore, "no-ignore", false, "Include files ignored by .gitignore/.fdignore/.ignore files")

	flag.Parse()

	args := flag.Args()
	if len(searches) == 0 && len(args) > 0 {
		searches = append(searches, args[0])
		args = args[1:]
	}

	for _, arg := range args {
		if arg == "" {
			continue
		}
		roots = append(roots, arg)
	}

	if len(roots) == 0 {
		roots = append(roots, ".")
	}

	opts := finder.FastOptions{
		Roots:         roots,
		Patterns:      searches,
		IgnoreCase:    ignoreCase,
		IncludeHidden: includeHidden,
		MaxDepth:      maxDepth,
		RespectIgnore: !noIgnore,
	}

	var start time.Time
	if timer || verbose {
		start = time.Now()
	}

	stats, err := finder.FastWalk(opts, func(res finder.FastResult) error {
		if countOnly {
			return nil
		}
		fmt.Println(res.Path)
		return nil
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "fastfind: %v\n", err)
		os.Exit(1)
	}

	if countOnly {
		fmt.Println(stats.FilesMatched)
	}

	if timer {
		fmt.Fprintf(os.Stderr, "fastfind: completed in %s\n", time.Since(start))
	}

	if verbose {
		fmt.Fprintf(os.Stderr, "fastfind: scanned %d files across %d roots (%d matches)\n",
			stats.FilesScanned, stats.RootsScanned, stats.FilesMatched)
	}
}

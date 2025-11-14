package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/rdubar/rogkit/go/internal/finder"
)

type multiValue []string

func (m *multiValue) String() string { return strings.Join(*m, ",") }
func (m *multiValue) Set(v string) error {
	*m = append(*m, v)
	return nil
}

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: fastfind [options] <pattern>

Find files and directories whose path or name matches <pattern>.

Examples:
  fastfind tmp
  fastfind -p ~/projects src
  fastfind -e go -e md fastfind
  fastfind -H -n ".swp"

Options:
`)
	flag.PrintDefaults()
}

// fastfind is an experimental alias around finder.FastWalk. Prefer `finder`
// for stable behaviour; use this binary to trial alternate defaults or
// scripting hooks without affecting the primary tool.
func main() {
	flag.CommandLine = flag.NewFlagSet(os.Args[0], flag.ExitOnError)
	flag.Usage = usage

	var roots multiValue
	var patterns multiValue

	var (
		ignoreCase    bool
		caseSensitive bool
		includeHidden bool
		respectIgnore = true
		relativePaths bool
		maxDepth      int
		verbose       bool
		timer         bool
		countOnly     bool
	)

	flag.Var(&roots, "path", "Root directory to search (repeatable)")
	flag.Var(&roots, "p", "Shorthand for --path")

	flag.Var(&patterns, "search", "Pattern to match (glob or substring, repeatable)")
	flag.Var(&patterns, "s", "Shorthand for --search")

	flag.BoolVar(&ignoreCase, "ignore-case", false, "Force case-insensitive matching")
	flag.BoolVar(&ignoreCase, "i", false, "Shorthand for --ignore-case")
	flag.BoolVar(&caseSensitive, "case-sensitive", false, "Force case-sensitive matching (overrides -i)")

	flag.BoolVar(&includeHidden, "hidden", false, "Include hidden files and directories")
	flag.BoolVar(&includeHidden, "H", false, "Shorthand for --hidden")

	flag.BoolVar(&respectIgnore, "respect-ignore", true, "Respect default ignore directories (.git, node_modules, etc)")
	flag.BoolVar(&respectIgnore, "I", true, "Shorthand for --respect-ignore")
	// convenience: --no-ignore
	noIgnore := flag.Bool("no-ignore", false, "Do not respect default ignore directories")
	flag.BoolVar(noIgnore, "n", false, "Shorthand for --no-ignore")

	flag.BoolVar(&relativePaths, "relative", false, "Print paths relative to their root")
	flag.BoolVar(&relativePaths, "r", false, "Shorthand for --relative")

	flag.IntVar(&maxDepth, "max-depth", -1, "Limit search depth relative to the root (-1 for unlimited)")
	flag.IntVar(&maxDepth, "d", -1, "Shorthand for --max-depth")

	flag.BoolVar(&verbose, "verbose", false, "Print summary information")
	flag.BoolVar(&verbose, "v", false, "Shorthand for --verbose")

	flag.BoolVar(&timer, "timer", false, "Report how long the search took")
	flag.BoolVar(&timer, "t", false, "Shorthand for --timer")

	flag.BoolVar(&countOnly, "count", false, "Only print the total number of matches")
	flag.BoolVar(&countOnly, "c", false, "Shorthand for --count")

	flag.Parse()

	if *noIgnore {
		respectIgnore = false
	}

	args := flag.Args()
	if len(patterns) == 0 && len(args) > 0 {
		for _, arg := range args {
			if arg != "" {
				patterns = append(patterns, arg)
			}
		}
	}

	if len(patterns) == 0 {
		fmt.Fprintln(os.Stderr, "error: provide at least one search pattern")
		usage()
		os.Exit(1)
	}

	if len(roots) == 0 {
		roots = multiValue{"."}
	}

	ignorePathsCase := resolveIgnoreCase(patterns, ignoreCase, caseSensitive)

	start := time.Now()

	opts := finder.FastOptions{
		Roots:         roots,
		Patterns:      patterns,
		IgnoreCase:    ignorePathsCase,
		IncludeHidden: includeHidden,
		MaxDepth:      maxDepth,
		RespectIgnore: respectIgnore,
	}

	var matches int64

	stats, err := finder.FastWalk(opts, func(res finder.FastResult) error {
		matches++

		if countOnly {
			return nil
		}

		path := res.Path
		if relativePaths {
			if rel, err := filepath.Rel(res.Root, res.Path); err == nil {
				path = rel
			}
		}
		fmt.Println(path)
		return nil
	})

	if err != nil {
		fmt.Fprintf(os.Stderr, "fastfind: %v\n", err)
		os.Exit(1)
	}

	if countOnly {
		fmt.Println(matches)
	}

	elapsed := time.Since(start)
	if timer {
		fmt.Fprintf(os.Stderr, "fastfind: completed in %s\n", elapsed.Round(time.Millisecond))
	}

	if verbose {
		fmt.Fprintf(os.Stderr, "Scanned %d roots, %d dirs, %d files, %d matches in %s\n",
			stats.RootsScanned, stats.Directories, stats.FilesScanned, matches, elapsed.Round(time.Millisecond))
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
	for _, p := range patterns {
		for _, r := range p {
			if 'A' <= r && r <= 'Z' {
				return false
			}
		}
	}
	return true
}

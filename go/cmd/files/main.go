package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/rdubar/rogkit/go/internal/util"
)

func usage() {
	fmt.Fprintf(os.Stderr, `Usage: files [options] term1 [term2 ...]

Search recursively for files whose paths contain all supplied terms.

Options:
`)
	flag.PrintDefaults()
}

var defaultFolders = []string{
	"/home/rdubar/projects/pythonProject/openerp-addons",
	"/mnt/expansion/Media/Movies/",
	"/mnt/archive/Media/TV Shows/",
}

type fileResult struct {
	path string
	size int64
}

func main() {
	flag.Usage = usage

	folder := flag.String("folder", "", "Folder to search (default: use predefined list)")
	showAll := flag.Bool("all", false, "Show all matching results")
	limit := flag.Int("number", 10, "Number of results to display")
	includeUser := flag.Bool("user", false, "Include the user's home directory in the search")
	flag.Parse()

	if len(os.Args) == 1 {
		usage()
		os.Exit(1)
	}

	terms := flag.Args()
	if len(terms) == 0 {
		fmt.Fprintln(os.Stderr, "error: provide at least one search term\n")
		usage()
		os.Exit(1)
	}

	roots := collectRoots(*folder, *includeUser)
	if len(roots) == 0 {
		fmt.Fprintln(os.Stderr, "error: no valid folders to search")
		os.Exit(1)
	}

	fmt.Printf("Searching in folders: %s\n", strings.Join(roots, ", "))
	fmt.Printf("Looking for files containing all of: %s\n", strings.Join(terms, ", "))

	start := time.Now()
	results, totalFiles := findFiles(roots, terms)
	elapsed := time.Since(start)

	matches := len(results)
	fmt.Printf("Found %d match%s in %d files (%.2f seconds)\n", matches, plural(matches), totalFiles, elapsed.Seconds())

	if matches == 0 {
		return
	}

	if *showAll || *limit >= matches {
		*limit = matches
	}

	if *limit < 0 {
		*limit = 0
	}

	for i := 0; i < *limit; i++ {
		r := results[i]
		fmt.Printf("%10s  %s\n", humanBytes(r.size), r.path)
	}

	if matches > *limit {
		fmt.Println("...and more")
	}
}

func collectRoots(folder string, includeUser bool) []string {
	var roots []string

	if folder != "" {
		if info, err := os.Stat(folder); err == nil && info.IsDir() {
			roots = append(roots, filepath.Clean(folder))
		}
	}

	if len(roots) == 0 {
		for _, candidate := range defaultFolders {
			if info, err := os.Stat(candidate); err == nil && info.IsDir() {
				roots = append(roots, filepath.Clean(candidate))
			}
		}
	}

	if includeUser || len(roots) == 0 {
		if home, err := os.UserHomeDir(); err == nil {
			roots = append(roots, home)
		}
	}

	return roots
}

func findFiles(roots []string, terms []string) ([]fileResult, int) {
	needles := make([]string, len(terms))
	for i, term := range terms {
		needles[i] = strings.ToLower(term)
	}

	var results []fileResult
	var totalFiles int

	for _, root := range roots {
		filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
			if err != nil {
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

			totalFiles++

			lower := strings.ToLower(path)
			for _, needle := range needles {
				if !strings.Contains(lower, needle) {
					return nil
				}
			}

			info, err := d.Info()
			if err != nil {
				return nil
			}

			results = append(results, fileResult{
				path: path,
				size: info.Size(),
			})

			return nil
		})
	}

	return results, totalFiles
}

func humanBytes(size int64) string {
	const (
		kb = 1024
		mb = 1024 * kb
		gb = 1024 * mb
	)

	switch {
	case size >= gb:
		return fmt.Sprintf("%.2f GB", float64(size)/float64(gb))
	case size >= mb:
		return fmt.Sprintf("%.2f MB", float64(size)/float64(mb))
	case size >= kb:
		return fmt.Sprintf("%.2f KB", float64(size)/float64(kb))
	default:
		return fmt.Sprintf("%d B", size)
	}
}

func plural(n int) string {
	if n == 1 {
		return ""
	}
	return "es"
}

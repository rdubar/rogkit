package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/sahilm/fuzzy"
)

const (
	cacheDirName  = "dirfind"
	cacheFileName = "cache.json"
)

type Cache struct {
	Results map[string][]string `json:"results"`
	Updated time.Time           `json:"updated"`
}

func getCachePath() (string, error) {
	conf, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(conf, cacheDirName, cacheFileName), nil
}

func loadCache() (Cache, error) {
	var c Cache
	cacheFile, err := getCachePath()
	if err != nil {
		return c, err
	}
	data, err := os.ReadFile(cacheFile)
	if err != nil {
		return Cache{Results: make(map[string][]string)}, nil
	}
	err = json.Unmarshal(data, &c)
	if err != nil {
		return Cache{Results: make(map[string][]string)}, nil
	}
	return c, nil
}

func saveCache(c Cache) error {
	cachePath, err := getCachePath()
	if err != nil {
		return err
	}

	dir := filepath.Dir(cachePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(cachePath, data, 0644)
}

func runFD(searchRoot, query string, includeHidden bool, verbose bool) ([]string, error) {
	pattern, useGlob := buildFdPattern(query)
	args := []string{"-t", "d"}
	if includeHidden {
		args = append(args, "-H")
	}
	if useGlob {
		args = append(args, "--glob", pattern)
	} else {
		args = append(args, pattern)
	}
	args = append(args, searchRoot)
	if verbose {
		fmt.Fprintf(os.Stderr, "[dirfind] running fd %v\n", args)
	}
	cmd := exec.Command("fd", args...)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	var cleaned []string
	for _, l := range lines {
		if l != "" {
			cleaned = append(cleaned, l)
		}
	}
	if verbose {
		fmt.Fprintf(os.Stderr, "[dirfind] fd returned %d entries\n", len(cleaned))
	}
	return cleaned, nil
}

func fuzzyRank(results []string, query string) []string {
	matches := fuzzy.Find(query, results)

	var ranked []string
	for _, m := range matches {
		ranked = append(ranked, results[m.Index])
	}
	return ranked
}

func findDirs(query string, rootOverride string, includeHidden bool, verbose bool) ([]string, error) {
	root, err := resolveRoot(rootOverride)
	if err != nil {
		return nil, err
	}
	if verbose {
		fmt.Fprintf(os.Stderr, "[dirfind] searching %s\n", root)
	}
	results, err := runFD(root, query, includeHidden, verbose)
	if err != nil {
		return nil, err
	}
	if len(results) == 0 {
		return nil, fmt.Errorf("no matches found in %s", root)
	}
	ranked := fuzzyRank(results, query)
	if verbose {
		fmt.Fprintf(os.Stderr, "[dirfind] %d matches in %s\n", len(ranked), root)
	}
	return ranked, nil
}

func resolveRoot(rootOverride string) (string, error) {
	if rootOverride != "" {
		return rootOverride, nil
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("unable to determine home directory: %w", err)
	}
	return home, nil
}

func displayRoot(rootOverride string) string {
	if rootOverride != "" {
		return rootOverride
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "<home>"
	}
	return home
}

func buildFdPattern(query string) (string, bool) {
	trimmed := strings.TrimSpace(query)
	if trimmed == "" {
		return "", false
	}
	tokens := strings.Fields(trimmed)
	pattern := "*" + strings.Join(tokens, "*") + "*"
	return pattern, true
}

func printCache(c Cache) {
	if len(c.Results) == 0 {
		fmt.Println("Cache is empty.")
		return
	}
	for key, entries := range c.Results {
		parts := strings.Split(key, "::")
		root := ""
		pattern := ""
		hidden := "false"
		if len(parts) > 0 {
			root = parts[0]
		}
		if len(parts) > 1 {
			pattern = parts[1]
		}
		if len(parts) > 2 {
			hidden = parts[2]
		}
		fmt.Printf("root=%s hidden=%s query=%s (%d hits)\n", root, hidden, pattern, len(entries))
	}
}

func clearCacheFile() {
	path, err := getCachePath()
	if err != nil {
		fmt.Fprintf(os.Stderr, "unable to locate cache path: %v\n", err)
		return
	}
	if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "failed to remove cache: %v\n", err)
	}
}

func printResults(results []string, all bool) {
	if len(results) == 0 {
		fmt.Fprintln(os.Stderr, "No results.")
		return
	}

	if !all {
		fmt.Println(results[0])
		return
	}

	for _, r := range results {
		fmt.Println(r)
	}
}

func printUsage() {
	fmt.Println(`dirfind <pattern> [options]
Experimental directory locator built with fd + Go + fuzzy ranking.

Options:
  -a, --all   Show all matches
  -s, --shell Open a new shell session at the best match
  -v, --verbose Show detailed search diagnostics
  -r, --root  Search this root instead of the user home directory
  -h, --hidden Include hidden directories in the search
  -c, --cache  Display cached entries and exit
      --clear-cache Clear cached entries and exit
`)
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	var parts []string
	all := false
	shellSession := false
	verbose := false
	includeHidden := false
	showCache := false
	clearCache := false
	rootOverride := ""
	start := time.Now()

	for i := 1; i < len(os.Args); i++ {
		arg := os.Args[i]
		switch arg {
		case "-a", "--all":
			all = true
		case "-s", "--shell":
			shellSession = true
		case "-v", "--verbose":
			verbose = true
		case "-h", "--hidden":
			includeHidden = true
		case "-c", "--cache":
			showCache = true
		case "--clear-cache":
			clearCache = true
		case "-r", "--root":
			if i+1 >= len(os.Args) {
				fmt.Fprintln(os.Stderr, "--root expects a path")
				os.Exit(1)
			}
			i++
			rootOverride = os.Args[i]
		default:
			parts = append(parts, arg)
		}
	}

	query := strings.TrimSpace(strings.Join(parts, " "))

	cache, _ := loadCache()
	if cache.Results == nil {
		cache.Results = make(map[string][]string)
	}
	if showCache {
		if verbose {
			fmt.Fprintln(os.Stderr, "[dirfind] cache contents:")
		}
		printCache(cache)
	}
	if clearCache {
		if verbose {
			fmt.Fprintln(os.Stderr, "[dirfind] clearing cache")
		}
		clearCacheFile()
		cache.Results = make(map[string][]string)
	}

	if query == "" {
		if showCache || clearCache {
			return
		}
		printUsage()
		os.Exit(1)
	}

	cacheKey := fmt.Sprintf("%s::%s::%t", rootOverride, query, includeHidden)

	// Cached results?
	if cached, ok := cache.Results[cacheKey]; ok {
		if verbose {
			fmt.Fprintf(
				os.Stderr,
				"[dirfind] cache hit for %q (root %q, hidden=%t)\n",
				query,
				displayRoot(rootOverride),
				includeHidden,
			)
		}
		printResults(cached, all)
		if verbose {
			fmt.Fprintf(os.Stderr, "[dirfind] completed in %s\n", time.Since(start))
		}
		return
	}

	// Fresh search
	results, err := findDirs(query, rootOverride, includeHidden, verbose)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%v\n", err)
		os.Exit(1)
	}

	printResults(results, all)

	if shellSession && len(results) > 0 && !all {
		if err := launchShell(results[0]); err != nil {
			fmt.Fprintf(os.Stderr, "failed to launch shell: %v\n", err)
		}
	}

	// Update cache
	cache.Results[cacheKey] = results
	cache.Updated = time.Now()
	saveCache(cache)

	if verbose {
		fmt.Fprintf(os.Stderr, "[dirfind] completed in %s\n", time.Since(start))
	}
}

func launchShell(target string) error {
	shell := os.Getenv("SHELL")
	if shell == "" {
		shell = "sh"
	}
	cmd := exec.Command(shell, "-l")
	cmd.Dir = target
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

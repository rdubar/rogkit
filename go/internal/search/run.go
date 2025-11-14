package search

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
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

func usage(progName string, fs *flag.FlagSet, errOut io.Writer) {
	fmt.Fprintf(errOut, "Usage: %s [options] term1 [term2 ...]\n\n", progName)
	fmt.Fprintln(errOut, "Search recursively for files whose contents contain all supplied terms.")
	fmt.Fprintln(errOut)
	fmt.Fprintln(errOut, "Each positional argument becomes an independent term. Wrap phrases in double quotes")
	fmt.Fprintln(errOut, "so they are treated as a single term. By default matching is case-insensitive unless")
	fmt.Fprintln(errOut, "any term contains an uppercase character (smart case). Use --case-sensitive or")
	fmt.Fprintln(errOut, "--ignore-case to explicitly control the behaviour.")
	fmt.Fprintln(errOut)
	fmt.Fprintln(errOut, "Examples:")
	fmt.Fprintf(errOut, "  %s TODO\n", progName)
	fmt.Fprintf(errOut, "  %s fixme panic\n", progName)
	fmt.Fprintf(errOut, "  %s --path ~/projects --limit 50 foo \"bar baz\"\n", progName)
	fmt.Fprintf(errOut, "  %s --no-ignore password\n", progName)
	fmt.Fprintln(errOut)
	fmt.Fprintln(errOut, "Options:")
	fs.PrintDefaults()
}

type matchConfig struct {
	rawTerms        []string
	normalized      []string
	caseInsensitive bool
	maxNeedleLen    int
}

// buildMatchConfig normalizes terms and precomputes the maximum term length.
func buildMatchConfig(terms []string, ignoreCase bool) (matchConfig, error) {
	if len(terms) == 0 {
		return matchConfig{}, errors.New("no search terms provided")
	}

	normalized := make([]string, 0, len(terms))
	maxLen := 0

	for _, term := range terms {
		base := strings.TrimSpace(term)
		if base == "" {
			return matchConfig{}, errors.New("empty search term")
		}
		if ignoreCase {
			base = strings.ToLower(base)
		}
		normalized = append(normalized, base)
		if l := len(base); l > maxLen {
			maxLen = l
		}
	}

	return matchConfig{
		rawTerms:        terms,
		normalized:      normalized,
		caseInsensitive: ignoreCase,
		maxNeedleLen:    maxLen,
	}, nil
}

// matches streams the file and checks that *all* terms appear at least once.
// It is boundary-safe: matches that cross read-buffer boundaries are still detected.
func (cfg matchConfig) matches(r io.Reader) (bool, error) {
	if len(cfg.normalized) == 0 {
		return false, errors.New("no search terms configured")
	}

	needles := cfg.normalized
	found := make([]bool, len(needles))
	remaining := len(needles)

	// No need for boundary handling if max needle len is 0 (shouldn't happen) or 1.
	maxLen := cfg.maxNeedleLen
	if maxLen < 1 {
		maxLen = 1
	}

	const bufSize = 64 * 1024
	buf := make([]byte, bufSize)
	var tail string

	for {
		n, err := r.Read(buf)
		if n > 0 {
			chunk := string(buf[:n])
			if cfg.caseInsensitive {
				chunk = strings.ToLower(chunk)
			}

			segment := tail + chunk

			for i, needle := range needles {
				if found[i] {
					continue
				}
				if strings.Contains(segment, needle) {
					found[i] = true
					remaining--
					if remaining == 0 {
						return true, nil
					}
				}
			}

			// Keep a tail so that terms crossing buffer boundaries can still be matched.
			// We only need maxLen-1 bytes from the end.
			if maxLen > 1 {
				if len(segment) >= maxLen-1 {
					tail = segment[len(segment)-(maxLen-1):]
				} else {
					tail = segment
				}
			} else {
				tail = ""
			}
		}

		if err == io.EOF {
			break
		}
		if err != nil {
			return false, err
		}
	}

	// If we exit the loop without having found all terms:
	return false, nil
}

// resolveIgnoreCase decides whether a pattern / term set should be matched case-insensitively.
// Priority:
//  1. --case-sensitive => always false
//  2. --ignore-case    => always true
//  3. smartCase()      => depends on presence of uppercase letters
func resolveIgnoreCase(patterns []string, ignoreCase bool, caseSensitive bool) bool {
	if caseSensitive {
		return false
	}
	if ignoreCase {
		return true
	}
	return smartCase(patterns)
}

// smartCase emulates ripgrep's behaviour:
//   - if any pattern contains an uppercase letter => case-sensitive
//   - otherwise => case-insensitive
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

// scanResult represents the outcome of scanning a single file.
type scanResult struct {
	res     finder.Result
	matched bool
	err     error
}

// global stop flag to short-circuit heavy scanning work when we've hit the limit.
// We still drain channels so nothing deadlocks, but workers can skip expensive I/O.
var stopScanFlag int32

func shouldStopScanning() bool {
	return atomic.LoadInt32(&stopScanFlag) != 0
}

func requestStopScanning() {
	atomic.StoreInt32(&stopScanFlag, 1)
}

// worker consumes finder.Results from fileCh, scans them, and sends
// matches (and optionally errors) to resultCh.
func worker(fileCh <-chan finder.Result, resultCh chan<- scanResult, cfg matchConfig, reportErrors bool) {
	for res := range fileCh {
		if shouldStopScanning() {
			// Drain remaining work quickly without scanning.
			continue
		}

		f, err := os.Open(res.Path)
		if err != nil {
			if reportErrors {
				resultCh <- scanResult{
					res: res,
					err: fmt.Errorf("open %s: %w", res.Path, err),
				}
			}
			continue
		}

		matched, mErr := cfg.matches(f)
		closeErr := f.Close()
		if mErr != nil {
			if reportErrors {
				resultCh <- scanResult{
					res: res,
					err: fmt.Errorf("read %s: %w", res.Path, mErr),
				}
			}
			continue
		}
		if closeErr != nil && reportErrors {
			resultCh <- scanResult{
				res: res,
				err: fmt.Errorf("close %s: %w", res.Path, closeErr),
			}
			continue
		}

		if matched {
			resultCh <- scanResult{
				res:     res,
				matched: true,
			}
		}
	}
}

func Run(args []string, out io.Writer, errOut io.Writer, progName string) int {
	fs := flag.NewFlagSet(progName, flag.ContinueOnError)
	fs.SetOutput(errOut)
	fs.Usage = func() {
		usage(progName, fs, errOut)
	}

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

	fs.Var(&roots, "path", "Root directory to search (repeatable)")
	fs.Var(&roots, "p", "Shorthand for --path")
	fs.Var(&pathPatterns, "filter", "Restrict content search to files whose paths match these patterns (glob or substring, repeatable)")
	fs.Var(&includeExts, "ext", "Only include files with this extension (repeatable, no leading dot required)")
	fs.Var(&excludeExts, "exclude-ext", "Exclude files with this extension (repeatable)")
	fs.BoolVar(&countOnly, "count", false, "Only print the total number of matching files")
	fs.BoolVar(&ignoreCase, "ignore-case", false, "Force case-insensitive matching")
	fs.BoolVar(&caseSensitive, "case-sensitive", false, "Force case-sensitive matching (overrides --ignore-case)")
	fs.BoolVar(&includeHidden, "include-hidden", false, "Include hidden files and directories")
	fs.BoolVar(&includeHidden, "hidden", false, "Shorthand for --include-hidden")
	fs.BoolVar(&showTime, "time", false, "Display how long the search took (requires --verbose)")
	fs.BoolVar(&relativePaths, "relative", false, "Print paths relative to their root")
	fs.BoolVar(&withSize, "with-size", false, "Include the file size (bytes) in the output")
	fs.IntVar(&maxDepth, "max-depth", -1, "Limit search depth relative to the root (-1 for unlimited)")
	fs.BoolVar(&noIgnore, "no-ignore", false, "Include files ignored by .gitignore/.fdignore/.ignore files")
	fs.BoolVar(&includeIgnored, "include-ignored", false, "Alias for --no-ignore")
	fs.BoolVar(&verbose, "verbose", false, "Print summary information")
	fs.BoolVar(&verbose, "v", false, "Shorthand for --verbose")
	fs.BoolVar(&showAll, "all", false, "Display every match (overrides --limit)")
	fs.IntVar(&limit, "limit", 20, "Maximum number of matches to display (use --all to show every match)")
	fs.BoolVar(&showErrors, "show-errors", false, "Display files that could not be read")

	if err := fs.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}

	if includeIgnored {
		noIgnore = true
	}

	if len(roots) == 0 {
		roots = append(roots, ".")
	}

	terms := fs.Args()
	if len(terms) == 0 {
		fmt.Fprintln(errOut, "error: provide at least one search term")
		usage(progName, fs, errOut)
		return 1
	}

	// Reset any previous run's global flag (paranoia if reused in tests).
	atomic.StoreInt32(&stopScanFlag, 0)

	contentIgnoreCase := resolveIgnoreCase(terms, ignoreCase, caseSensitive)

	matchCfg, err := buildMatchConfig(terms, contentIgnoreCase)
	if err != nil {
		fmt.Fprintf(errOut, "%s: %v\n", progName, err)
		return 1
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

	workers := runtime.NumCPU()
	if workers < 1 {
		workers = 1
	}

	fileCh := make(chan finder.Result, 1024)
	resultCh := make(chan scanResult, 1024)

	var wg sync.WaitGroup
	wg.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer wg.Done()
			worker(fileCh, resultCh, matchCfg, showErrors)
		}()
	}

	// Close resultCh once all workers have exited.
	go func() {
		wg.Wait()
		close(resultCh)
	}()

	var stats finder.Stats
	var walkErr error
	walkDone := make(chan struct{})

	// Walk filesystem in its own goroutine so we can process results concurrently.
	var filesDispatched int64

	go func() {
		stats, walkErr = finder.Walk(opts, func(res finder.Result) error {
			if shouldStopScanning() {
				// We've hit the limit; don't enqueue more files, but keep walking
				// cheaply so Walk can complete.
				return nil
			}
			fileCh <- res
			atomic.AddInt64(&filesDispatched, 1)
			return nil
		})
		// No more files to scan.
		close(fileCh)
		close(walkDone)
	}()

	var (
		matches   int64
		printed   int
		errorList []string
	)

	var start time.Time
	if verbose && showTime {
		start = time.Now()
	}

	// Consume scan results as they arrive.
	for r := range resultCh {
		if r.err != nil {
			// Errors only appear if showErrors==true; but we still store them and
			// optionally print later.
			errorList = append(errorList, r.err.Error())
			continue
		}
		if !r.matched {
			continue
		}

		matches++

		if countOnly {
			// Just counting; don't print, don't stop early.
			continue
		}

		if !showAll && limit >= 0 && printed >= limit {
			// We've already printed up to the limit; we still need to drain resultCh
			// to avoid deadlocks, but we won't print more.
			continue
		}

		output := r.res.Path
		if relativePaths {
			if rel, err := filepath.Rel(r.res.Root, r.res.Path); err == nil {
				output = rel
			}
		}

		if withSize {
			fmt.Fprintf(out, "%12d  %s\n", r.res.Info.Size(), output)
		} else {
			fmt.Fprintln(out, output)
		}

		printed++

		// Once we've printed up to the limit, request to stop scanning more content.
		if !showAll && limit >= 0 && printed >= limit {
			requestStopScanning()
		}
	}

	// Ensure the walker goroutine has finished so stats / walkErr are valid.
	<-walkDone

	if walkErr != nil {
		fmt.Fprintf(errOut, "%s: %v\n", progName, walkErr)
		return 1
	}

	if countOnly {
		fmt.Fprintln(out, matches)
	}

	if verbose {
		if showTime {
			elapsed := time.Since(start)
			fmt.Fprintf(errOut, "Scanned %d files across %d roots (%d matches, %d dispatched) in %s\n",
				stats.FilesScanned, stats.RootsScanned, matches, filesDispatched, elapsed.Round(time.Millisecond))
		} else if !countOnly {
			fmt.Fprintf(errOut, "Matched %d file(s) (scanned %d)\n", matches, stats.FilesScanned)
		}
	}

	if showErrors && len(errorList) > 0 {
		fmt.Fprintln(errOut, "Errors:")
		for _, msg := range errorList {
			fmt.Fprintf(errOut, "  %s\n", msg)
		}
	}

	return 0
}

package finder

import (
	"bufio"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/go-git/go-git/v5/plumbing/format/gitignore"
	"github.com/rdubar/rogkit/go/internal/util"
)

// Options describes how a search should be performed.
type Options struct {
	Roots         []string // Directories to search
	Patterns      []string // Glob or substring patterns to match
	IgnoreCase    bool     // Whether to perform case-insensitive matching
	IncludeHidden bool     // Include dotfiles and dot-directories
	IncludeExt    []string // Only include files with these extensions (leading dot optional)
	ExcludeExt    []string // Skip files with these extensions (leading dot optional)
	MaxDepth      int      // Maximum depth relative to the root (-1 for unlimited)
	RespectIgnore bool     // Respect .gitignore/.ignore/.fdignore files
}

// Result represents a matching file.
type Result struct {
	Root string
	Path string
	Info fs.FileInfo
}

// Stats captures details about a walk.
type Stats struct {
	RootsScanned  int
	FilesScanned  int64
	FilesMatched  int64
	Directories   int64
	PatternsUsed  int
	IncludeFilter int
	ExcludeFilter int
}

// FastOptions configures the high-performance walker backed by godirwalk.
type FastOptions struct {
	Roots         []string
	Patterns      []string
	IgnoreCase    bool
	IncludeHidden bool
	MaxDepth      int
	RespectIgnore bool
}

// FastResult contains information about a matched entry returned by FastWalk.
type FastResult struct {
	Root string
	Path string
	Name string
}

// Walk traverses the configured roots and invokes cb for each file that satisfies the options.
func Walk(opts Options, cb func(Result) error) (Stats, error) {
	var stats Stats

	if len(opts.Roots) == 0 {
		return stats, errors.New("finder: no roots provided")
	}

	compiledPatterns, err := compilePatterns(opts.Patterns, opts.IgnoreCase)
	if err != nil {
		return stats, err
	}

	includeExts := normalizeExtensions(opts.IncludeExt)
	excludeExts := normalizeExtensions(opts.ExcludeExt)

	stats.PatternsUsed = len(compiledPatterns)
	if includeExts != nil {
		stats.IncludeFilter = len(includeExts)
	}
	if excludeExts != nil {
		stats.ExcludeFilter = len(excludeExts)
	}

	var roots []string
	for _, root := range opts.Roots {
		if root == "" {
			continue
		}
		clean := filepath.Clean(root)
		info, err := os.Stat(clean)
		if err != nil {
			return stats, fmt.Errorf("finder: unable to stat root %q: %w", root, err)
		}
		if !info.IsDir() {
			return stats, fmt.Errorf("finder: root %q is not a directory", root)
		}
		roots = append(roots, clean)
	}

	if len(roots) == 0 {
		return stats, errors.New("finder: no valid roots to scan")
	}

	for _, root := range roots {
		stats.RootsScanned++
		rootDepth := depthOf(root)
		ignoreStates := map[string]ignoreState{}

		err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}

			relDepth := depthOf(path) - rootDepth
			if opts.MaxDepth >= 0 && relDepth > opts.MaxDepth {
				if entry.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}

			name := entry.Name()
			isDir := entry.IsDir()

			var parentDir string
			if path == root {
				parentDir = ""
			} else {
				parentDir = filepath.Dir(path)
			}

			state := ignoreState{}
			if parentDir != "" {
				state = ignoreStates[parentDir]
			}

			if isDir {
				if opts.RespectIgnore {
					extended, err := extendIgnoreState(state, root, path)
					if err != nil {
						return err
					}
					state = extended
				}

				if path != root {
					if opts.RespectIgnore && shouldIgnore(state.matcher, root, path, true) {
						return filepath.SkipDir
					}
					if !opts.IncludeHidden && isHiddenName(name) {
						return filepath.SkipDir
					}
					if util.ShouldSkip(path) {
						return filepath.SkipDir
					}
				}

				stats.Directories++
				ignoreStates[path] = state
				return nil
			}

			if opts.RespectIgnore && shouldIgnore(state.matcher, root, path, false) {
				return nil
			}

			stats.FilesScanned++

			if !opts.IncludeHidden && isHiddenName(name) {
				return nil
			}

			if util.ShouldSkip(path) {
				return nil
			}

			relativePath, relErr := filepath.Rel(root, path)
			if relErr != nil {
				relativePath = path
			}

			normalizedPath := relativePath
			normalizedAbs := path
			normalizedBase := name
			if opts.IgnoreCase {
				normalizedPath = strings.ToLower(normalizedPath)
				normalizedBase = strings.ToLower(normalizedBase)
				normalizedAbs = strings.ToLower(normalizedAbs)
			}

			if len(compiledPatterns) > 0 && !matchesAny(compiledPatterns, normalizedPath, normalizedBase, normalizedAbs) {
				return nil
			}

			if includeExts != nil || excludeExts != nil {
				ext := strings.ToLower(filepath.Ext(name))
				if includeExts != nil {
					if _, ok := includeExts[ext]; !ok {
						return nil
					}
				}
				if excludeExts != nil {
					if _, ok := excludeExts[ext]; ok {
						return nil
					}
				}
			}

			info, err := entry.Info()
			if err != nil {
				return err
			}

			stats.FilesMatched++
			if cb != nil {
				if err := cb(Result{
					Root: root,
					Path: path,
					Info: info,
				}); err != nil {
					return err
				}
			}
			return nil
		})
		if err != nil {
			return stats, err
		}
	}

	return stats, nil
}

// FastWalk traverses roots using the same filtering logic as Walk but with a
// stripped-down result payload. It currently delegates to Walk for stability.
func FastWalk(opts FastOptions, cb func(FastResult) error) (Stats, error) {
	options := Options{
		Roots:         opts.Roots,
		Patterns:      opts.Patterns,
		IgnoreCase:    opts.IgnoreCase,
		IncludeHidden: opts.IncludeHidden,
		MaxDepth:      opts.MaxDepth,
		RespectIgnore: opts.RespectIgnore,
	}

	stats, err := Walk(options, func(res Result) error {
		if cb == nil {
			return nil
		}
		return cb(FastResult{
			Root: res.Root,
			Path: res.Path,
			Name: res.Info.Name(),
		})
	})

	return stats, err
}

type compiledPattern struct {
	value  string
	isGlob bool
}

func compilePatterns(patterns []string, ignoreCase bool) ([]compiledPattern, error) {
	var result []compiledPattern
	for _, raw := range patterns {
		raw = strings.TrimSpace(raw)
		if raw == "" {
			continue
		}
		pattern := raw
		if ignoreCase {
			pattern = strings.ToLower(pattern)
		}
		cp := compiledPattern{
			value:  pattern,
			isGlob: strings.ContainsAny(raw, "*?["),
		}
		if cp.isGlob {
			if _, err := filepath.Match(raw, ""); err != nil {
				return nil, fmt.Errorf("finder: invalid pattern %q: %w", raw, err)
			}
		}
		result = append(result, cp)
	}
	return result, nil
}

func matchesAny(patterns []compiledPattern, relPath string, base string, absPath string) bool {
	for _, p := range patterns {
		if p.isGlob {
			if ok, _ := filepath.Match(p.value, relPath); ok {
				return true
			}
			if ok, _ := filepath.Match(p.value, absPath); ok {
				return true
			}
			if ok, _ := filepath.Match(p.value, base); ok {
				return true
			}
			continue
		}
		if strings.Contains(relPath, p.value) || strings.Contains(base, p.value) || strings.Contains(absPath, p.value) {
			return true
		}
	}
	return false
}

func normalizeExtensions(exts []string) map[string]struct{} {
	if len(exts) == 0 {
		return nil
	}
	result := make(map[string]struct{})
	for _, ext := range exts {
		trimmed := strings.TrimSpace(ext)
		if trimmed == "" {
			continue
		}
		if !strings.HasPrefix(trimmed, ".") {
			trimmed = "." + trimmed
		}
		result[strings.ToLower(trimmed)] = struct{}{}
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

func depthOf(path string) int {
	if path == "" {
		return 0
	}
	return strings.Count(filepath.Clean(path), string(os.PathSeparator))
}

func isHiddenName(name string) bool {
	if name == "" {
		return false
	}
	if name == "." || name == ".." {
		return false
	}
	return strings.HasPrefix(name, ".")
}

type ignoreState struct {
	patterns []gitignore.Pattern
	matcher  gitignore.Matcher
}

func extendIgnoreState(parent ignoreState, root, dir string) (ignoreState, error) {
	rel, err := filepath.Rel(root, dir)
	if err != nil {
		rel = "."
	}
	rel = filepath.ToSlash(rel)
	if rel == "." {
		rel = ""
	}

	base := splitPath(rel)
	var additions []gitignore.Pattern

	for _, name := range []string{".gitignore", ".fdignore", ".ignore"} {
		file := filepath.Join(dir, name)
		patterns, err := loadIgnorePatterns(file, base)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				continue
			}
			return ignoreState{}, err
		}
		additions = append(additions, patterns...)
	}

	if len(additions) == 0 {
		return parent, nil
	}

	combined := make([]gitignore.Pattern, 0, len(parent.patterns)+len(additions))
	combined = append(combined, parent.patterns...)
	combined = append(combined, additions...)

	return ignoreState{
		patterns: combined,
		matcher:  gitignore.NewMatcher(combined),
	}, nil
}

func loadIgnorePatterns(filePath string, base []string) ([]gitignore.Pattern, error) {
	f, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var patterns []gitignore.Pattern
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		patterns = append(patterns, gitignore.ParsePattern(line, base))
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return patterns, nil
}

func shouldIgnore(matcher gitignore.Matcher, root, path string, isDir bool) bool {
	if matcher == nil {
		return false
	}

	rel, err := filepath.Rel(root, path)
	if err != nil {
		return false
	}
	rel = filepath.ToSlash(rel)
	if rel == "." {
		rel = ""
	}
	segments := splitPath(rel)

	return matcher.Match(segments, isDir)
}

func splitPath(path string) []string {
	if path == "" {
		return nil
	}
	return strings.Split(path, "/")
}

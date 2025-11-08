package util

import (
	"path/filepath"
	"strings"
)

var skipParts = map[string]struct{}{
	"node_modules": {},
	".git":         {},
	".venv":        {},
	".tox":         {},
	"__pycache__":  {},
	"env":          {},
	"eggs":         {},
	"parts":        {},
}

var textExtensions = map[string]struct{}{
	".txt":  {},
	".md":   {},
	".rst":  {},
	".csv":  {},
	".conf": {},
	".json": {},
	".xml":  {},
	".html": {},
	".htm":  {},
	".css":  {},
	".js":   {},
	".ts":   {},
	".go":   {},
	".sh":   {},
	".py":   {},
	".toml": {},
	".po":   {},
	".pot":  {},
	".mako": {},
	".ini":  {},
	".cfg":  {},
	".yaml": {},
	".yml":  {},
}

// ShouldSkip returns true if the path should be skipped based on common directory names.
func ShouldSkip(path string) bool {
	for _, part := range strings.Split(path, string(filepath.Separator)) {
		if _, ok := skipParts[part]; ok {
			return true
		}
	}
	return false
}

// IsTextFile returns true if the path has a recognised text file extension.
func IsTextFile(path string) bool {
	if info, ok := textExtensions[strings.ToLower(filepath.Ext(path))]; ok {
		_ = info
		return true
	}
	return false
}

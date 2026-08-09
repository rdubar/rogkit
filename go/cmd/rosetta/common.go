package main

import (
	"path/filepath"
	"regexp"
)

// app groups translated pids under one canonical app name.
type app struct {
	Name string `json:"name"`
	Pids []int  `json:"pids"`
}

var appBundlePath = regexp.MustCompile(`/([^/]+)\.app/Contents/MacOS/`)
var helperSuffix = regexp.MustCompile(`\s+Helper(\s*\([^)]*\))?$`)

// canonicalAppName turns a `ps` comm (often a full executable path) into a
// human-readable app name: pull the bundle name out of a `.app/Contents/
// MacOS/` path when present, else fall back to the basename, and strip
// Chromium/Electron-style " Helper (Renderer)" suffixes so helper processes
// roll up under their parent app — mirrors the `mem` tool's grouping.
func canonicalAppName(comm string) string {
	name := comm
	if m := appBundlePath.FindStringSubmatch(comm); m != nil {
		name = m[1]
	} else {
		name = filepath.Base(comm)
	}
	return helperSuffix.ReplaceAllString(name, "")
}

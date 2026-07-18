package main

import (
	"bufio"
	"bytes"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// proc is one running process: RSS in bytes plus both the raw ps `comm`
// (used for pattern matching, since it carries the full path) and the
// basename derived from it (used for display and grouping).
type proc struct {
	pid  int
	name string
	rss  uint64
}

// group is a set of processes rolled up under one canonical app name.
type group struct {
	name  string
	procs int
	rss   uint64
}

// readProcs shells out to `ps -axo pid=,rss=,comm=` once and parses every
// line — a single exec is fast enough that there's no need for a psutil-style
// per-process syscall loop, and the column set is identical on macOS (BSD ps)
// and Linux (procps).
func readProcs() ([]proc, error) {
	out, err := exec.Command("ps", "-axo", "pid=,rss=,comm=").Output()
	if err != nil {
		return nil, err
	}

	var procs []proc
	scanner := bufio.NewScanner(bytes.NewReader(out))
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 3 {
			continue
		}
		pid, err := strconv.Atoi(fields[0])
		if err != nil {
			continue
		}
		rssKB, err := strconv.ParseUint(fields[1], 10, 64)
		if err != nil {
			continue
		}
		comm := strings.Join(fields[2:], " ")
		procs = append(procs, proc{
			pid:  pid,
			name: filepath.Base(comm),
			rss:  rssKB * 1024,
		})
	}
	return procs, scanner.Err()
}

// helperSuffix strips Chromium/Electron-style helper-process suffixes (e.g.
// "Google Chrome Helper (Renderer)", "Slack Helper") so every helper rolls
// up under the same canonical app name as its parent in the grouped summary.
var helperSuffix = regexp.MustCompile(`\s+Helper(\s*\([^)]*\))?$`)

func canonicalName(name string) string {
	return helperSuffix.ReplaceAllString(name, "")
}

// groupByName buckets procs under their canonical app name, summing RSS and
// counting instances.
func groupByName(procs []proc) []group {
	index := make(map[string]int)
	var groups []group
	for _, p := range procs {
		name := canonicalName(p.name)
		if i, ok := index[name]; ok {
			groups[i].procs++
			groups[i].rss += p.rss
			continue
		}
		index[name] = len(groups)
		groups = append(groups, group{name: name, procs: 1, rss: p.rss})
	}
	return groups
}

// matchProcs returns processes whose name (raw ps comm, not the canonical
// name) contains pattern case-insensitively — the raw comm still carries
// "chrome" in every helper's path, so no canonicalization is needed to match.
func matchProcs(procs []proc, pattern string) []proc {
	needle := strings.ToLower(pattern)
	var out []proc
	for _, p := range procs {
		if strings.Contains(strings.ToLower(p.name), needle) {
			out = append(out, p)
		}
	}
	return out
}

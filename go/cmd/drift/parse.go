package main

import (
	"regexp"
	"strconv"
	"strings"
)

// parseLsofLines parses `lsof -nP -iTCP -sTCP:LISTEN`/`-iUDP` output. The
// NAME column (last field, or second-to-last when lsof appends "(LISTEN)")
// looks like "*:8080" or "[::1]:52698"; wildcard UDP entries ("*:*", no
// fixed port) are skipped since they aren't meaningful for diffing.
func parseLsofLines(out []byte, proto string) []PortEntry {
	var entries []PortEntry
	lines := strings.Split(string(out), "\n")
	for i, line := range lines {
		if i == 0 || strings.TrimSpace(line) == "" {
			continue // header row or trailing blank
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		cmd := fields[0]
		pid, err := strconv.Atoi(fields[1])
		if err != nil {
			continue
		}
		name := fields[len(fields)-1]
		if name == "(LISTEN)" && len(fields) >= 2 {
			name = fields[len(fields)-2]
		}
		m := lsofPortRe.FindStringSubmatch(name)
		if m == nil {
			continue
		}
		port, err := strconv.Atoi(m[1])
		if err != nil {
			continue
		}
		entries = append(entries, PortEntry{Proto: proto, Port: port, Process: cmd, PID: pid})
	}
	return dedupePorts(entries)
}

var lsofPortRe = regexp.MustCompile(`:(\d+)$`)

// parseSSLines parses `ss -ltnp`/`ss -lunp` output. Local address is column
// 4 (0-indexed), e.g. "0.0.0.0:8080" or "[::]:8080"; the process comes from
// the trailing users:(("name",pid=1234,fd=3)) column when -p succeeded
// (requires root for some processes — those rows just have no process name).
func parseSSLines(out []byte, proto string) []PortEntry {
	var entries []PortEntry
	lines := strings.Split(string(out), "\n")
	for i, line := range lines {
		if i == 0 || strings.TrimSpace(line) == "" {
			continue // header row or trailing blank
		}
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		localAddr := fields[3]
		m := lsofPortRe.FindStringSubmatch(localAddr)
		if m == nil {
			continue
		}
		port, err := strconv.Atoi(m[1])
		if err != nil {
			continue
		}
		proc, pid := "", 0
		if pm := ssProcRe.FindStringSubmatch(line); pm != nil {
			proc = pm[1]
			pid, _ = strconv.Atoi(pm[2])
		}
		entries = append(entries, PortEntry{Proto: proto, Port: port, Process: proc, PID: pid})
	}
	return dedupePorts(entries)
}

var ssProcRe = regexp.MustCompile(`\(\("([^"]+)",pid=(\d+)`)

// dedupePorts collapses IPv4/IPv6 duplicates of the same service (lsof/ss
// both list a dual-stack listener as two rows) into one entry per
// proto+port+process.
func dedupePorts(entries []PortEntry) []PortEntry {
	seen := make(map[string]bool)
	out := make([]PortEntry, 0, len(entries))
	for _, e := range entries {
		key := e.Proto + ":" + strconv.Itoa(e.Port) + ":" + e.Process
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, e)
	}
	return out
}

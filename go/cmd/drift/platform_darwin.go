//go:build darwin

package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

func collectPorts() []PortEntry {
	if _, err := exec.LookPath("lsof"); err != nil {
		return nil
	}
	var entries []PortEntry
	if out, err := exec.Command("lsof", "-nP", "-iTCP", "-sTCP:LISTEN").Output(); err == nil {
		entries = append(entries, parseLsofLines(out, "tcp")...)
	}
	if out, err := exec.Command("lsof", "-nP", "-iUDP").Output(); err == nil {
		entries = append(entries, parseLsofLines(out, "udp")...)
	}
	return entries
}

// collectAgents reads the per-user LaunchAgents directory — filenames are a
// stable identity to diff against, unlike `launchctl list`'s live PID/status
// output which changes on every run regardless of what actually changed.
func collectAgents() []string {
	dir := filepath.Join(os.Getenv("HOME"), "Library", "LaunchAgents")
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var agents []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".plist") {
			agents = append(agents, strings.TrimSuffix(e.Name(), ".plist"))
		}
	}
	sort.Strings(agents)
	return agents
}

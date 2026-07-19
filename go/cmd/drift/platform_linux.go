//go:build linux

package main

import (
	"os/exec"
	"sort"
	"strings"
)

// collectPorts uses `ss` (part of iproute2, present on essentially every
// modern distro). Hand-rolled /proc/net/tcp parsing plus inode-to-process
// matching would avoid the dependency but is meaningfully more code for
// marginal gain on a minimal-install edge case — deferred to v2 if it turns
// out `ss` is ever actually missing on the Pi.
func collectPorts() []PortEntry {
	if _, err := exec.LookPath("ss"); err != nil {
		return nil
	}
	var entries []PortEntry
	if out, err := exec.Command("ss", "-ltnp").Output(); err == nil {
		entries = append(entries, parseSSLines(out, "tcp")...)
	}
	if out, err := exec.Command("ss", "-lunp").Output(); err == nil {
		entries = append(entries, parseSSLines(out, "udp")...)
	}
	return entries
}

// collectAgents lists the current user's enabled systemd units — the
// closest Linux analogue to "what starts automatically for this user",
// scoped to --user so it works without root.
func collectAgents() []string {
	if _, err := exec.LookPath("systemctl"); err != nil {
		return nil
	}
	out, err := exec.Command("systemctl", "--user", "list-unit-files", "--type=service", "--state=enabled", "--no-legend").Output()
	if err != nil {
		return nil
	}
	var agents []string
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) > 0 {
			agents = append(agents, fields[0])
		}
	}
	sort.Strings(agents)
	return agents
}

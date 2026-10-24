//go:build linux

package main

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// totalMemory returns physical RAM in bytes, parsed from /proc/meminfo's
// MemTotal line (reported in kB).
func totalMemory() (uint64, error) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "MemTotal:") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			return 0, fmt.Errorf("unexpected MemTotal line: %q", line)
		}
		kb, err := strconv.ParseUint(fields[1], 10, 64)
		if err != nil {
			return 0, err
		}
		return kb * 1024, nil
	}
	if err := scanner.Err(); err != nil {
		return 0, err
	}
	return 0, fmt.Errorf("MemTotal not found in /proc/meminfo")
}

// applyFootprint adds each process's swapped-out memory (VmSwap) to its
// RSS, so a process the kernel has pushed to swap still ranks by what it
// really holds. Unreadable /proc entries (other users, exited) keep RSS.
func applyFootprint(procs []proc) {
	for i := range procs {
		data, err := os.ReadFile(fmt.Sprintf("/proc/%d/status", procs[i].pid))
		if err != nil {
			continue
		}
		procs[i].rss += parseVmSwap(string(data))
	}
}

func parseVmSwap(status string) uint64 {
	for _, line := range strings.Split(status, "\n") {
		if !strings.HasPrefix(line, "VmSwap:") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			return 0
		}
		kb, _ := strconv.ParseUint(fields[1], 10, 64)
		return kb * 1024
	}
	return 0
}

//go:build linux

package main

import (
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

// currentBoot derives the live run from /proc/uptime, which is exact and
// needs no privileges — the same source sysreboot reads.
func currentBoot() (Boot, error) {
	data, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return Boot{}, err
	}
	fields := strings.Fields(string(data))
	if len(fields) == 0 {
		return Boot{}, io.ErrUnexpectedEOF
	}
	secs, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return Boot{}, err
	}

	uptime := time.Duration(secs * float64(time.Second))
	return Boot{
		Boot:    time.Now().Add(-uptime),
		Uptime:  uptime,
		Current: true,
		System:  systemString(),
		Source:  "live",
	}, nil
}

// systemString matches the "Linux 6.1.0-rpi7-rpi-v8" form uptimed
// stores. Read from /proc rather than uname(2) so there is no libc
// struct layout to get right per architecture.
func systemString() string {
	ostype := strings.TrimSpace(readProcString("/proc/sys/kernel/ostype"))
	release := strings.TrimSpace(readProcString("/proc/sys/kernel/osrelease"))
	switch {
	case ostype == "":
		return release
	case release == "":
		return ostype
	}
	return ostype + " " + release
}

func readProcString(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(data)
}

// wtmpPaths returns the current login database plus whatever rotated
// generations are still on disk. Servers commonly rotate wtmp monthly,
// so the older files are where any long-running history actually lives.
func wtmpPaths() []string {
	if p := os.Getenv("UPREC_WTMP"); p != "" {
		return strings.Split(p, ":")
	}
	matches, err := filepath.Glob("/var/log/wtmp*")
	if err != nil {
		return []string{"/var/log/wtmp"}
	}
	sort.Strings(matches)
	return matches
}

// bootEvents reads both login databases. Which one holds the boot
// records depends on the distribution and its age — Debian 13 moved them
// from wtmp to wtmpdb, and a machine mid-migration has wtmp full of
// sessions and wtmpdb full of boots — so ask both and let the merge sort
// out any overlap. A source that is absent or unreadable is skipped
// rather than failing the run: partial history beats none.
func bootEvents() ([]event, error) {
	var events []event
	for _, path := range wtmpPaths() {
		found, err := readWtmp(path)
		if err != nil {
			continue
		}
		events = append(events, found...)
	}
	return append(events, wtmpdbEvents()...), nil
}

// wtmpdbEvents shells out to wtmpdb's read subcommand. A missing tool or
// database is the normal case on a machine that never migrated, so every
// failure here is silent.
func wtmpdbEvents() []event {
	out, err := exec.Command(wtmpdbCommand, wtmpdbArgs(os.Getenv("UPREC_WTMPDB"))...).Output()
	if err != nil {
		return nil
	}
	events, err := parseWtmpdbJSON(out)
	if err != nil {
		return nil
	}
	return events
}

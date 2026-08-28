//go:build darwin

package main

import (
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"

	"golang.org/x/sys/unix"
)

// currentBoot reads kern.boottime, the same authoritative source
// sysreboot uses, so the run in progress is exact to the second.
func currentBoot() (Boot, error) {
	tv, err := unix.SysctlTimeval("kern.boottime")
	if err != nil {
		return Boot{}, err
	}
	sec, _ := tv.Unix()
	booted := time.Unix(sec, 0)
	return Boot{
		Boot:    booted,
		Uptime:  time.Since(booted),
		Current: true,
		System:  systemString(),
		Source:  "live",
	}, nil
}

// systemString matches the "Darwin 25.6.0" form uptimed stores, so
// records written here and by the daemon stay interchangeable.
func systemString() string {
	ostype, err := unix.Sysctl("kern.ostype")
	if err != nil {
		return ""
	}
	release, err := unix.Sysctl("kern.osrelease")
	if err != nil {
		return ostype
	}
	return ostype + " " + release
}

// bootEvents shells out to last(1). Unlike Linux there is no flat utmpx
// file to decode: macOS keeps its login database inside the ASL store,
// and last is the only supported reader of it.
func bootEvents() ([]event, error) {
	out, err := exec.Command("last", "reboot", "shutdown").Output()
	if err != nil {
		return nil, err
	}
	return parseLastOutput(string(out), time.Now()), nil
}

// A date in last(1) output, in either field order macOS has used
// ("Wed 19 Aug 18:10" and "Wed Aug 19 18:10"), with the year and seconds
// both optional so a GNU-style `last -F` line parses too.
var lastDatePattern = regexp.MustCompile(
	`(?:(\d{1,2})\s+([A-Z][a-z]{2})|([A-Z][a-z]{2})\s+(\d{1,2}))` +
		`\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s+(\d{4}))?`)

var monthNames = map[string]time.Month{
	"Jan": time.January, "Feb": time.February, "Mar": time.March,
	"Apr": time.April, "May": time.May, "Jun": time.June,
	"Jul": time.July, "Aug": time.August, "Sep": time.September,
	"Oct": time.October, "Nov": time.November, "Dec": time.December,
}

// parseLastOutput turns last(1) output into events.
//
// macOS omits the year, so it is inferred from position instead: last
// prints newest first, so each record must fall at or before the one
// above it. Walking down the output and rolling the year back whenever a
// date jumps forward keeps multi-year logs correct, where comparing each
// date against today alone would not.
func parseLastOutput(out string, now time.Time) []event {
	newer := now.Add(time.Minute) // slack for clock skew on the first record

	var events []event
	for _, line := range strings.Split(out, "\n") {
		var kind eventKind
		switch {
		case strings.HasPrefix(line, "reboot"):
			kind = eventBoot
		case strings.HasPrefix(line, "shutdown"):
			kind = eventShutdown
		default:
			continue
		}

		matches := lastDatePattern.FindAllStringSubmatch(line, -1)
		if len(matches) == 0 {
			continue
		}
		// The trailing match is the timestamp; anything earlier in the
		// line is a tty or host name that happened to look like a date.
		t, ok := parseLastDate(matches[len(matches)-1], newer)
		if !ok {
			continue
		}
		events = append(events, event{When: t, Kind: kind})
		newer = t
	}
	return events
}

func parseLastDate(m []string, newer time.Time) (time.Time, bool) {
	dayStr, monStr := m[1], m[2]
	if dayStr == "" {
		monStr, dayStr = m[3], m[4]
	}
	month, ok := monthNames[monStr]
	if !ok {
		return time.Time{}, false
	}
	day, err := strconv.Atoi(dayStr)
	if err != nil {
		return time.Time{}, false
	}
	hour, err := strconv.Atoi(m[5])
	if err != nil {
		return time.Time{}, false
	}
	minute, err := strconv.Atoi(m[6])
	if err != nil {
		return time.Time{}, false
	}
	second := 0
	if m[7] != "" {
		second, _ = strconv.Atoi(m[7])
	}

	if m[8] != "" {
		year, err := strconv.Atoi(m[8])
		if err != nil {
			return time.Time{}, false
		}
		return time.Date(year, month, day, hour, minute, second, 0, time.Local), true
	}

	t := time.Date(newer.Year(), month, day, hour, minute, second, 0, time.Local)
	if t.After(newer) {
		t = t.AddDate(-1, 0, 0)
	}
	return t, true
}

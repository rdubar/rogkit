//go:build darwin

package main

import (
	"testing"
	"time"
)

// Real `last reboot shutdown` output: no year, newest first.
const lastFixture = `reboot    time                                Wed 19 Aug 18:10
shutdown  time                                Wed 19 Aug 18:06
reboot    time                                Fri  7 Aug 20:33
shutdown  time                                Fri  7 Aug 20:29
reboot    time                                Wed  5 Aug 08:14

wtmp begins Sun 28 Jun 2026 22:31:47 BST
`

func TestParseLastOutput(t *testing.T) {
	now := at("2026-08-28 19:37:00")
	events := parseLastOutput(lastFixture, now)

	if len(events) != 5 {
		t.Fatalf("got %d events, want 5: %+v", len(events), events)
	}
	if events[0].Kind != eventBoot || !events[0].When.Equal(at("2026-08-19 18:10:00")) {
		t.Errorf("first event = %+v, want the 19 Aug reboot", events[0])
	}
	if events[1].Kind != eventShutdown || !events[1].When.Equal(at("2026-08-19 18:06:00")) {
		t.Errorf("second event = %+v, want the 19 Aug shutdown", events[1])
	}
	if !events[4].When.Equal(at("2026-08-05 08:14:00")) {
		t.Errorf("last event = %v, want 5 Aug 08:14", events[4].When)
	}
}

// last(1) omits the year, so a log spanning New Year has to be dated by
// position: each record falls at or before the one above it.
func TestParseLastOutputRollsYearBack(t *testing.T) {
	now := at("2026-01-15 12:00:00")
	out := `reboot    time                                Thu 10 Jan 09:00
shutdown  time                                Wed 24 Dec 22:00
reboot    time                                Mon 15 Dec 08:00
shutdown  time                                Sat 30 Nov 19:00
`
	events := parseLastOutput(out, now)
	if len(events) != 4 {
		t.Fatalf("got %d events, want 4", len(events))
	}

	want := []time.Time{
		at("2026-01-10 09:00:00"),
		at("2025-12-24 22:00:00"),
		at("2025-12-15 08:00:00"),
		at("2025-11-30 19:00:00"),
	}
	for i, w := range want {
		if !events[i].When.Equal(w) {
			t.Errorf("event %d = %v, want %v", i, events[i].When, w)
		}
	}
}

// Some macOS releases print the month before the day.
func TestParseLastOutputAcceptsMonthFirst(t *testing.T) {
	now := at("2026-08-28 19:37:00")
	events := parseLastOutput("reboot    time    Wed Aug 19 18:10\n", now)

	if len(events) != 1 {
		t.Fatalf("got %d events, want 1", len(events))
	}
	if !events[0].When.Equal(at("2026-08-19 18:10:00")) {
		t.Errorf("got %v, want 19 Aug 18:10", events[0].When)
	}
}

// A `last -F` style line carries its own year, which must be trusted
// over the inferred one.
func TestParseLastOutputUsesExplicitYear(t *testing.T) {
	now := at("2026-08-28 19:37:00")
	events := parseLastOutput("reboot   system boot  Mon Aug 19 18:10:04 2024\n", now)

	if len(events) != 1 {
		t.Fatalf("got %d events, want 1", len(events))
	}
	if !events[0].When.Equal(at("2024-08-19 18:10:04")) {
		t.Errorf("got %v, want the explicit 2024 date", events[0].When)
	}
}

func TestParseLastOutputIgnoresOtherLines(t *testing.T) {
	now := at("2026-08-28 19:37:00")
	out := "rdubar   ttys002    Wed 19 Aug 18:20\nwtmp begins Sun 28 Jun 2026 22:31:47 BST\n\n"

	if events := parseLastOutput(out, now); len(events) != 0 {
		t.Errorf("got %+v, want no events from login and footer lines", events)
	}
}

func TestCurrentBootIsPlausible(t *testing.T) {
	b, err := currentBoot()
	if err != nil {
		t.Fatalf("currentBoot: %v", err)
	}
	if !b.Current || b.Source != "live" {
		t.Errorf("got %+v, want the live current run", b)
	}
	if b.Uptime <= 0 || b.Uptime > 10*365*24*time.Hour {
		t.Errorf("uptime = %v, outside any plausible range", b.Uptime)
	}
	if b.System == "" {
		t.Error("system string should be populated from sysctl")
	}
}

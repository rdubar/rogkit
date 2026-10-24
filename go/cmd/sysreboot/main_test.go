package main

import (
	"strings"
	"testing"
)

func TestRebootScoreAndExitCode(t *testing.T) {
	stats := &Stats{
		UptimeSeconds: 40 * 86400,
		Load1:         10,
		Load5:         12,
		Cores:         4,
		MemTotal:      100,
		MemAvailable:  5,
		SwapTotal:     100,
		SwapUsed:      40,
	}

	score := rebootScore(stats)
	if score != 85 {
		t.Fatalf("expected score 85, got %d", score)
	}
	if got := exitCode(score, false); got != 2 {
		t.Fatalf("expected exit code 2, got %d", got)
	}
}

func TestVerdictLocaleFallback(t *testing.T) {
	t.Setenv("LC_ALL", "C")
	t.Setenv("LC_CTYPE", "")
	t.Setenv("LANG", "")

	emoji, label := verdict(10, false)
	if emoji != "[OK]" {
		t.Fatalf("expected ASCII ok marker, got %q", emoji)
	}
	if label != "No reboot needed" {
		t.Fatalf("unexpected label %q", label)
	}

	emoji, label = verdict(10, true)
	if emoji != "[X]" || label != "REBOOT REQUIRED" {
		t.Fatalf("unexpected reboot verdict: %q %q", emoji, label)
	}
}

func TestUtf8Locale(t *testing.T) {
	t.Setenv("LC_ALL", "")
	t.Setenv("LC_CTYPE", "")
	t.Setenv("LANG", "en_US.UTF-8")

	if !utf8Locale() {
		t.Fatal("expected UTF-8 locale detection to succeed")
	}
}

func TestFormatDuration(t *testing.T) {
	if got := formatDuration(0); got != "0m" {
		t.Fatalf("expected 0m, got %q", got)
	}
	if got := formatDuration(65 * 60); got != "1h 5m" {
		t.Fatalf("expected 1h 5m, got %q", got)
	}
	if got := formatDuration(27 * 3600); got != "1d 3h" {
		t.Fatalf("expected 1d 3h, got %q", got)
	}
}

func TestSwapAgainstRAMDrivesVerdict(t *testing.T) {
	const gb = 1024 * 1024 * 1024
	// Freshly rebooted 8 GB Mac with 6 GB swapped: the case that froze on
	// open while the old swap-total ratio stayed quiet.
	stats := &Stats{UptimeSeconds: 3600, Cores: 6, Load1: 2, MemTotal: 8 * gb, MemAvailable: 1600 * 1024 * 1024, SwapTotal: 7 * gb, SwapUsed: 6 * gb}
	score := rebootScore(stats)
	if score < 70 {
		t.Fatalf("expected 6 GB swap on 8 GB RAM to advise a reboot, got score %d", score)
	}
	warnings := memWarnings(stats)
	if len(warnings) == 0 || !strings.Contains(warnings[0], "expect freezes") {
		t.Fatalf("expected a freeze warning, got %q", warnings)
	}
}

func TestMemWarnings(t *testing.T) {
	const gb = 1024 * 1024 * 1024
	healthy := &Stats{MemTotal: 8 * gb, MemAvailable: 4 * gb, SwapUsed: 512 * 1024 * 1024}
	if w := memWarnings(healthy); len(w) != 0 {
		t.Fatalf("expected no warnings for healthy memory, got %q", w)
	}

	tight := &Stats{MemTotal: 8 * gb, MemAvailable: 2 * gb, SwapUsed: 3 * gb, Pressure: "warn"}
	w := memWarnings(tight)
	if len(w) != 2 || !strings.Contains(w[0], "pressure") || !strings.Contains(w[1], "getting tight") {
		t.Fatalf("unexpected warnings %q", w)
	}
}

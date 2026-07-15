package main

import (
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
	if score != 80 {
		t.Fatalf("expected score 80, got %d", score)
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

package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestByteSize(t *testing.T) {
	cases := map[uint64]string{
		0:             "0 bytes",
		1:             "1 byte",
		2:             "2 bytes",
		999:           "999 bytes",
		1000:          "1.00 KB",
		1023:          "1.02 KB",
		1234567890:    "1.23 GB",
		1234567890123: "1.23 TB",
	}
	for in, want := range cases {
		if got := byteSize(in); got != want {
			t.Errorf("byteSize(%d) = %q, want %q", in, got, want)
		}
	}
}

func TestCommaFloat(t *testing.T) {
	cases := []struct {
		f    float64
		want string
	}{
		{1.5, "1.50"},
		{1234.567, "1,234.57"},
		{1234567.891, "1,234,567.89"},
		{-1234.5, "-1,234.50"},
	}
	for _, c := range cases {
		if got := commaFloat(c.f, 2); got != c.want {
			t.Errorf("commaFloat(%v) = %q, want %q", c.f, got, c.want)
		}
	}
}

func TestPercentOf(t *testing.T) {
	if got := percentOf(50, 100); got != 50 {
		t.Fatalf("expected 50, got %v", got)
	}
	if got := percentOf(1, 0); got != 0 {
		t.Fatalf("expected 0 for zero total, got %v", got)
	}
}

func TestDedupeByDevice(t *testing.T) {
	rows := []row{
		{path: "/a", dev: 1},
		{path: "/b", dev: 2},
		{path: "/c", dev: 1}, // same device as /a, should be dropped
	}
	out := dedupeByDevice(rows)
	if len(out) != 2 {
		t.Fatalf("expected 2 rows after dedupe, got %d: %v", len(out), out)
	}
	if out[0].path != "/a" || out[1].path != "/b" {
		t.Fatalf("expected first-seen order [/a /b], got %v", out)
	}
}

func TestResolvePathsExplicit(t *testing.T) {
	dir := t.TempDir()
	got := resolvePaths([]string{dir})
	if len(got) != 1 || got[0] != dir {
		t.Fatalf("expected [%s], got %v", dir, got)
	}
}

func TestResolvePathsDefaultFallsBackToRoot(t *testing.T) {
	// No /mnt on most dev/test machines, no args: should fall back to "/".
	got := resolvePaths(nil)
	found := false
	for _, p := range got {
		if p == "/" {
			found = true
		}
	}
	if !found {
		t.Fatalf("expected fallback to include \"/\", got %v", got)
	}
}

func TestResolvePathsSubstringMatch(t *testing.T) {
	mnt := t.TempDir()
	sub := filepath.Join(mnt, "media1")
	if err := os.Mkdir(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	got := resolvePathsFrom(mnt, []string{"media1"})
	if len(got) != 1 || got[0] != sub {
		t.Fatalf("expected [%s], got %v", sub, got)
	}
}

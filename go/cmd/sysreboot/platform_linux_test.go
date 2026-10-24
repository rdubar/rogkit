//go:build linux

package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadRebootMarkerPath(t *testing.T) {
	dir := t.TempDir()
	marker := filepath.Join(dir, "reboot-required")
	if err := os.WriteFile(marker, []byte(""), 0o600); err != nil {
		t.Fatalf("write marker: %v", err)
	}

	got, ok := readRebootMarkerPath([]string{filepath.Join(dir, "missing"), marker})
	if !ok {
		t.Fatal("expected to find marker")
	}
	if got != marker {
		t.Fatalf("expected %q, got %q", marker, got)
	}
}

func TestReadRebootRequiredPkgs(t *testing.T) {
	dir := t.TempDir()
	marker := filepath.Join(dir, "reboot-required")
	pkgsPath := marker + ".pkgs"
	content := "kernel-a kernel-b kernel-c kernel-d\n"
	if err := os.WriteFile(pkgsPath, []byte(content), 0o600); err != nil {
		t.Fatalf("write pkgs: %v", err)
	}

	t.Run("ascii", func(t *testing.T) {
		t.Setenv("LC_ALL", "C")
		t.Setenv("LC_CTYPE", "")
		t.Setenv("LANG", "")
		if got := readRebootRequiredPkgs(marker); got != "kernel-a, kernel-b, kernel-c, ..." {
			t.Fatalf("unexpected ASCII truncation: %q", got)
		}
	})

	t.Run("utf8", func(t *testing.T) {
		t.Setenv("LC_ALL", "")
		t.Setenv("LC_CTYPE", "")
		t.Setenv("LANG", "en_US.UTF-8")
		if got := readRebootRequiredPkgs(marker); got != "kernel-a, kernel-b, kernel-c, …" {
			t.Fatalf("unexpected UTF-8 truncation: %q", got)
		}
	})
}

func TestEstimateMemAvailable(t *testing.T) {
	values := map[string]uint64{
		"MemFree":      100,
		"Buffers":      50,
		"Cached":       200,
		"SReclaimable": 25,
		"Shmem":        75,
	}

	if got := estimateMemAvailable(values); got != 300 {
		t.Fatalf("expected 300, got %d", got)
	}
}

func TestParsePSI(t *testing.T) {
	cases := map[string]string{
		"some avg10=0.00 avg60=0.00 avg300=0.00 total=0\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n":      "normal",
		"some avg10=30.00 avg60=12.50 avg300=4.00 total=1\nfull avg10=5.00 avg60=3.00 avg300=1.00 total=1\n":    "warn",
		"some avg10=80.00 avg60=60.00 avg300=20.00 total=1\nfull avg10=40.00 avg60=25.00 avg300=9.00 total=1\n": "critical",
	}
	for in, want := range cases {
		if got := parsePSI(in); got != want {
			t.Errorf("parsePSI(%q) = %q, want %q", in, got, want)
		}
	}
}

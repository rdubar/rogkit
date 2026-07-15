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

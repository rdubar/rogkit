//go:build linux

package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestIsRaspberryPi(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "model")
	writeModel(t, path, "Raspberry Pi 5 Model B Rev 1.0\x00")
	if !isRaspberryPi(path) {
		t.Fatal("expected Raspberry Pi model string to be detected")
	}
}

func TestIsRaspberryPiFalseForOtherHardware(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "model")
	writeModel(t, path, "Some Other Board\x00")
	if isRaspberryPi(path) {
		t.Fatal("expected non-Pi model string to not match")
	}
}

func TestIsRaspberryPiFalseWhenMissing(t *testing.T) {
	if isRaspberryPi(filepath.Join(t.TempDir(), "missing")) {
		t.Fatal("expected missing model file to not match")
	}
}

func writeModel(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write model file: %v", err)
	}
}

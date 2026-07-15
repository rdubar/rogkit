//go:build darwin

package main

import "testing"

func TestStatfsRoot(t *testing.T) {
	st, err := statfs("/")
	if err != nil {
		t.Fatalf("statfs(/): %v", err)
	}
	if st.total == 0 {
		t.Fatal("expected non-zero total space for /")
	}
	if st.free > st.total {
		t.Fatalf("free (%d) exceeds total (%d)", st.free, st.total)
	}
	if st.dev == 0 {
		t.Fatal("expected non-zero device id for /")
	}
}

func TestStatfsMissingPath(t *testing.T) {
	if _, err := statfs("/no/such/path/hopefully"); err == nil {
		t.Fatal("expected error for missing path")
	}
}

func TestStatfsDedupeAcrossFirmlink(t *testing.T) {
	root, err := statfs("/")
	if err != nil {
		t.Fatalf("statfs(/): %v", err)
	}
	data, err := statfs("/System/Volumes/Data")
	if err != nil {
		t.Skip("no /System/Volumes/Data on this system")
	}
	if root.dev != data.dev {
		t.Fatalf("expected / and /System/Volumes/Data to share a device, got %d vs %d", root.dev, data.dev)
	}
}

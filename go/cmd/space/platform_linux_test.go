//go:build linux

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
	if st.avail > st.free {
		t.Fatalf("avail (%d) exceeds free (%d)", st.avail, st.free)
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

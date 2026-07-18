package main

import "testing"

func TestByteSize(t *testing.T) {
	cases := map[uint64]string{
		0:          "0 bytes",
		1:          "1 byte",
		999:        "999 bytes",
		1000:       "1.00 KB",
		1234567:    "1.23 MB",
		1234567890: "1.23 GB",
	}
	for in, want := range cases {
		if got := byteSize(in); got != want {
			t.Errorf("byteSize(%d) = %q, want %q", in, got, want)
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

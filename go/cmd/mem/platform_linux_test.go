//go:build linux

package main

import "testing"

func TestParseVmSwap(t *testing.T) {
	status := "Name:\tchrome\nVmRSS:\t  204800 kB\nVmSwap:\t  102400 kB\nThreads:\t12\n"
	if got := parseVmSwap(status); got != 102400*1024 {
		t.Fatalf("parseVmSwap = %d, want %d", got, 102400*1024)
	}
	if got := parseVmSwap("Name:\tkthreadd\n"); got != 0 {
		t.Fatalf("expected 0 for a kernel thread with no VmSwap, got %d", got)
	}
}

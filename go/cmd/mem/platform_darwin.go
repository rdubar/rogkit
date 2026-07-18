//go:build darwin

package main

import "golang.org/x/sys/unix"

// totalMemory returns physical RAM in bytes via the hw.memsize sysctl.
func totalMemory() (uint64, error) {
	return unix.SysctlUint64("hw.memsize")
}

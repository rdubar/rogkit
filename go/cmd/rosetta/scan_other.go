//go:build !darwin

package main

import "fmt"

// scan is a stub for every platform besides macOS: Rosetta 2 only exists on
// Apple Silicon Macs, so there is nothing to detect here. main() prints the
// one-line "unsupported platform" message and exits before ever calling
// this, but the package still needs to build and this keeps behavior
// well-defined if that ever changes.
func scan() ([]app, error) {
	return nil, fmt.Errorf("rosetta: unsupported platform")
}

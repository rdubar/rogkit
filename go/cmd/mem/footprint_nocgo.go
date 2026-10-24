//go:build darwin && !cgo

package main

// applyFootprint needs libproc via cgo; without it mem falls back to RSS.
func applyFootprint(procs []proc) {}

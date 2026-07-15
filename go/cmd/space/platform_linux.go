//go:build linux

package main

import (
	"os"
	"syscall"

	"golang.org/x/sys/unix"
)

type mountStats struct {
	total uint64
	free  uint64
	dev   uint64
}

// statfs reads total/free space in the same units os.statvfs() reports:
// block counts scaled by f_frsize (the fragment size), not f_bsize — Linux
// statfs(2) exposes both separately, and they can differ, so Frsize is the
// one that matches Python's os.statvfs().f_frsize semantics.
//
// dev comes from stat(2), not statfs's Fsid: Fsid can differ between two
// mounts that share the same underlying device (e.g. macOS APFS firmlinks),
// where Python's dedupe key (os.stat().st_dev) does not.
func statfs(path string) (mountStats, error) {
	var st unix.Statfs_t
	if err := unix.Statfs(path, &st); err != nil {
		return mountStats{}, err
	}
	dev, err := deviceID(path)
	if err != nil {
		return mountStats{}, err
	}
	unit := uint64(st.Frsize)
	return mountStats{
		total: st.Blocks * unit,
		free:  st.Bfree * unit,
		dev:   dev,
	}, nil
}

func deviceID(path string) (uint64, error) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, err
	}
	st, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return 0, nil
	}
	return uint64(st.Dev), nil
}

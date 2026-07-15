//go:build darwin

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

// statfs reads total/free space scaled by Bsize — Darwin's statfs(2) has
// no separate frsize field, and block size doubles as fragment size on
// BSD-derived filesystems, matching os.statvfs()'s f_frsize on macOS.
//
// dev comes from stat(2), not statfs's Fsid: on macOS, "/" and
// "/System/Volumes/Data" report different Fsid values despite sharing one
// APFS container and one st_dev — Fsid would wrongly keep both as
// distinct rows where Python's dedupe key (os.stat().st_dev) collapses
// them into one.
func statfs(path string) (mountStats, error) {
	var st unix.Statfs_t
	if err := unix.Statfs(path, &st); err != nil {
		return mountStats{}, err
	}
	dev, err := deviceID(path)
	if err != nil {
		return mountStats{}, err
	}
	unit := uint64(st.Bsize)
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

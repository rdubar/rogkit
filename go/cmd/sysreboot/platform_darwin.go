//go:build darwin

package main

import (
	"encoding/binary"
	"os/exec"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"

	"golang.org/x/sys/unix"
)

// gather uses direct sysctls where the value is a plain scalar (fast,
// no subprocess, no struct-layout guessing) and falls back to the
// system's own small utilities (sysctl, vm_stat) for values that come
// back as structs or formatted text — trading a few milliseconds of
// subprocess overhead for not hand-decoding kernel struct layouts we'd
// have to re-verify on every macOS release.
func gather() (*Stats, error) {
	s := &Stats{Cores: runtime.NumCPU()}

	if uptime, err := readUptimeSysctl(); err == nil {
		s.UptimeSeconds = uptime
	}
	if l1, l5, l15, err := readLoadAvg(); err == nil {
		s.Load1, s.Load5, s.Load15 = l1, l5, l15
	}
	if total, err := unix.SysctlUint64("hw.memsize"); err == nil {
		s.MemTotal = total
	}
	readVMStat(s)
	readSwapUsage(s)

	return s, nil
}

// kern.boottime is a struct timeval; we only need the leading 8-byte
// tv_sec field, so read the raw bytes rather than modeling the full
// (padded) struct.
func readUptimeSysctl() (float64, error) {
	raw, err := unix.SysctlRaw("kern.boottime")
	if err != nil || len(raw) < 8 {
		return 0, err
	}
	bootSec := int64(binary.LittleEndian.Uint64(raw[:8]))
	return float64(time.Now().Unix() - bootSec), nil
}

var loadAvgPattern = regexp.MustCompile(`\{\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\}`)

func readLoadAvg() (l1, l5, l15 float64, err error) {
	out, err := exec.Command("sysctl", "-n", "vm.loadavg").Output()
	if err != nil {
		return 0, 0, 0, err
	}
	m := loadAvgPattern.FindStringSubmatch(string(out))
	if m == nil {
		return 0, 0, 0, nil
	}
	l1, _ = strconv.ParseFloat(m[1], 64)
	l5, _ = strconv.ParseFloat(m[2], 64)
	l15, _ = strconv.ParseFloat(m[3], 64)
	return l1, l5, l15, nil
}

var (
	pageSizePattern   = regexp.MustCompile(`page size of (\d+) bytes`)
	vmStatLinePattern = regexp.MustCompile(`^(Pages [a-z ]+):\s+(\d+)\.?$`)
)

// readVMStat approximates "available" memory as free+inactive pages —
// macOS caches aggressively, so raw free pages alone badly understates
// what's actually reclaimable. This is a heuristic, not an exact figure.
func readVMStat(s *Stats) {
	out, err := exec.Command("vm_stat").Output()
	if err != nil {
		return
	}
	text := string(out)

	pageSize := uint64(4096)
	if m := pageSizePattern.FindStringSubmatch(text); m != nil {
		if v, err := strconv.ParseUint(m[1], 10, 64); err == nil {
			pageSize = v
		}
	}

	pages := map[string]uint64{}
	for _, line := range strings.Split(text, "\n") {
		if m := vmStatLinePattern.FindStringSubmatch(strings.TrimSpace(line)); m != nil {
			if v, err := strconv.ParseUint(m[2], 10, 64); err == nil {
				pages[m[1]] = v
			}
		}
	}

	s.MemAvailable = (pages["Pages free"] + pages["Pages inactive"]) * pageSize
}

var swapUsagePattern = regexp.MustCompile(`total = ([\d.]+)M\s+used = ([\d.]+)M`)

func readSwapUsage(s *Stats) {
	out, err := exec.Command("sysctl", "-n", "vm.swapusage").Output()
	if err != nil {
		return
	}
	m := swapUsagePattern.FindStringSubmatch(string(out))
	if m == nil {
		return
	}
	total, _ := strconv.ParseFloat(m[1], 64)
	used, _ := strconv.ParseFloat(m[2], 64)
	s.SwapTotal = uint64(total * 1024 * 1024)
	s.SwapUsed = uint64(used * 1024 * 1024)
}

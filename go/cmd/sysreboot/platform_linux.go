//go:build linux

package main

import (
	"bufio"
	"os"
	"runtime"
	"strconv"
	"strings"
)

// gather reads /proc directly — no subprocess, no heuristics needed for
// the headline signal, since Debian/Ubuntu/Raspberry Pi OS already write
// an authoritative marker when a reboot is required.
func gather() (*Stats, error) {
	s := &Stats{Cores: runtime.NumCPU()}

	if uptime, err := readUptime(); err == nil {
		s.UptimeSeconds = uptime
	}
	if l1, l5, l15, err := readLoadAvg(); err == nil {
		s.Load1, s.Load5, s.Load15 = l1, l5, l15
	}
	readMemInfo(s)

	if markerPath, ok := readRebootMarkerPath([]string{
		"/run/reboot-required",
		"/var/run/reboot-required",
	}); ok {
		s.RebootRequired = true
		s.RebootReason = "pending kernel/library update"
		if pkgs := readRebootRequiredPkgs(markerPath); pkgs != "" {
			s.RebootReason += " (" + pkgs + ")"
		}
	}

	return s, nil
}

func readUptime() (float64, error) {
	data, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return 0, err
	}
	fields := strings.Fields(string(data))
	if len(fields) == 0 {
		return 0, nil
	}
	return strconv.ParseFloat(fields[0], 64)
}

func readLoadAvg() (l1, l5, l15 float64, err error) {
	data, err := os.ReadFile("/proc/loadavg")
	if err != nil {
		return 0, 0, 0, err
	}
	fields := strings.Fields(string(data))
	if len(fields) < 3 {
		return 0, 0, 0, nil
	}
	l1, _ = strconv.ParseFloat(fields[0], 64)
	l5, _ = strconv.ParseFloat(fields[1], 64)
	l15, _ = strconv.ParseFloat(fields[2], 64)
	return l1, l5, l15, nil
}

func readMemInfo(s *Stats) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return
	}
	defer f.Close()

	values := map[string]uint64{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		colon := strings.IndexByte(line, ':')
		if colon < 0 {
			continue
		}
		key := line[:colon]
		fields := strings.Fields(line[colon+1:])
		if len(fields) == 0 {
			continue
		}
		kb, err := strconv.ParseUint(fields[0], 10, 64)
		if err != nil {
			continue
		}
		values[key] = kb * 1024 // /proc/meminfo is in kB
	}

	s.MemTotal = values["MemTotal"]
	s.MemAvailable = values["MemAvailable"]
	if s.MemAvailable == 0 {
		s.MemAvailable = estimateMemAvailable(values)
	}
	s.SwapTotal = values["SwapTotal"]
	swapFree := values["SwapFree"]
	if s.SwapTotal > swapFree {
		s.SwapUsed = s.SwapTotal - swapFree
	}
}

func estimateMemAvailable(values map[string]uint64) uint64 {
	available := values["MemFree"] + values["Buffers"] + values["Cached"] + values["SReclaimable"]
	if shmem := values["Shmem"]; available > shmem {
		available -= shmem
	} else {
		available = 0
	}
	return available
}

func readRebootMarkerPath(paths []string) (string, bool) {
	for _, path := range paths {
		if _, err := os.Stat(path); err == nil {
			return path, true
		}
	}
	return "", false
}

func readRebootRequiredPkgs(markerPath string) string {
	data, err := os.ReadFile(markerPath + ".pkgs")
	if err != nil {
		return ""
	}
	pkgs := strings.Fields(string(data))
	if len(pkgs) == 0 {
		return ""
	}
	if len(pkgs) > 3 {
		ellipsis := "…"
		if !utf8Locale() {
			ellipsis = "..."
		}
		return strings.Join(pkgs[:3], ", ") + ", " + ellipsis
	}
	return strings.Join(pkgs, ", ")
}

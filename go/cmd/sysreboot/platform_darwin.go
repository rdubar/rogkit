//go:build darwin

package main

import (
	"encoding/binary"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	"golang.org/x/sys/unix"
)

// gather uses direct sysctls where the value is a plain scalar (fast,
// no struct-layout guessing) and only falls back to vm_stat for the page
// counters that are awkward to retrieve through a single scalar sysctl —
// trading one tiny subprocess for avoiding kernel struct decoding.
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

// kern.boottime is exposed as a timeval; SysctlTimeval gives us the
// boot timestamp without having to hand-decode the raw struct bytes.
func readUptimeSysctl() (float64, error) {
	tv, err := unix.SysctlTimeval("kern.boottime")
	if err != nil {
		return 0, err
	}
	bootSec, _ := tv.Unix()
	return float64(time.Now().Unix() - bootSec), nil
}

func readLoadAvg() (l1, l5, l15 float64, err error) {
	raw, err := unix.SysctlRaw("vm.loadavg")
	if err != nil {
		return 0, 0, 0, err
	}
	if l1, l5, l15, ok := parseLoadAvgRaw(raw); ok {
		return l1, l5, l15, nil
	}
	out, err := unix.Sysctl("vm.loadavg")
	if err != nil {
		return 0, 0, 0, err
	}
	return readLoadAvgFromText(out)
}

func readLoadAvgFromText(out string) (l1, l5, l15 float64, err error) {
	fields := strings.Fields(strings.Trim(out, "{} \t\n"))
	if len(fields) < 3 {
		return 0, 0, 0, nil
	}
	l1, _ = strconv.ParseFloat(fields[0], 64)
	l5, _ = strconv.ParseFloat(fields[1], 64)
	l15, _ = strconv.ParseFloat(fields[2], 64)
	return l1, l5, l15, nil
}

func parseLoadAvgRaw(raw []byte) (l1, l5, l15 float64, ok bool) {
	if len(raw) < 16 {
		return 0, 0, 0, false
	}

	ld1 := int32(binary.LittleEndian.Uint32(raw[0:4]))
	ld5 := int32(binary.LittleEndian.Uint32(raw[4:8]))
	ld15 := int32(binary.LittleEndian.Uint32(raw[8:12]))

	var fscale int64
	switch {
	case len(raw) >= 24:
		fscale = int64(binary.LittleEndian.Uint64(raw[16:24]))
	case len(raw) >= 16:
		fscale = int64(int32(binary.LittleEndian.Uint32(raw[12:16])))
	default:
		return 0, 0, 0, false
	}
	if fscale <= 0 {
		return 0, 0, 0, false
	}

	scale := float64(fscale)
	return float64(ld1) / scale, float64(ld5) / scale, float64(ld15) / scale, true
}

// readVMStat approximates "available" memory as free+inactive+speculative
// pages — macOS caches aggressively, so raw free pages alone badly
// understates what's actually reclaimable. This is a heuristic, not an
// exact figure.
func readVMStat(s *Stats) {
	out, err := exec.Command("vm_stat").Output()
	if err != nil {
		return
	}
	text := string(out)

	pageSize := uint64(4096)
	pages := map[string]uint64{}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if v, ok := parseVMStatPageSize(line); ok {
			pageSize = v
			continue
		}
		if name, count, ok := parseVMStatLine(line); ok {
			pages[name] = count
		}
	}

	s.MemAvailable = (pages["Pages free"] + pages["Pages inactive"] + pages["Pages speculative"]) * pageSize
}

func readSwapUsage(s *Stats) {
	raw, err := unix.SysctlRaw("vm.swapusage")
	if err != nil {
		return
	}
	if total, used, ok := parseSwapUsageRaw(raw); ok {
		s.SwapTotal = total
		s.SwapUsed = used
		return
	}
	out, err := unix.Sysctl("vm.swapusage")
	if err != nil {
		return
	}
	total, used, ok := parseSwapUsageText(out)
	if !ok {
		return
	}
	s.SwapTotal = total
	s.SwapUsed = used
}

func parseVMStatPageSize(line string) (uint64, bool) {
	const marker = "page size of "
	start := strings.Index(line, marker)
	if start < 0 {
		return 0, false
	}
	start += len(marker)
	end := strings.Index(line[start:], " bytes")
	if end < 0 {
		return 0, false
	}
	value, err := strconv.ParseUint(strings.TrimSpace(line[start:start+end]), 10, 64)
	if err != nil {
		return 0, false
	}
	return value, true
}

func parseVMStatLine(line string) (name string, count uint64, ok bool) {
	namePart, valuePart, found := strings.Cut(line, ":")
	if !found {
		return "", 0, false
	}
	name = strings.TrimSpace(namePart)
	valuePart = strings.TrimSpace(strings.TrimSuffix(valuePart, "."))
	if name == "" || valuePart == "" {
		return "", 0, false
	}
	count, err := strconv.ParseUint(valuePart, 10, 64)
	if err != nil {
		return "", 0, false
	}
	return name, count, true
}

func parseSwapUsageText(text string) (totalBytes, usedBytes uint64, ok bool) {
	const totalMarker = "total = "
	const usedMarker = " used = "

	start := strings.Index(text, totalMarker)
	if start < 0 {
		return 0, 0, false
	}
	text = text[start+len(totalMarker):]
	end := strings.Index(text, " ")
	if end < 0 {
		return 0, 0, false
	}
	total, ok := parseScaledBytes(text[:end])
	if !ok {
		return 0, 0, false
	}
	usedStart := strings.Index(text, usedMarker)
	if usedStart < 0 {
		return 0, 0, false
	}
	usedField := strings.Fields(text[usedStart+len(usedMarker):])
	if len(usedField) == 0 {
		return 0, 0, false
	}
	used, ok := parseScaledBytes(usedField[0])
	if !ok {
		return 0, 0, false
	}
	return total, used, true
}

func parseSwapUsageRaw(raw []byte) (totalBytes, usedBytes uint64, ok bool) {
	if len(raw) < 24 {
		return 0, 0, false
	}

	total := binary.LittleEndian.Uint64(raw[0:8])
	used := binary.LittleEndian.Uint64(raw[16:24])
	if total == 0 {
		return 0, 0, false
	}
	return total, used, true
}

func parseScaledBytes(value string) (uint64, bool) {
	if value == "" {
		return 0, false
	}
	unit := value[len(value)-1]
	multiplier := uint64(1)
	switch unit {
	case 'K', 'k':
		multiplier = 1024
		value = value[:len(value)-1]
	case 'M', 'm':
		multiplier = 1024 * 1024
		value = value[:len(value)-1]
	case 'G', 'g':
		multiplier = 1024 * 1024 * 1024
		value = value[:len(value)-1]
	case 'T', 't':
		multiplier = 1024 * 1024 * 1024 * 1024
		value = value[:len(value)-1]
	default:
		return 0, false
	}
	f, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return 0, false
	}
	return uint64(f * float64(multiplier)), true
}

package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// siblingBinary locates another rogkit Go tool the same way drift does:
// same directory as the running executable first (all installed to one
// GOBIN by scripts/build_go.sh), falling back to $PATH.
func siblingBinary(name string) string {
	if exe, err := os.Executable(); err == nil {
		candidate := filepath.Join(filepath.Dir(exe), name)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	if path, err := exec.LookPath(name); err == nil {
		return path
	}
	return ""
}

// sysStats mirrors the fields why cares about from `sysreboot --json`.
type sysStats struct {
	Cores        int     `json:"cores"`
	Load1        float64 `json:"load1"`
	MemTotal     uint64  `json:"mem_total"`
	MemAvailable uint64  `json:"mem_available"`
	SwapTotal    uint64  `json:"swap_total"`
	SwapUsed     uint64  `json:"swap_used"`
}

func collectSysStats() (sysStats, bool) {
	bin := siblingBinary("sysreboot")
	if bin == "" {
		return sysStats{}, false
	}
	out, err := exec.Command(bin, "--json").Output()
	if err != nil {
		return sysStats{}, false
	}
	var s sysStats
	if err := json.Unmarshal(out, &s); err != nil {
		return sysStats{}, false
	}
	return s, true
}

// memGroup mirrors one entry of `mem --json`'s "groups" array.
type memGroup struct {
	Name     string  `json:"name"`
	RSSBytes uint64  `json:"rss_bytes"`
	PctMem   float64 `json:"pct_mem"`
}

func collectTopMem() (memGroup, bool) {
	bin := siblingBinary("mem")
	if bin == "" {
		return memGroup{}, false
	}
	out, err := exec.Command(bin, "--json", "-n", "1").Output()
	if err != nil {
		return memGroup{}, false
	}
	var parsed struct {
		Groups []memGroup `json:"groups"`
	}
	if err := json.Unmarshal(out, &parsed); err != nil || len(parsed.Groups) == 0 {
		return memGroup{}, false
	}
	return parsed.Groups[0], true
}

type cpuProc struct {
	Name string
	PID  int
	PCPU float64
}

// collectTopCPU shells out to `ps -axo pid=,pcpu=,comm=` once and returns the
// single highest-%CPU process — a one-shot snapshot, not a sustained-over-time
// measurement (that would need repeated sampling, which a single invocation
// can't honestly claim to have done).
func collectTopCPU() (cpuProc, bool) {
	out, err := exec.Command("ps", "-axo", "pid=,pcpu=,comm=").Output()
	if err != nil {
		return cpuProc{}, false
	}
	best := cpuProc{}
	found := false
	scanner := bufio.NewScanner(bytes.NewReader(out))
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 3 {
			continue
		}
		pid, err := strconv.Atoi(fields[0])
		if err != nil {
			continue
		}
		pcpu, err := strconv.ParseFloat(fields[1], 64)
		if err != nil {
			continue
		}
		name := filepath.Base(strings.Join(fields[2:], " "))
		if !found || pcpu > best.PCPU {
			best = cpuProc{Name: name, PID: pid, PCPU: pcpu}
			found = true
		}
	}
	return best, found
}

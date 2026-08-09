//go:build darwin

package main

import (
	"bufio"
	"bytes"
	"fmt"
	"os/exec"
	"sort"
	"strconv"
	"strings"

	"golang.org/x/sys/unix"
)

// P_TRANSLATED, from XNU's bsd/sys/proc.h: set on kinfo_proc.Proc.P_flag for
// any process running under Rosetta 2. This is the same bit Activity
// Monitor's "Kind: Intel" column and `sysctl.proc_translated` are backed by.
const pTranslated = 0x00020000

// scan reads kern.proc.all once to find every translated pid, then shells
// out to `ps` once for full executable paths so grouping can use the real
// app name instead of kinfo_proc's 16-byte truncated comm. Both calls are
// cheap enough that a one-shot run stays effectively instant.
func scan() ([]app, error) {
	procs, err := unix.SysctlKinfoProcSlice("kern.proc.all")
	if err != nil {
		return nil, fmt.Errorf("sysctl kern.proc.all: %w", err)
	}

	var translatedPids []int
	for _, p := range procs {
		if p.Proc.P_flag&pTranslated != 0 {
			translatedPids = append(translatedPids, int(p.Proc.P_pid))
		}
	}
	if len(translatedPids) == 0 {
		return []app{}, nil
	}

	names, err := pidNames()
	if err != nil {
		return nil, fmt.Errorf("ps: %w", err)
	}

	index := make(map[string]int)
	var apps []app
	for _, pid := range translatedPids {
		name := names[pid]
		if name == "" {
			name = fmt.Sprintf("pid %d", pid)
		}
		name = canonicalAppName(name)
		if i, ok := index[name]; ok {
			apps[i].Pids = append(apps[i].Pids, pid)
			continue
		}
		index[name] = len(apps)
		apps = append(apps, app{Name: name, Pids: []int{pid}})
	}

	for i := range apps {
		sort.Ints(apps[i].Pids)
	}
	sort.Slice(apps, func(i, j int) bool { return apps[i].Name < apps[j].Name })
	return apps, nil
}

// pidNames returns full `ps` comm (executable path) keyed by pid.
func pidNames() (map[int]string, error) {
	out, err := exec.Command("ps", "-axo", "pid=,comm=").Output()
	if err != nil {
		return nil, err
	}
	names := make(map[int]string)
	scanner := bufio.NewScanner(bytes.NewReader(out))
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 2 {
			continue
		}
		pid, err := strconv.Atoi(fields[0])
		if err != nil {
			continue
		}
		names[pid] = strings.Join(fields[1:], " ")
	}
	return names, scanner.Err()
}

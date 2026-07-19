package main

import (
	"fmt"
	"strconv"
	"strings"
)

type severity int

const (
	severityInfo severity = iota
	severityNotable
)

// Change is one reported delta between two snapshots.
type Change struct {
	Collector string
	Text      string
	Severity  severity
}

// Thresholds below which a delta is noise, not signal — deliberately
// conservative so `drift` stays quiet on ordinary day-to-day variance.
const (
	diskNotableBytes = 2 * 1024 * 1024 * 1024 // 2 GB
	memNotableBytes  = 512 * 1024 * 1024      // 512 MB
	diskAlarmingPct  = 90.0
)

// Diff compares two snapshots and returns every reportable change, disk
// first through repos last (the fixed collector order used everywhere else
// in drift).
func Diff(prev, curr Snapshot) []Change {
	var changes []Change
	changes = append(changes, diffDisk(prev.Disk, curr.Disk)...)
	changes = append(changes, diffMem(prev.Mem, curr.Mem)...)
	changes = append(changes, diffPorts(prev.Ports, curr.Ports)...)
	changes = append(changes, diffAgents(prev.Agents, curr.Agents)...)
	changes = append(changes, diffPackages(prev.Packages, curr.Packages)...)
	changes = append(changes, diffRepos(prev.Repos, curr.Repos)...)
	return changes
}

func diffDisk(prev, curr []DiskEntry) []Change {
	prevByPath := make(map[string]DiskEntry, len(prev))
	for _, d := range prev {
		prevByPath[d.Path] = d
	}
	var changes []Change
	for _, c := range curr {
		p, ok := prevByPath[c.Path]
		if !ok {
			changes = append(changes, Change{"disk", fmt.Sprintf("%s now tracked, %s used (%.1f%%)", c.Path, byteSize(c.UsedBytes), c.UsagePct), severityNotable})
			continue
		}
		delta := int64(c.UsedBytes) - int64(p.UsedBytes)
		if abs64(delta) >= diskNotableBytes {
			sign := "+"
			if delta < 0 {
				sign = "-"
			}
			sev := severityNotable
			changes = append(changes, Change{"disk", fmt.Sprintf("%s %s%s used (%s → %s, %.1f%%)", c.Path, sign, byteSize(uint64(abs64(delta))), byteSize(p.UsedBytes), byteSize(c.UsedBytes), c.UsagePct), sev})
		} else if p.UsagePct < diskAlarmingPct && c.UsagePct >= diskAlarmingPct {
			changes = append(changes, Change{"disk", fmt.Sprintf("%s crossed %.0f%% used (now %.1f%%)", c.Path, diskAlarmingPct, c.UsagePct), severityNotable})
		}
	}
	return changes
}

func diffMem(prev, curr []MemEntry) []Change {
	prevByName := make(map[string]MemEntry, len(prev))
	for _, m := range prev {
		prevByName[m.Name] = m
	}
	var changes []Change
	for _, c := range curr {
		p, ok := prevByName[c.Name]
		if !ok {
			continue // new top-30 entrant is routine churn, not signal
		}
		delta := int64(c.RSSBytes) - int64(p.RSSBytes)
		if abs64(delta) >= memNotableBytes {
			sign := "+"
			if delta < 0 {
				sign = "-"
			}
			changes = append(changes, Change{"mem", fmt.Sprintf("%s %s%s (%s → %s)", c.Name, sign, byteSize(uint64(abs64(delta))), byteSize(p.RSSBytes), byteSize(c.RSSBytes)), severityInfo})
		}
	}
	return changes
}

func diffPorts(prev, curr []PortEntry) []Change {
	key := func(p PortEntry) string { return p.Proto + ":" + strconv.Itoa(p.Port) }
	prevByKey := make(map[string]PortEntry, len(prev))
	for _, p := range prev {
		prevByKey[key(p)] = p
	}
	currByKey := make(map[string]PortEntry, len(curr))
	for _, p := range curr {
		currByKey[key(p)] = p
	}
	var changes []Change
	for k, c := range currByKey {
		if _, ok := prevByKey[k]; !ok {
			label := c.Process
			if label == "" {
				label = "unknown"
			}
			changes = append(changes, Change{"ports", fmt.Sprintf("NEW %s :%d %s (pid %d)", strings.ToUpper(c.Proto), c.Port, label, c.PID), severityNotable})
		}
	}
	for k, p := range prevByKey {
		if _, ok := currByKey[k]; !ok {
			changes = append(changes, Change{"ports", fmt.Sprintf("CLOSED %s :%d (was %s)", strings.ToUpper(p.Proto), p.Port, p.Process), severityInfo})
		}
	}
	return changes
}

func diffAgents(prev, curr []string) []Change {
	prevSet := toSet(prev)
	currSet := toSet(curr)
	var changes []Change
	for _, a := range curr {
		if !prevSet[a] {
			changes = append(changes, Change{"agents", "NEW " + a, severityNotable})
		}
	}
	for _, a := range prev {
		if !currSet[a] {
			changes = append(changes, Change{"agents", "REMOVED " + a, severityInfo})
		}
	}
	return changes
}

func diffPackages(prev, curr map[string]string) []Change {
	var changes []Change
	for k, v := range curr {
		if pv, ok := prev[k]; !ok {
			changes = append(changes, Change{"pkgs", fmt.Sprintf("+%s %s", k, v), severityInfo})
		} else if pv != v {
			changes = append(changes, Change{"pkgs", fmt.Sprintf("%s %s → %s", k, pv, v), severityInfo})
		}
	}
	for k, v := range prev {
		if _, ok := curr[k]; !ok {
			changes = append(changes, Change{"pkgs", fmt.Sprintf("-%s (was %s)", k, v), severityInfo})
		}
	}
	return changes
}

func diffRepos(prev, curr []RepoEntry) []Change {
	prevByName := make(map[string]RepoEntry, len(prev))
	for _, r := range prev {
		prevByName[r.Name] = r
	}
	var changes []Change
	for _, c := range curr {
		p, ok := prevByName[c.Name]
		if !ok {
			continue
		}
		if p.Dirty != c.Dirty {
			changes = append(changes, Change{"repos", fmt.Sprintf("%s %s → %s", c.Name, dirtyLabel(p.Dirty), dirtyLabel(c.Dirty)), severityInfo})
		}
		if p.Ahead != c.Ahead && c.Ahead > 0 {
			changes = append(changes, Change{"repos", fmt.Sprintf("%s %d commit(s) ahead of upstream", c.Name, c.Ahead), severityInfo})
		}
	}
	return changes
}

func dirtyLabel(n int) string {
	if n == 0 {
		return "clean"
	}
	return fmt.Sprintf("%d dirty files", n)
}

func abs64(n int64) int64 {
	if n < 0 {
		return -n
	}
	return n
}

func toSet(items []string) map[string]bool {
	set := make(map[string]bool, len(items))
	for _, i := range items {
		set[i] = true
	}
	return set
}

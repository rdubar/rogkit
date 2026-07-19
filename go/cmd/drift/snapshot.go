package main

import "time"

// Snapshot is one point-in-time capture of machine state. Every collector is
// independent and skips gracefully (empty result, not an error) when its
// data source is unavailable on this platform/machine — same principle
// BUGS.md's cdu proposal used for its provider-per-source design.
type Snapshot struct {
	Timestamp time.Time         `json:"timestamp"`
	Disk      []DiskEntry       `json:"disk"`
	Mem       []MemEntry        `json:"mem"`
	Ports     []PortEntry       `json:"ports"`
	Agents    []string          `json:"agents"`
	Packages  map[string]string `json:"packages"` // "brew:jq" -> "1.8.1"
	Repos     []RepoEntry       `json:"repos"`
}

type DiskEntry struct {
	Path       string  `json:"path"`
	UsedBytes  uint64  `json:"used_bytes"`
	TotalBytes uint64  `json:"total_bytes"`
	UsagePct   float64 `json:"usage_pct"`
}

type MemEntry struct {
	Name     string  `json:"name"`
	RSSBytes uint64  `json:"rss_bytes"`
	PctMem   float64 `json:"pct_mem"`
}

type PortEntry struct {
	Proto   string `json:"proto"`
	Port    int    `json:"port"`
	Process string `json:"process"`
	PID     int    `json:"pid"`
}

type RepoEntry struct {
	Name  string `json:"name"`
	Dirty int    `json:"dirty"`
	Ahead int    `json:"ahead"`
}

// collectSnapshot runs every collector. Each is independently
// best-effort: a failing collector yields a nil/empty slice rather than
// aborting the whole snapshot.
func collectSnapshot(roots []string) Snapshot {
	return Snapshot{
		Timestamp: time.Now(),
		Disk:      collectDisk(),
		Mem:       collectMem(),
		Ports:     collectPorts(),
		Agents:    collectAgents(),
		Packages:  collectPackages(),
		Repos:     collectRepos(roots),
	}
}

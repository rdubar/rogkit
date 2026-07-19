package main

import (
	"compress/gzip"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const snapshotTimeFormat = "2006-01-02T150405"
const maxSnapshotAge = 90 * 24 * time.Hour

// stateDir follows the same inline XDG_STATE_HOME idiom already used by
// rogkit_package/media/update.py's get_sync_log_path — state, not config,
// so it stays out of ~/.config/rogkit which is for user-edited settings.
func stateDir() (string, error) {
	base := os.Getenv("XDG_STATE_HOME")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		base = filepath.Join(home, ".local", "state")
	}
	dir := filepath.Join(base, "rogkit", "drift")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	return dir, nil
}

func snapshotFilename(t time.Time) string {
	return fmt.Sprintf("snap-%s.json.gz", t.UTC().Format(snapshotTimeFormat))
}

// SaveSnapshot writes a gzipped JSON snapshot and prunes anything older than
// maxSnapshotAge that isn't a named baseline.
func SaveSnapshot(dir string, snap Snapshot) (string, error) {
	path := filepath.Join(dir, snapshotFilename(snap.Timestamp))
	f, err := os.Create(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	gz := gzip.NewWriter(f)
	enc := json.NewEncoder(gz)
	if err := enc.Encode(snap); err != nil {
		gz.Close()
		return "", err
	}
	if err := gz.Close(); err != nil {
		return "", err
	}

	prune(dir)
	return path, nil
}

func LoadSnapshot(path string) (Snapshot, error) {
	f, err := os.Open(path)
	if err != nil {
		return Snapshot{}, err
	}
	defer f.Close()

	gz, err := gzip.NewReader(f)
	if err != nil {
		return Snapshot{}, err
	}
	defer gz.Close()

	var snap Snapshot
	if err := json.NewDecoder(gz).Decode(&snap); err != nil {
		return Snapshot{}, err
	}
	return snap, nil
}

// ListSnapshots returns every snap-*.json.gz filename in dir, oldest first.
func ListSnapshots(dir string) ([]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasPrefix(e.Name(), "snap-") && strings.HasSuffix(e.Name(), ".json.gz") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names) // RFC3339-ish filenames sort chronologically
	return names, nil
}

// prune deletes snapshots older than maxSnapshotAge, skipping anything a
// baseline currently points at.
func prune(dir string) {
	names, err := ListSnapshots(dir)
	if err != nil {
		return
	}
	baselines, _ := LoadBaselines(dir)
	protected := make(map[string]bool, len(baselines))
	for _, name := range baselines {
		protected[name] = true
	}
	cutoff := time.Now().Add(-maxSnapshotAge)
	for _, name := range names {
		if protected[name] {
			continue
		}
		t, err := parseSnapshotTime(name)
		if err != nil || t.After(cutoff) {
			continue
		}
		_ = os.Remove(filepath.Join(dir, name))
	}
}

func parseSnapshotTime(name string) (time.Time, error) {
	trimmed := strings.TrimSuffix(strings.TrimPrefix(name, "snap-"), ".json.gz")
	return time.Parse(snapshotTimeFormat, trimmed)
}

// baselines.json maps a user-chosen name to a snapshot filename — a tiny
// index file rather than symlinks, so it stays trivially inspectable/editable.
func baselinesPath(dir string) string { return filepath.Join(dir, "baselines.json") }

func LoadBaselines(dir string) (map[string]string, error) {
	data, err := os.ReadFile(baselinesPath(dir))
	if os.IsNotExist(err) {
		return map[string]string{}, nil
	}
	if err != nil {
		return nil, err
	}
	var baselines map[string]string
	if err := json.Unmarshal(data, &baselines); err != nil {
		return nil, err
	}
	return baselines, nil
}

func SaveBaseline(dir, name, snapshotFile string) error {
	baselines, err := LoadBaselines(dir)
	if err != nil {
		return err
	}
	baselines[name] = snapshotFile
	data, err := json.MarshalIndent(baselines, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(baselinesPath(dir), data, 0o644)
}

// FindComparisonSnapshot resolves the --since value: a baseline name, a
// duration like "7d", an RFC3339-ish date, or "" for the previous snapshot.
func FindComparisonSnapshot(dir, since string) (string, error) {
	names, err := ListSnapshots(dir)
	if err != nil {
		return "", err
	}
	if len(names) == 0 {
		return "", fmt.Errorf("no previous snapshots")
	}

	if since == "" {
		return names[len(names)-1], nil
	}

	if baselines, err := LoadBaselines(dir); err == nil {
		if file, ok := baselines[since]; ok {
			return file, nil
		}
	}

	target, err := parseSinceValue(since)
	if err != nil {
		return "", err
	}
	return nearestSnapshot(names, target)
}

func parseSinceValue(since string) (time.Time, error) {
	if strings.HasSuffix(since, "d") {
		if days, err := parseDays(since); err == nil {
			return time.Now().Add(-time.Duration(days) * 24 * time.Hour), nil
		}
	}
	for _, layout := range []string{"2006-01-02", time.RFC3339} {
		if t, err := time.Parse(layout, since); err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("unrecognized --since value %q (want a duration like 7d, a date like 2026-07-01, or a baseline name)", since)
}

func parseDays(s string) (int, error) {
	var n int
	_, err := fmt.Sscanf(s, "%dd", &n)
	return n, err
}

// nearestSnapshot returns the snapshot closest to target, preferring the
// nearest one at or before it (so "--since 7d" means "roughly a week ago",
// not "whichever side happens to be numerically closer").
func nearestSnapshot(names []string, target time.Time) (string, error) {
	best := ""
	var bestDiff time.Duration = -1
	for _, name := range names {
		t, err := parseSnapshotTime(name)
		if err != nil {
			continue
		}
		diff := target.Sub(t)
		if diff < 0 {
			diff = -diff
		}
		if bestDiff == -1 || diff < bestDiff {
			bestDiff = diff
			best = name
		}
	}
	if best == "" {
		return "", fmt.Errorf("no snapshot found near %s", target.Format("2006-01-02"))
	}
	return best, nil
}

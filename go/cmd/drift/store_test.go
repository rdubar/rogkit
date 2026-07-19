package main

import (
	"path/filepath"
	"testing"
	"time"
)

func TestSaveLoadSnapshotRoundtrip(t *testing.T) {
	dir := t.TempDir()
	snap := Snapshot{
		Timestamp: time.Date(2026, 7, 18, 9, 2, 0, 0, time.UTC),
		Disk:      []DiskEntry{{Path: "/", UsedBytes: 100, TotalBytes: 200, UsagePct: 50}},
		Repos:     []RepoEntry{{Name: "rogkit", Dirty: 2}},
	}
	path, err := SaveSnapshot(dir, snap)
	if err != nil {
		t.Fatalf("SaveSnapshot: %v", err)
	}

	got, err := LoadSnapshot(path)
	if err != nil {
		t.Fatalf("LoadSnapshot: %v", err)
	}
	if len(got.Disk) != 1 || got.Disk[0].Path != "/" || got.Repos[0].Name != "rogkit" {
		t.Fatalf("roundtrip mismatch: %+v", got)
	}
}

func TestListSnapshotsSortedChronologically(t *testing.T) {
	dir := t.TempDir()
	times := []time.Time{
		time.Date(2026, 7, 18, 9, 0, 0, 0, time.UTC),
		time.Date(2026, 7, 17, 9, 0, 0, 0, time.UTC),
		time.Date(2026, 7, 19, 9, 0, 0, 0, time.UTC),
	}
	for _, ts := range times {
		if _, err := SaveSnapshot(dir, Snapshot{Timestamp: ts}); err != nil {
			t.Fatalf("SaveSnapshot: %v", err)
		}
	}
	names, err := ListSnapshots(dir)
	if err != nil {
		t.Fatalf("ListSnapshots: %v", err)
	}
	if len(names) != 3 {
		t.Fatalf("expected 3 snapshots, got %d: %v", len(names), names)
	}
	t17, _ := parseSnapshotTime(names[0])
	t19, _ := parseSnapshotTime(names[2])
	if t17.Day() != 17 || t19.Day() != 19 {
		t.Fatalf("expected chronological order, got %v", names)
	}
}

func TestBaselineRoundtrip(t *testing.T) {
	dir := t.TempDir()
	if err := SaveBaseline(dir, "morning", "snap-2026-07-18T090000.json.gz"); err != nil {
		t.Fatalf("SaveBaseline: %v", err)
	}
	baselines, err := LoadBaselines(dir)
	if err != nil {
		t.Fatalf("LoadBaselines: %v", err)
	}
	if baselines["morning"] != "snap-2026-07-18T090000.json.gz" {
		t.Fatalf("unexpected baselines: %+v", baselines)
	}
}

func TestFindComparisonSnapshotByBaseline(t *testing.T) {
	dir := t.TempDir()
	path, err := SaveSnapshot(dir, Snapshot{Timestamp: time.Now()})
	if err != nil {
		t.Fatalf("SaveSnapshot: %v", err)
	}
	name := filepath.Base(path)
	if err := SaveBaseline(dir, "morning", name); err != nil {
		t.Fatalf("SaveBaseline: %v", err)
	}
	got, err := FindComparisonSnapshot(dir, "morning")
	if err != nil {
		t.Fatalf("FindComparisonSnapshot: %v", err)
	}
	if got != name {
		t.Fatalf("expected %q, got %q", name, got)
	}
}

func TestFindComparisonSnapshotBadSinceErrors(t *testing.T) {
	dir := t.TempDir()
	if _, err := SaveSnapshot(dir, Snapshot{Timestamp: time.Now()}); err != nil {
		t.Fatalf("SaveSnapshot: %v", err)
	}
	if _, err := FindComparisonSnapshot(dir, "not-a-real-value"); err == nil {
		t.Fatal("expected an error for an unparseable --since value")
	}
}

func TestFindComparisonSnapshotNoPrevious(t *testing.T) {
	dir := t.TempDir()
	if _, err := FindComparisonSnapshot(dir, ""); err == nil {
		t.Fatal("expected an error when no snapshots exist yet")
	}
}

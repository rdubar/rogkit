package main

import "testing"

func TestDiffDiskNotableDelta(t *testing.T) {
	prev := []DiskEntry{{Path: "/", UsedBytes: 100 * 1024 * 1024 * 1024, TotalBytes: 500 * 1024 * 1024 * 1024, UsagePct: 20}}
	curr := []DiskEntry{{Path: "/", UsedBytes: 103 * 1024 * 1024 * 1024, TotalBytes: 500 * 1024 * 1024 * 1024, UsagePct: 20.6}}
	changes := diffDisk(prev, curr)
	if len(changes) != 1 {
		t.Fatalf("expected 1 change for a 3GB delta, got %d: %+v", len(changes), changes)
	}
}

func TestDiffDiskIgnoresSmallDelta(t *testing.T) {
	prev := []DiskEntry{{Path: "/", UsedBytes: 100 * 1024 * 1024 * 1024, TotalBytes: 500 * 1024 * 1024 * 1024, UsagePct: 20}}
	curr := []DiskEntry{{Path: "/", UsedBytes: 100*1024*1024*1024 + 10*1024*1024, TotalBytes: 500 * 1024 * 1024 * 1024, UsagePct: 20}}
	if changes := diffDisk(prev, curr); len(changes) != 0 {
		t.Fatalf("expected no changes for a 10MB delta, got %+v", changes)
	}
}

func TestDiffDiskAlarmingThresholdCrossing(t *testing.T) {
	prev := []DiskEntry{{Path: "/", UsedBytes: 1, TotalBytes: 100, UsagePct: 89}}
	curr := []DiskEntry{{Path: "/", UsedBytes: 1, TotalBytes: 100, UsagePct: 91}}
	changes := diffDisk(prev, curr)
	if len(changes) != 1 || changes[0].Severity != severityNotable {
		t.Fatalf("expected 1 notable change crossing 90%%, got %+v", changes)
	}
}

func TestDiffPortsNewAndClosed(t *testing.T) {
	prev := []PortEntry{{Proto: "tcp", Port: 22, Process: "sshd", PID: 1}}
	curr := []PortEntry{{Proto: "tcp", Port: 8080, Process: "node", PID: 2}}
	changes := diffPorts(prev, curr)
	if len(changes) != 2 {
		t.Fatalf("expected 2 changes (1 new, 1 closed), got %d: %+v", len(changes), changes)
	}
	var sawNew, sawClosed bool
	for _, c := range changes {
		if c.Severity == severityNotable {
			sawNew = true
		} else {
			sawClosed = true
		}
	}
	if !sawNew || !sawClosed {
		t.Fatalf("expected one notable (new) and one info (closed), got %+v", changes)
	}
}

func TestDiffPortsUnchanged(t *testing.T) {
	entries := []PortEntry{{Proto: "tcp", Port: 22, Process: "sshd", PID: 1}}
	if changes := diffPorts(entries, entries); len(changes) != 0 {
		t.Fatalf("expected no changes for identical port lists, got %+v", changes)
	}
}

func TestDiffAgentsNewIsNotable(t *testing.T) {
	changes := diffAgents([]string{"com.a"}, []string{"com.a", "com.b"})
	if len(changes) != 1 || changes[0].Severity != severityNotable {
		t.Fatalf("expected 1 notable new-agent change, got %+v", changes)
	}
}

func TestDiffPackagesAddedChangedRemoved(t *testing.T) {
	prev := map[string]string{"brew:jq": "1.7", "brew:zstd": "1.5"}
	curr := map[string]string{"brew:jq": "1.8", "brew:new": "1.0"}
	changes := diffPackages(prev, curr)
	if len(changes) != 3 {
		t.Fatalf("expected 3 changes (1 version bump, 1 added, 1 removed), got %d: %+v", len(changes), changes)
	}
}

func TestDiffReposDirtyTransition(t *testing.T) {
	prev := []RepoEntry{{Name: "rogkit", Dirty: 0, Ahead: 0}}
	curr := []RepoEntry{{Name: "rogkit", Dirty: 3, Ahead: 0}}
	changes := diffRepos(prev, curr)
	if len(changes) != 1 {
		t.Fatalf("expected 1 dirty-transition change, got %+v", changes)
	}
}

func TestDiffReposNewRepoIgnored(t *testing.T) {
	// A repo with no prior snapshot entry has nothing to diff against.
	curr := []RepoEntry{{Name: "brand-new", Dirty: 5, Ahead: 0}}
	if changes := diffRepos(nil, curr); len(changes) != 0 {
		t.Fatalf("expected no changes for a repo with no baseline, got %+v", changes)
	}
}

func TestExitCode(t *testing.T) {
	cases := []struct {
		changes []Change
		want    int
	}{
		{nil, 0},
		{[]Change{{Severity: severityInfo}}, 1},
		{[]Change{{Severity: severityNotable}}, 2},
		{[]Change{{Severity: severityInfo}, {Severity: severityNotable}}, 2},
	}
	for _, c := range cases {
		if got := exitCode(c.changes); got != c.want {
			t.Errorf("exitCode(%+v) = %d, want %d", c.changes, got, c.want)
		}
	}
}

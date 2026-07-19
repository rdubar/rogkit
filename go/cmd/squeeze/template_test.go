package main

import "testing"

func TestMaskLine(t *testing.T) {
	cases := map[string]string{
		"2026-07-18T09:02:11Z rsync: sent 4821 bytes":                   "<TS> rsync: sent <N> bytes",
		"WARNING: skipping /var/log/app/output.log (permission denied)": "WARNING: skipping <PATH> (permission denied)",
		"connected to 192.168.1.42 on port 8080":                        "connected to <IP> on port <N>",
		"session f47ac10b-58cc-4372-a567-0e02b2c3d479 started":          "session <ID> started",
	}
	for in, want := range cases {
		if got := maskLine(in); got != want {
			t.Errorf("maskLine(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestClusterLinesGroupsIdenticalTemplates(t *testing.T) {
	lines := []string{
		"2026-07-18T09:00:00Z rsync: sent 100 bytes",
		"2026-07-18T09:00:01Z rsync: sent 200 bytes",
		"2026-07-18T09:00:02Z tar: exiting with failure status",
		"",
	}
	clusters := clusterLines(lines)
	if len(clusters) != 2 {
		t.Fatalf("expected 2 clusters (blank line ignored), got %d: %+v", len(clusters), clusters)
	}
	if clusters[0].Count != 2 || clusters[0].First != 1 || clusters[0].Last != 2 {
		t.Errorf("unexpected rsync cluster: %+v", clusters[0])
	}
	if clusters[1].Count != 1 || !clusters[1].Errorish {
		t.Errorf("expected tar failure line marked errorish, got %+v", clusters[1])
	}
}

func TestMaskLineCollapsesPaddingWhitespace(t *testing.T) {
	// Right-aligned numeric columns (common in fixed-width logs, e.g. logd's
	// statistics dump) pad differently by digit count — the mask must not
	// let that padding keep otherwise-identical rows in separate templates.
	a := maskLine("    - [    1749817,  17.5, /usr/libexec/mobileassetd ]")
	b := maskLine("    - [      84751,   0.8, /usr/libexec/routined ]")
	if a != b {
		t.Fatalf("expected padded rows to mask to the same template, got %q vs %q", a, b)
	}
	want := "- [ <N>, <N>.<N>, <PATH> ]"
	if a != want {
		t.Fatalf("maskLine(...) = %q, want %q", a, want)
	}
}

func TestIsErrorish(t *testing.T) {
	if !isErrorish("connection refused by peer") {
		t.Error("expected 'refused' to be errorish")
	}
	if isErrorish("connection established successfully") {
		t.Error("expected a clean success line to not be errorish")
	}
}

package main

import "testing"

func TestCanonicalName(t *testing.T) {
	cases := map[string]string{
		"Google Chrome Helper (Renderer)": "Google Chrome",
		"Google Chrome Helper (GPU)":      "Google Chrome",
		"Google Chrome Helper":            "Google Chrome",
		"Google Chrome":                   "Google Chrome",
		"Slack Helper (Plugin)":           "Slack",
		"WindowServer":                    "WindowServer",
	}
	for in, want := range cases {
		if got := canonicalName(in); got != want {
			t.Errorf("canonicalName(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestGroupByName(t *testing.T) {
	procs := []proc{
		{pid: 1, name: "Google Chrome", rss: 100},
		{pid: 2, name: "Google Chrome Helper (Renderer)", rss: 200},
		{pid: 3, name: "Google Chrome Helper (GPU)", rss: 50},
		{pid: 4, name: "Slack", rss: 300},
	}
	groups := groupByName(procs)
	if len(groups) != 2 {
		t.Fatalf("expected 2 groups, got %d: %+v", len(groups), groups)
	}
	if groups[0].name != "Google Chrome" || groups[0].procs != 3 || groups[0].rss != 350 {
		t.Errorf("unexpected chrome group: %+v", groups[0])
	}
	if groups[1].name != "Slack" || groups[1].procs != 1 || groups[1].rss != 300 {
		t.Errorf("unexpected slack group: %+v", groups[1])
	}
}

func TestMatchProcs(t *testing.T) {
	procs := []proc{
		{pid: 1, name: "Google Chrome", rss: 100},
		{pid: 2, name: "Google Chrome Helper (Renderer)", rss: 200},
		{pid: 3, name: "Slack", rss: 300},
	}
	got := matchProcs(procs, "chrome")
	if len(got) != 2 {
		t.Fatalf("expected 2 matches, got %d: %+v", len(got), got)
	}

	got = matchProcs(procs, "CHROME")
	if len(got) != 2 {
		t.Fatalf("expected case-insensitive match to find 2, got %d", len(got))
	}

	got = matchProcs(procs, "nope")
	if len(got) != 0 {
		t.Fatalf("expected 0 matches, got %d", len(got))
	}
}

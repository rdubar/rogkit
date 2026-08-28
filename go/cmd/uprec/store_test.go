package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestParseRecordUptimedFormat(t *testing.T) {
	b, ok := parseRecord("1424760:1783547580:Darwin 25.6.0")
	if !ok {
		t.Fatal("want a parsed record")
	}
	if b.Uptime != 1424760*time.Second {
		t.Errorf("uptime = %v, want 1424760s", b.Uptime)
	}
	if b.Boot.Unix() != 1783547580 {
		t.Errorf("boot = %d, want 1783547580", b.Boot.Unix())
	}
	if b.System != "Darwin 25.6.0" {
		t.Errorf("system = %q", b.System)
	}
	if b.CleanKnown {
		t.Error("a three-field uptimed line says nothing about how the run ended")
	}
	if !b.End.Equal(b.Boot.Add(b.Uptime)) {
		t.Errorf("end = %v, want boot plus uptime", b.End)
	}
}

func TestParseRecordCleanField(t *testing.T) {
	cases := []struct {
		line             string
		wantClean, known bool
	}{
		{"100:1783547580:Linux 6.1.0:clean", true, true},
		{"100:1783547580:Linux 6.1.0:unclean", false, true},
		{"100:1783547580:Linux 6.1.0:something-else", false, false},
	}
	for _, c := range cases {
		b, ok := parseRecord(c.line)
		if !ok {
			t.Fatalf("%q: want a parsed record", c.line)
		}
		if b.Clean != c.wantClean || b.CleanKnown != c.known {
			t.Errorf("%q: clean=%v known=%v, want %v/%v",
				c.line, b.Clean, b.CleanKnown, c.wantClean, c.known)
		}
	}
}

func TestParseRecordUnknownSystemIsBlank(t *testing.T) {
	b, _ := parseRecord("100:1783547580:unknown")
	if b.System != "" {
		t.Errorf("system = %q, want empty so a real value can replace it in a merge", b.System)
	}
}

func TestParseRecordRejectsJunk(t *testing.T) {
	for _, line := range []string{"", "   ", "# a comment", "nonsense", "abc:123:Linux", "100:def:Linux", "100"} {
		if _, ok := parseRecord(line); ok {
			t.Errorf("parseRecord(%q) accepted a bad line", line)
		}
	}
}

func TestFormatRecordRoundTrip(t *testing.T) {
	cases := []Boot{
		{Boot: time.Unix(1783547580, 0), Uptime: 1424760 * time.Second,
			System: "Darwin 25.6.0", Clean: true, CleanKnown: true},
		{Boot: time.Unix(1785271920, 0), Uptime: 642120 * time.Second,
			System: "Linux 6.1.0", CleanKnown: true},
		{Boot: time.Unix(1787159404, 0), Uptime: 100 * time.Second},
	}

	for _, want := range cases {
		got, ok := parseRecord(formatRecord(want))
		if !ok {
			t.Fatalf("round trip of %+v failed to parse", want)
		}
		if !got.Boot.Equal(want.Boot) || got.Uptime != want.Uptime ||
			got.System != want.System || got.Clean != want.Clean ||
			got.CleanKnown != want.CleanKnown {
			t.Errorf("round trip: got %+v, want %+v", got, want)
		}
	}
}

// The current run has not ended, so it must not be written with a verdict
// on how it did.
func TestFormatRecordCurrentHasNoVerdict(t *testing.T) {
	line := formatRecord(Boot{Boot: time.Unix(1787159404, 0), Uptime: time.Hour,
		Current: true, System: "Darwin 25.6.0"})
	if strings.Count(line, ":") != 2 {
		t.Errorf("line = %q, want three fields for a run still in progress", line)
	}
}

// A colon in the system string would corrupt the field split.
func TestFormatRecordSanitisesSystem(t *testing.T) {
	line := formatRecord(Boot{Boot: time.Unix(1, 0), Uptime: time.Second, System: "Linux 6.1:odd"})
	b, ok := parseRecord(line)
	if !ok {
		t.Fatalf("line %q did not parse", line)
	}
	if b.System != "Linux 6.1 odd" {
		t.Errorf("system = %q, want the colon replaced", b.System)
	}
}

func TestFormatRecordUnknownSystem(t *testing.T) {
	line := formatRecord(Boot{Boot: time.Unix(1, 0), Uptime: time.Second})
	if !strings.HasSuffix(line, ":unknown") {
		t.Errorf("line = %q, want an explicit unknown system field", line)
	}
}

func TestSaveStateRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "uprec.records")
	boots := []Boot{
		{Boot: time.Unix(1783547580, 0), Uptime: 1424760 * time.Second,
			System: "Darwin 25.6.0", Clean: true, CleanKnown: true},
		{Boot: time.Unix(1787159404, 0), Uptime: 783871 * time.Second,
			System: "Darwin 25.6.0", Current: true},
	}

	if err := saveState(path, boots); err != nil {
		t.Fatalf("saveState: %v", err)
	}

	got := readRecords(path, "state")
	if len(got) != 2 {
		t.Fatalf("got %d records, want 2", len(got))
	}
	if got[0].Source != "state" {
		t.Errorf("source = %q, want the label the caller passed", got[0].Source)
	}
	if !got[0].Clean || !got[0].CleanKnown {
		t.Error("the clean verdict should survive a save/load cycle")
	}
}

// Saving must not leave a partial file behind if it is interrupted, so it
// writes to a temporary name and renames.
func TestSaveStateLeavesNoTempFiles(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "uprec.records")
	if err := saveState(path, []Boot{{Boot: time.Unix(1, 0), Uptime: time.Second}}); err != nil {
		t.Fatalf("saveState: %v", err)
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != "uprec.records" {
		t.Errorf("directory holds %v, want only the records file", entries)
	}
}

func TestReadRecordsMissingFileIsNotFatal(t *testing.T) {
	if got := readRecords(filepath.Join(t.TempDir(), "absent"), "state"); got != nil {
		t.Errorf("got %v, want nil for a file that does not exist", got)
	}
}

func TestStatePathHonoursEnvironment(t *testing.T) {
	t.Setenv("UPREC_STATE", "/tmp/explicit-records")
	if got := statePath(); got != "/tmp/explicit-records" {
		t.Errorf("statePath = %q, want the override", got)
	}

	t.Setenv("UPREC_STATE", "")
	t.Setenv("XDG_STATE_HOME", "/tmp/xdg")
	if got := statePath(); got != "/tmp/xdg/rogkit/uprec.records" {
		t.Errorf("statePath = %q, want it under XDG_STATE_HOME", got)
	}
}

func TestLoadStoredMergesUptimedRecords(t *testing.T) {
	dir := t.TempDir()

	statefile := filepath.Join(dir, "uprec.records")
	if err := os.WriteFile(statefile, []byte("100:1000:Linux 6.1.0:clean\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	uptimed := filepath.Join(dir, "records")
	if err := os.WriteFile(uptimed, []byte("200:2000:Linux 6.1.0\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	t.Setenv("UPREC_STATE", statefile)
	t.Setenv("UPREC_UPTIMED_RECORDS", uptimed)

	got := loadStored()
	if len(got) != 2 {
		t.Fatalf("got %d records, want both sources: %+v", len(got), got)
	}

	sources := map[string]bool{got[0].Source: true, got[1].Source: true}
	if !sources["state"] || !sources["uptimed"] {
		t.Errorf("sources = %v, want one of each", sources)
	}
}

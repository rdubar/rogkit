package main

import (
	"testing"
	"time"
)

// Captured verbatim from `wtmpdb last -x -j --time-format iso` on a
// Raspberry Pi running Debian 13, against a throwaway database seeded
// with boot and shutdown entries. Note the trailing space in
// "still running " and the session row that must be ignored.
const wtmpdbFixture = `{
   "entries": [
     { "user": "rog",
       "tty": "pts/2",
       "hostname": "100.126.182.85",
       "login": "2026-08-28T20:06:29+0100",
       "logout": "still logged in"
     },
     { "user": "reboot",
       "tty": "system boot",
       "hostname": "6.18.39+rpt-rpi-2712",
       "login": "2026-08-18T22:37:24+0100",
       "logout": "still running "
     },
     { "user": "reboot",
       "tty": "system boot",
       "hostname": "6.18.39+rpt-rpi-2712",
       "login": "2026-08-18T22:37:24+0100",
       "logout": "2026-08-28T20:56:17+0100",
       "length": "9+22:18"
     },
     { "user": "shutdown",
       "tty": "system down",
       "hostname": "6.18.39+rpt-rpi-2712",
       "login": "2026-08-28T20:56:17+0100",
       "logout": "2026-08-18T22:37:24+0100",
       "length": "213503972+09:42"
     }
   ],
   "start": "2026-08-18T22:37:24+0100"
}`

func TestParseWtmpdbJSON(t *testing.T) {
	events, err := parseWtmpdbJSON([]byte(wtmpdbFixture))
	if err != nil {
		t.Fatalf("parseWtmpdbJSON: %v", err)
	}
	if len(events) != 4 {
		t.Fatalf("got %d events, want 4 (the login session must be ignored, and the "+
			"ended boot contributes both its start and its logout): %+v",
			len(events), events)
	}

	boot := time.Date(2026, 8, 18, 22, 37, 24, 0, time.FixedZone("BST", 3600))
	down := time.Date(2026, 8, 28, 20, 56, 17, 0, time.FixedZone("BST", 3600))

	for i, want := range []struct {
		when time.Time
		kind eventKind
	}{
		{boot, eventBoot},
		{boot, eventBoot},
		{down, eventShutdown},
		{down, eventShutdown},
	} {
		if !events[i].When.Equal(want.when) || events[i].Kind != want.kind {
			t.Errorf("event %d = %v/%v, want %v/%v",
				i, events[i].When, events[i].Kind, want.when, want.kind)
		}
	}
}

// The whole point of asking for --time-format iso is that the year is
// present; the default format omits it.
// Captured from `wtmpdb last -x -j --time-format iso` against a database
// seeded with three historical boots. The last completed run (Jul 1-5)
// has no synthesised "shutdown" entry of its own — wtmpdb only makes one
// for the gap between two boots — so its end exists solely as that row's
// logout.
const wtmpdbHistoryFixture = `{
   "entries": [
     { "user": "reboot",
       "tty": "system boot",
       "login": "2026-07-01T09:00:00+0100",
       "logout": "2026-07-05T09:00:00+0100",
       "length": "4+00:00"
     },
     { "user": "reboot",
       "tty": "system boot",
       "login": "2026-06-16T12:05:00+0100",
       "logout": "crash "
     },
     { "user": "reboot",
       "tty": "system boot",
       "login": "2026-06-01T10:00:00+0100",
       "logout": "2026-06-16T12:00:00+0100",
       "length": "15+02:00"
     },
     { "user": "shutdown",
       "tty": "system down",
       "login": "2026-06-16T12:00:00+0100",
       "logout": "2026-06-16T12:05:00+0100",
       "length": "00:05"
     }
   ],
   "start": "2026-06-01T10:00:00+0100"
}`

// The end of the most recent completed run is only ever in its boot row's
// logout, so a parser reading login alone leaves that run looking like it
// never ended.
func TestParseWtmpdbJSONRecoversFinalShutdown(t *testing.T) {
	events, err := parseWtmpdbJSON([]byte(wtmpdbHistoryFixture))
	if err != nil {
		t.Fatalf("parseWtmpdbJSON: %v", err)
	}

	bst := time.FixedZone("BST", 3600)
	jul5 := time.Date(2026, 7, 5, 9, 0, 0, 0, bst)

	var found bool
	for _, e := range events {
		if e.Kind == eventShutdown && e.When.Equal(jul5) {
			found = true
		}
	}
	if !found {
		t.Errorf("no shutdown at %v in %+v — the last run's end was lost", jul5, events)
	}
}

// Pairing the parsed events must reproduce what wtmpdb itself reports:
// two clean runs and one crash.
func TestWtmpdbHistoryPairsIntoBoots(t *testing.T) {
	events, err := parseWtmpdbJSON([]byte(wtmpdbHistoryFixture))
	if err != nil {
		t.Fatalf("parseWtmpdbJSON: %v", err)
	}

	boots := pairEvents(events, at("2026-08-28 12:00:00"))
	if len(boots) != 3 {
		t.Fatalf("got %d boots, want 3: %+v", len(boots), boots)
	}

	if boots[0].Uptime != 15*24*time.Hour+2*time.Hour || !boots[0].Clean {
		t.Errorf("boot 0 = %v clean=%v, want 15d2h clean", boots[0].Uptime, boots[0].Clean)
	}
	if boots[1].Clean || !boots[1].CleanKnown {
		t.Errorf("boot 1 should be a known crash, got clean=%v known=%v",
			boots[1].Clean, boots[1].CleanKnown)
	}
	if boots[2].Uptime != 4*24*time.Hour || !boots[2].Clean {
		t.Errorf("boot 2 = %v clean=%v, want 4d clean", boots[2].Uptime, boots[2].Clean)
	}
	if boots[2].Current {
		t.Error("the last completed run must not be reported as still running")
	}
}

func TestParseWtmpdbJSONRequiresISOTimes(t *testing.T) {
	events, err := parseWtmpdbJSON([]byte(
		`{"entries":[{"user":"reboot","login":"Tue Aug 18 22:37"}]}`))
	if err != nil {
		t.Fatalf("parseWtmpdbJSON: %v", err)
	}
	if len(events) != 0 {
		t.Errorf("got %+v, want an unparseable timestamp skipped, not guessed", events)
	}
}

func TestParseWtmpdbJSONRejectsNonJSON(t *testing.T) {
	if _, err := parseWtmpdbJSON([]byte("wtmpdb: command not found")); err == nil {
		t.Error("want an error so the caller can fall back to other sources")
	}
}

func TestParseWtmpdbJSONEmpty(t *testing.T) {
	events, err := parseWtmpdbJSON([]byte(`{"entries":[]}`))
	if err != nil {
		t.Fatalf("parseWtmpdbJSON: %v", err)
	}
	if len(events) != 0 {
		t.Errorf("got %+v, want none", events)
	}
}

// The read invocation must never become a writing one: `wtmpdb boot` and
// `wtmpdb shutdown` both add entries to the database.
func TestWtmpdbArgsAreReadOnly(t *testing.T) {
	for _, args := range [][]string{wtmpdbArgs(""), wtmpdbArgs("/tmp/fixture.db")} {
		if args[0] != "last" {
			t.Fatalf("args = %v, want the read subcommand first", args)
		}
		for _, a := range args {
			if a == "boot" || a == "shutdown" || a == "rotate" || a == "import" {
				t.Errorf("args = %v, contains the writing subcommand %q", args, a)
			}
		}
	}

	withFile := wtmpdbArgs("/tmp/fixture.db")
	if withFile[len(withFile)-2] != "-f" || withFile[len(withFile)-1] != "/tmp/fixture.db" {
		t.Errorf("args = %v, want the database path passed with -f", withFile)
	}
	if len(wtmpdbArgs("")) != len(withFile)-2 {
		t.Error("an empty path should add no -f flag")
	}
}

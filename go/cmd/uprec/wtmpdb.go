package main

import (
	"encoding/json"
	"strings"
	"time"
)

// Debian 13 moved boot and shutdown records out of wtmp and into wtmpdb,
// a SQLite database. Rather than put a SQLite driver in go.mod for one
// source, uprec asks the wtmpdb tool itself — the same composition the
// macOS path uses with last(1).
//
// Only the read subcommand is ever invoked. `wtmpdb boot` and `wtmpdb
// shutdown` WRITE entries to the database; they must never be run to
// probe for data.
const (
	wtmpdbCommand = "wtmpdb"

	// wtmpdbTimeFormat is what `--time-format iso` emits. The default
	// format omits the year, which is exactly the ambiguity the macOS
	// last(1) parser has to work around, so ask for ISO instead.
	wtmpdbTimeFormat = "2006-01-02T15:04:05-0700"
)

// wtmpdbArgs is the read-only invocation: -x includes system shutdown
// entries alongside boots, -j gives JSON, and iso timestamps carry a year.
func wtmpdbArgs(dbFile string) []string {
	args := []string{"last", "-x", "-j", "--time-format", "iso"}
	if dbFile != "" {
		args = append(args, "-f", dbFile)
	}
	return args
}

// wtmpdbEntry is one row of `wtmpdb last --json`. Only the fields uprec
// needs are decoded; wtmpdb also reports tty, hostname and length.
type wtmpdbEntry struct {
	User   string `json:"user"`
	Login  string `json:"login"`
	Logout string `json:"logout"`
}

// parseWtmpdbJSON pulls boot and shutdown events out of wtmpdb's output.
// Login sessions are ignored: like last(1), wtmpdb reports a boot as the
// pseudo-user "reboot" and a stop as "shutdown".
//
// A boot row's own logout has to be read as well, not just the separate
// "shutdown" entries. wtmpdb synthesises one of those only for the gap
// between two boots, so the most recent shutdown — the one closing the
// last completed run — appears in that run's logout field and nowhere
// else. Ignoring it leaves the last completed boot looking like it never
// ended.
func parseWtmpdbJSON(data []byte) ([]event, error) {
	var doc struct {
		Entries []wtmpdbEntry `json:"entries"`
	}
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}

	var events []event
	for _, e := range doc.Entries {
		switch e.User {
		case "reboot":
			if t, ok := parseWtmpdbTime(e.Login); ok {
				events = append(events, event{When: t, Kind: eventBoot})
			}
			// "crash " and "still running " are sentinels rather than
			// times; failing to parse them is the right outcome, since
			// neither marks a clean stop.
			if t, ok := parseWtmpdbTime(e.Logout); ok {
				events = append(events, event{When: t, Kind: eventShutdown})
			}
		case "shutdown":
			if t, ok := parseWtmpdbTime(e.Login); ok {
				events = append(events, event{When: t, Kind: eventShutdown})
			}
		}
	}
	return events, nil
}

// parseWtmpdbTime reads one ISO timestamp. wtmpdb pads some values
// ("still running "), so trim before parsing rather than after failing.
func parseWtmpdbTime(s string) (time.Time, bool) {
	t, err := time.Parse(wtmpdbTimeFormat, strings.TrimSpace(s))
	if err != nil {
		return time.Time{}, false
	}
	return t, true
}

// Command drift snapshots system state (disk, per-app memory, listening
// ports, launch agents/systemd units, package inventory, dirty repos under
// ~/dev) and reports what changed since the previous snapshot or a named
// baseline. Every rogkit system tool up to this point is a point-in-time
// view with no memory of yesterday; drift is the missing time axis.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	since := flag.String("since", "", "Compare against: a duration (7d), a date (2026-07-01), or a baseline name. Default: previous snapshot.")
	setBaseline := flag.String("set-baseline", "", "Snapshot now and save it under this baseline name, then exit")
	snapOnly := flag.Bool("snap", false, "Snapshot only, no diff report (for scheduled runs)")
	full := flag.Bool("full", false, "Also print current totals per collector, not just deltas")
	quiet := flag.Bool("q", false, "Plain output, no color")
	flag.BoolVar(quiet, "quiet", false, "Plain output, no color (alias for -q)")
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	var roots rootFlags
	flag.Var(&roots, "root", "Directory to scan for git repos (repeatable, default ~/dev)")
	flag.Parse()

	if len(roots) == 0 {
		home, err := os.UserHomeDir()
		if err == nil {
			roots = rootFlags{home + "/dev"}
		}
	}

	dir, err := stateDir()
	if err != nil {
		fmt.Fprintf(os.Stderr, "drift: %v\n", err)
		os.Exit(3)
	}

	snap := collectSnapshot(roots)

	if *setBaseline != "" {
		path, err := SaveSnapshot(dir, snap)
		if err != nil {
			fmt.Fprintf(os.Stderr, "drift: %v\n", err)
			os.Exit(3)
		}
		if err := SaveBaseline(dir, *setBaseline, filepath.Base(path)); err != nil {
			fmt.Fprintf(os.Stderr, "drift: %v\n", err)
			os.Exit(3)
		}
		fmt.Printf("Baseline %q saved.\n", *setBaseline)
		return
	}

	prevFile, findErr := FindComparisonSnapshot(dir, *since)

	if _, err := SaveSnapshot(dir, snap); err != nil {
		fmt.Fprintf(os.Stderr, "drift: %v\n", err)
		os.Exit(3)
	}

	if *snapOnly {
		return
	}

	if findErr != nil {
		if *since != "" {
			// A bad --since value (typo'd baseline name, unparseable
			// duration/date) is a user error, not "first run" — surface it
			// rather than silently treating it as if no snapshots existed.
			fmt.Fprintf(os.Stderr, "drift: %v\n", findErr)
			os.Exit(3)
		}
		if *jsonOut {
			enc := json.NewEncoder(os.Stdout)
			enc.SetIndent("", "  ")
			_ = enc.Encode(firstRunPayload())
		} else {
			fmt.Println("No previous snapshot to compare against — this one is now the baseline for next time.")
		}
		os.Exit(0)
	}

	prev, err := LoadSnapshot(filepath.Join(dir, prevFile))
	if err != nil {
		fmt.Fprintf(os.Stderr, "drift: %v\n", err)
		os.Exit(3)
	}

	changes := Diff(prev, snap)

	if *jsonOut {
		printReportJSON(changes, prev.Timestamp)
	} else {
		color := !*quiet && isTerminal()
		printReport(changes, prev.Timestamp, color)
		if *full {
			printTotals(snap, color)
		}
	}

	os.Exit(exitCode(changes))
}

// firstRunPayload is what --json emits when there's no previous snapshot to
// diff against — still valid, shaped JSON, not the plain-text sentence the
// non-JSON path prints, so JSON consumers (e.g. primer) never have to
// special-case a first run by failing to parse it.
func firstRunPayload() map[string]any {
	return map[string]any{"first_run": true, "change_count": 0, "notable_count": 0, "changes": []any{}}
}

func exitCode(changes []Change) int {
	notable := false
	for _, c := range changes {
		if c.Severity == severityNotable {
			notable = true
			break
		}
	}
	switch {
	case notable:
		return 2
	case len(changes) > 0:
		return 1
	default:
		return 0
	}
}

func printTotals(snap Snapshot, color bool) {
	c := colors{}
	if color {
		c = activePalette()
	}
	fmt.Println()
	header := "Current totals"
	if color {
		fmt.Println(c.header + header + colorReset)
	} else {
		fmt.Println(header)
	}
	for _, d := range snap.Disk {
		fmt.Printf("  disk    %s: %s used (%.1f%%)\n", d.Path, byteSize(d.UsedBytes), d.UsagePct)
	}
	fmt.Printf("  ports   %d listening\n", len(snap.Ports))
	fmt.Printf("  agents  %d\n", len(snap.Agents))
	fmt.Printf("  pkgs    %d tracked\n", len(snap.Packages))
	dirty := 0
	for _, r := range snap.Repos {
		if r.Dirty > 0 {
			dirty++
		}
	}
	fmt.Printf("  repos   %d dirty of %d scanned\n", dirty, len(snap.Repos))
}

// rootFlags collects repeated -root flags into a slice.
type rootFlags []string

func (r *rootFlags) String() string { return strings.Join(*r, ",") }
func (r *rootFlags) Set(v string) error {
	*r = append(*r, v)
	return nil
}

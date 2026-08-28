// Command uprec reports the longest uptimes a machine has recorded, and
// where the current run sits among them.
//
// It works with or without the uptimed daemon. Where uptimed is running,
// its records are read and merged in; where it is not, the history is
// recovered from the login database (wtmp on Linux, last(1) on macOS),
// which means a machine reports a real history the first time uprec runs
// on it. Every run writes the merged result back to a file under the
// user's state directory, so boots survive the login database being
// rotated away.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"
)

func main() {
	oneline := flag.Bool("1", false, "One-line summary")
	flag.BoolVar(oneline, "oneline", false, "One-line summary (alias for -1)")
	quiet := flag.Bool("q", false, "Plain pipe-delimited output, no table or color")
	flag.BoolVar(quiet, "quiet", false, "Plain pipe-delimited output (alias for -q)")
	flag.BoolVar(quiet, "plain", false, "Plain pipe-delimited output (alias for -q)")
	jsonOut := flag.Bool("json", false, "Output JSON for automation (always the full history)")
	limit := flag.Int("n", 10, "Sessions to show in table and plain output")
	all := flag.Bool("a", false, "Show every session on record")
	flag.BoolVar(all, "all", false, "Show every session on record (alias for -a)")
	noSave := flag.Bool("no-save", false, "Report without updating the stored history")
	flag.Parse()

	ranked := byUptime(gatherHistory(time.Now()))
	if len(ranked) == 0 {
		fmt.Fprintln(os.Stderr, "uprec: no boot records found")
		os.Exit(3)
	}
	sum := summarize(ranked)

	if !*noSave {
		if err := saveState(statePath(), ranked); err != nil {
			fmt.Fprintf(os.Stderr, "uprec: could not save history: %v\n", err)
		}
	}

	if *jsonOut {
		printJSON(ranked, sum)
		return
	}

	shown := ranked
	if !*all && *limit > 0 && len(shown) > *limit {
		shown = shown[:*limit]
	}

	switch {
	case *oneline:
		printOneline(sum)
	case *quiet || !isTerminal():
		printPlain(shown)
	default:
		printTable(shown, sum)
	}
}

// gatherHistory folds together every source that knows about past boots.
// Each is best-effort: a machine with no login database still reports its
// current run, and one with no stored records still reports its history.
func gatherHistory(now time.Time) []Boot {
	stored := loadStored()

	var fromLog []Boot
	if events, err := bootEvents(); err == nil {
		fromLog = pairEvents(events, now)
	}

	var live []Boot
	if b, err := currentBoot(); err == nil {
		live = []Boot{b}
	}

	return mergeBoots(stored, fromLog, live)
}

func printOneline(sum Summary) {
	sep := separator()

	parts := []string{fmt.Sprintf("record %s", formatDuration(sum.Record.Uptime))}
	if sum.CurrentRank > 0 {
		parts = []string{
			fmt.Sprintf("up %s", formatDuration(currentUptime(sum))),
			fmt.Sprintf("rank %d of %d", sum.CurrentRank, sum.Total),
			fmt.Sprintf("record %s (%s)", formatDuration(sum.Record.Uptime),
				sum.Record.Boot.Format("2006-01-02")),
		}
	}
	if sum.Unclean > 0 {
		parts = append(parts, fmt.Sprintf("%d unclean", sum.Unclean))
	}

	out := parts[0]
	for _, p := range parts[1:] {
		out += sep + p
	}
	fmt.Println(out)
}

// currentUptime recovers the live run's length from the ranked history,
// where it sits at the position the summary recorded.
func currentUptime(sum Summary) time.Duration {
	return sum.Record.Uptime - sum.ToRecord
}

func printPlain(shown []Boot) {
	for i, b := range shown {
		ended := "-"
		if !b.End.IsZero() {
			ended = b.End.Format(stampFormat)
		}
		fmt.Printf("%4d | %-14s | %-16s | %-16s | %s\n",
			i+1, formatDuration(b.Uptime), b.Boot.Format(stampFormat), ended, status(b))
	}
}

func printJSON(ranked []Boot, sum Summary) {
	records := make([]map[string]any, 0, len(ranked))
	var current map[string]any

	for i, b := range ranked {
		rec := map[string]any{
			"rank":           i + 1,
			"uptime_seconds": int64(b.Uptime / time.Second),
			"uptime":         formatDuration(b.Uptime),
			"boot":           b.Boot.Format(time.RFC3339),
			"boot_epoch":     b.Boot.Unix(),
			"status":         status(b),
			"system":         b.System,
			"source":         b.Source,
		}
		if !b.End.IsZero() {
			rec["end"] = b.End.Format(time.RFC3339)
			rec["end_epoch"] = b.End.Unix()
		}
		records = append(records, rec)
		if b.Current {
			current = rec
		}
	}

	summary := map[string]any{
		"total":                 sum.Total,
		"unclean":               sum.Unclean,
		"current_rank":          sum.CurrentRank,
		"record_uptime_seconds": int64(sum.Record.Uptime / time.Second),
		"record_boot":           sum.Record.Boot.Format(time.RFC3339),
		"since":                 sum.Since.Format(time.RFC3339),
	}
	if sum.CurrentRank > 1 {
		summary["to_next_rank_seconds"] = int64(sum.ToNextRank / time.Second)
		summary["to_record_seconds"] = int64(sum.ToRecord / time.Second)
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(map[string]any{
		"current": current,
		"records": records,
		"summary": summary,
	})
}

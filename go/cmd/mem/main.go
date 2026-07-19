// Command mem is a fast memory-usage summary: with no arguments, the top N
// processes grouped by app name (Chromium/Electron helper processes rolled
// into their parent); with a name/substring argument, every matching
// process individually plus a combined total — a Go binary so it starts
// instantly, no uv/Rich import cost.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
)

const defaultLimit = 10

func main() {
	limit := flag.Int("n", defaultLimit, "Number of groups to show (summary mode only)")
	flag.IntVar(limit, "limit", defaultLimit, "Number of groups to show (alias for -n)")
	all := flag.Bool("a", false, "Show all groups, no limit (summary mode only)")
	flag.BoolVar(all, "all", false, "Show all groups (alias for -a)")
	quiet := flag.Bool("q", false, "Plain tab-delimited output, no table or color")
	flag.BoolVar(quiet, "quiet", false, "Plain output (alias for -q)")
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	flag.Parse()

	procs, err := readProcs()
	if err != nil {
		fmt.Fprintf(os.Stderr, "mem: %v\n", err)
		os.Exit(1)
	}
	totalMem, err := totalMemory()
	if err != nil {
		fmt.Fprintf(os.Stderr, "mem: %v\n", err)
		os.Exit(1)
	}

	plain := *quiet || !isTerminal()

	if pattern := flag.Arg(0); pattern != "" {
		runFiltered(procs, pattern, totalMem, plain, *jsonOut)
		return
	}
	runSummary(procs, totalMem, *limit, *all, plain, *jsonOut)
}

func runSummary(procs []proc, totalMem uint64, limit int, all bool, plain bool, jsonOut bool) {
	groups := groupByName(procs)
	sort.SliceStable(groups, func(i, j int) bool { return groups[i].rss > groups[j].rss })
	if !all && len(groups) > limit {
		groups = groups[:limit]
	}

	if jsonOut {
		printSummaryJSON(groups, totalMem)
		return
	}

	c := activePalette()
	header := newSummaryHeader(c)
	rows := make([]tableRow, 0, len(groups))
	for _, g := range groups {
		rows = append(rows, formatSummaryRow(c, g, totalMem))
	}

	if plain {
		printPlain(header, rows, false)
		return
	}
	printTable(header, rows, false, summaryRightAlign)
}

func runFiltered(procs []proc, pattern string, totalMem uint64, plain bool, jsonOut bool) {
	matches := matchProcs(procs, pattern)
	sort.SliceStable(matches, func(i, j int) bool { return matches[i].rss > matches[j].rss })

	var totalRSS uint64
	for _, p := range matches {
		totalRSS += p.rss
	}

	if jsonOut {
		printFilteredJSON(pattern, matches, totalRSS, totalMem)
		return
	}

	if len(matches) == 0 {
		fmt.Printf("No processes matching %q.\n", pattern)
		return
	}

	c := activePalette()
	header := newFilteredHeader(c)
	rows := make([]tableRow, 0, len(matches)+1)
	for _, p := range matches {
		rows = append(rows, formatFilteredRow(c, p, totalMem))
	}
	hasTotal := len(matches) > 1
	if hasTotal {
		rows = append(rows, formatTotalRow(c, 1, fmt.Sprintf("TOTAL (%d procs)", len(matches)), totalRSS, totalMem, len(header.cells)))
	}

	if plain {
		printPlain(header, rows, hasTotal)
		return
	}
	printTable(header, rows, hasTotal, filteredRightAlign)
}

func printSummaryJSON(groups []group, totalMem uint64) {
	out := make([]map[string]any, 0, len(groups))
	for _, g := range groups {
		out = append(out, map[string]any{
			"name":      g.name,
			"procs":     g.procs,
			"rss_bytes": g.rss,
			"pct_mem":   percentOf(g.rss, totalMem),
		})
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(map[string]any{"groups": out})
}

func printFilteredJSON(pattern string, matches []proc, totalRSS, totalMem uint64) {
	out := make([]map[string]any, 0, len(matches))
	for _, p := range matches {
		out = append(out, map[string]any{
			"pid":       p.pid,
			"name":      p.name,
			"rss_bytes": p.rss,
			"pct_mem":   percentOf(p.rss, totalMem),
		})
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(map[string]any{
		"pattern":         pattern,
		"processes":       out,
		"total_rss_bytes": totalRSS,
		"total_pct_mem":   percentOf(totalRSS, totalMem),
	})
}

// Command mem is a fast memory-usage summary: with no arguments, the top N
// processes grouped by app name (Chromium/Electron helper processes rolled
// into their parent); with a name/substring argument, every matching
// process individually plus a combined total — a Go binary so it starts
// instantly, no uv/Rich import cost.
package main

import (
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
		runFiltered(procs, pattern, totalMem, plain)
		return
	}
	runSummary(procs, totalMem, *limit, *all, plain)
}

func runSummary(procs []proc, totalMem uint64, limit int, all bool, plain bool) {
	groups := groupByName(procs)
	sort.SliceStable(groups, func(i, j int) bool { return groups[i].rss > groups[j].rss })
	if !all && len(groups) > limit {
		groups = groups[:limit]
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

func runFiltered(procs []proc, pattern string, totalMem uint64, plain bool) {
	matches := matchProcs(procs, pattern)
	if len(matches) == 0 {
		fmt.Printf("No processes matching %q.\n", pattern)
		return
	}
	sort.SliceStable(matches, func(i, j int) bool { return matches[i].rss > matches[j].rss })

	c := activePalette()
	header := newFilteredHeader(c)
	rows := make([]tableRow, 0, len(matches)+1)
	var totalRSS uint64
	var count int
	for _, p := range matches {
		rows = append(rows, formatFilteredRow(c, p, totalMem))
		totalRSS += p.rss
		count++
	}
	hasTotal := len(matches) > 1
	if hasTotal {
		rows = append(rows, formatTotalRow(c, 1, fmt.Sprintf("TOTAL (%d procs)", count), totalRSS, totalMem, len(header.cells)))
	}

	if plain {
		printPlain(header, rows, hasTotal)
		return
	}
	printTable(header, rows, hasTotal, filteredRightAlign)
}

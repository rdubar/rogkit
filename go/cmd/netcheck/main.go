// Command netcheck is a superfast, cross-platform network triage check: it
// probes DNS, latency, and throughput in parallel and prints a one-line
// verdict, plus platform-specific commands to dig deeper when something
// looks wrong.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sync"
)

func main() {
	oneline := flag.Bool("1", false, "Squash the report onto a single line")
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	flag.BoolVar(oneline, "oneline", false, "Squash the report onto a single line (alias for -1)")
	flag.Parse()

	stats := collectAll()
	v := diagnose(stats, platformHintSet())

	if *jsonOut {
		printJSON(stats, v)
	} else {
		printReport(stats, v, *oneline)
	}

	if v.Culprit {
		os.Exit(1)
	}
}

// collectAll runs the three checks concurrently — each has its own timeout
// budget, and running them in parallel keeps the worst case at the slowest
// single check (throughput) rather than the sum of all three.
func collectAll() netStats {
	var stats netStats
	var wg sync.WaitGroup
	wg.Add(3)
	go func() { defer wg.Done(); stats.DNSMs, stats.DNSOK = collectDNS() }()
	go func() { defer wg.Done(); stats.LatencyMs, stats.LatencyOK = collectLatency() }()
	go func() { defer wg.Done(); stats.ThroughputMbps, stats.ThroughputOK = collectThroughput() }()
	wg.Wait()
	return stats
}

func printReport(stats netStats, v verdict, oneline bool) {
	emoji := "🔥"
	if !v.Culprit {
		emoji = "✅"
	}
	fmt.Printf("%s %s\n", emoji, v.Text)
	if oneline {
		return
	}
	fmt.Printf("dns %s · latency %s · throughput %s\n",
		fmtMs(stats.DNSMs, stats.DNSOK), fmtMs(stats.LatencyMs, stats.LatencyOK), fmtMbps(stats.ThroughputMbps, stats.ThroughputOK))
	for _, hint := range v.Hints {
		fmt.Printf("  → %s\n", hint)
	}
}

func fmtMs(ms float64, ok bool) string {
	if !ok {
		return "n/a"
	}
	return fmt.Sprintf("%.0fms", ms)
}

func fmtMbps(mbps float64, ok bool) string {
	if !ok {
		return "n/a"
	}
	return fmt.Sprintf("%.1f Mbps", mbps)
}

func printJSON(stats netStats, v verdict) {
	out := map[string]any{
		"diagnosis":       v.Text,
		"culprit":         v.Culprit,
		"hints":           v.Hints,
		"dns_ms":          stats.DNSMs,
		"dns_ok":          stats.DNSOK,
		"latency_ms":      stats.LatencyMs,
		"latency_ok":      stats.LatencyOK,
		"throughput_mbps": stats.ThroughputMbps,
		"throughput_ok":   stats.ThroughputOK,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}

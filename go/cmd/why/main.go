// Command why is a one-shot slowness triage: it runs the cheap checks in
// escalating order (swap pressure, CPU-bound, memory-bound) and prints a
// one-line diagnosis with a culprit, composing `sysreboot --json` and
// `mem --json` rather than re-reading the same syscalls itself.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
)

func main() {
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	flag.Parse()

	sys, sysOK := collectSysStats()
	topMem, memOK := collectTopMem()
	topCPU, cpuOK := collectTopCPU()

	v := diagnose(sys, sysOK, topMem, memOK, topCPU, cpuOK)

	if *jsonOut {
		printJSON(v, sys, sysOK)
	} else {
		printReport(v, sys, sysOK)
	}

	if v.Culprit {
		os.Exit(1)
	}
	os.Exit(0)
}

func printReport(v verdict, sys sysStats, sysOK bool) {
	emoji := "🔥"
	if !v.Culprit {
		emoji = "✅"
	}
	fmt.Printf("%s %s\n", emoji, v.Text)
	if sysOK {
		fmt.Printf("load %.2f (%d cores) · mem %d%% free%s\n",
			sys.Load1, sys.Cores, freePercent(sys.MemAvailable, sys.MemTotal), swapSuffix(sys.SwapUsed, sys.SwapTotal))
	}
}

func freePercent(available, total uint64) int {
	if total == 0 {
		return 0
	}
	return int(float64(available) / float64(total) * 100)
}

func swapSuffix(used, total uint64) string {
	if total == 0 {
		return ""
	}
	return fmt.Sprintf(" · swap %d%% used", int(float64(used)/float64(total)*100))
}

func printJSON(v verdict, sys sysStats, sysOK bool) {
	out := map[string]any{
		"diagnosis": v.Text,
		"culprit":   v.Culprit,
	}
	if sysOK {
		out["load1"] = sys.Load1
		out["cores"] = sys.Cores
		out["mem_total"] = sys.MemTotal
		out["mem_available"] = sys.MemAvailable
		out["swap_total"] = sys.SwapTotal
		out["swap_used"] = sys.SwapUsed
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}

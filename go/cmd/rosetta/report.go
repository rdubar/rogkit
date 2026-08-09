package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

func printJSON(apps []app) {
	total := 0
	for _, a := range apps {
		total += len(a.Pids)
	}
	out := map[string]any{
		"translated_count": total,
		"apps":             apps,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}

func printReport(apps []app, plain bool) {
	if len(apps) == 0 {
		if plain {
			fmt.Println("no rosetta processes running")
		} else {
			fmt.Println("✅ No Rosetta processes running")
		}
		return
	}

	total := 0
	for _, a := range apps {
		total += len(a.Pids)
	}

	if plain {
		for _, a := range apps {
			fmt.Printf("%s\t%d\t%s\n", a.Name, len(a.Pids), joinPids(a.Pids))
		}
		return
	}

	noun := "processes"
	if total == 1 {
		noun = "process"
	}
	fmt.Printf("🌀 %d %s running under Rosetta\n\n", total, noun)
	for _, a := range apps {
		procNoun := "processes"
		if len(a.Pids) == 1 {
			procNoun = "process "
		}
		fmt.Printf("  %-30s %d %s   pid %s\n", a.Name, len(a.Pids), procNoun, joinPids(a.Pids))
	}
}

func joinPids(pids []int) string {
	strs := make([]string, len(pids))
	for i, p := range pids {
		strs[i] = strconv.Itoa(p)
	}
	return strings.Join(strs, ",")
}

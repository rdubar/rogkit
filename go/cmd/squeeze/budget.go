package main

import (
	"fmt"
	"sort"
)

// estimateTokens is a deliberately simple, documented heuristic (~4 chars
// per token) — good enough for budgeting output size, not meant to match
// any specific tokenizer exactly.
func estimateTokens(s string) int {
	return (len(s) + 3) / 4
}

// selectForBudget keeps the most informative clusters within budgetTokens:
// error-shaped templates first, then rarest-first, since a template that
// only happened once is more likely to matter than one that happened 10,000
// times. Bulk, non-error noise is what gets elided when the budget runs out.
// Always keeps at least one cluster, even if it alone exceeds the budget.
func selectForBudget(clusters []cluster, budgetTokens int) (kept []cluster, elidedCount, elidedLines int) {
	ordered := make([]cluster, len(clusters))
	copy(ordered, clusters)
	sort.SliceStable(ordered, func(i, j int) bool {
		if ordered[i].Errorish != ordered[j].Errorish {
			return ordered[i].Errorish
		}
		return ordered[i].Count < ordered[j].Count
	})

	used := 0
	for _, c := range ordered {
		cost := estimateTokens(formatCluster(c))
		if used+cost > budgetTokens && len(kept) > 0 {
			elidedCount++
			elidedLines += c.Count
			continue
		}
		kept = append(kept, c)
		used += cost
	}

	sort.SliceStable(kept, func(i, j int) bool { return kept[i].Count > kept[j].Count })
	return kept, elidedCount, elidedLines
}

func formatCluster(c cluster) string {
	countLabel := fmt.Sprintf("%d×", c.Count)
	if c.First != c.Last {
		return fmt.Sprintf("%6s  %s   first line %d, last line %d", countLabel, c.Pattern, c.First, c.Last)
	}
	return fmt.Sprintf("%6s  %s   line %d", countLabel, c.Pattern, c.First)
}

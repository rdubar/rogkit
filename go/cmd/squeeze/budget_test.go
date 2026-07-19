package main

import "testing"

func TestSelectForBudgetKeepsErrorAndRareOverBulk(t *testing.T) {
	bulk := cluster{Pattern: "bulk noise line repeated many times over", Count: 1000, First: 1, Last: 1000}
	rare := cluster{Pattern: "rare but harmless thing happened once", Count: 1, First: 500, Last: 500}
	errorC := cluster{Pattern: "fatal: something broke badly", Count: 1, First: 999, Last: 999, Errorish: true}

	// Budget exactly enough for the error + rare clusters, not the bulk one.
	budget := estimateTokens(formatCluster(errorC)) + estimateTokens(formatCluster(rare))

	kept, elidedCount, elidedLines := selectForBudget([]cluster{bulk, rare, errorC}, budget)
	if elidedCount != 1 || elidedLines != 1000 {
		t.Fatalf("expected the 1000-count bulk cluster elided, got elidedCount=%d elidedLines=%d", elidedCount, elidedLines)
	}
	if len(kept) != 2 {
		t.Fatalf("expected 2 kept clusters (error + rare), got %d: %+v", len(kept), kept)
	}
	for _, k := range kept {
		if k.Count == 1000 {
			t.Fatalf("bulk cluster should have been elided, found in kept: %+v", k)
		}
	}
}

func TestSelectForBudgetAlwaysKeepsAtLeastOne(t *testing.T) {
	clusters := []cluster{
		{Pattern: "a single very long line that alone exceeds any tiny budget we might configure here", Count: 5, First: 1, Last: 5},
	}
	kept, elidedCount, _ := selectForBudget(clusters, 1)
	if len(kept) != 1 || elidedCount != 0 {
		t.Fatalf("expected the sole cluster kept even over budget, got kept=%d elided=%d", len(kept), elidedCount)
	}
}

func TestEstimateTokens(t *testing.T) {
	if got := estimateTokens("abcd"); got != 1 {
		t.Errorf("estimateTokens(4 chars) = %d, want 1", got)
	}
	if got := estimateTokens(""); got != 0 {
		t.Errorf("estimateTokens(empty) = %d, want 0", got)
	}
}

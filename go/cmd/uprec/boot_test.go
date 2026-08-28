package main

import (
	"testing"
	"time"
)

func at(s string) time.Time {
	t, err := time.ParseInLocation("2006-01-02 15:04:05", s, time.Local)
	if err != nil {
		panic(err)
	}
	return t
}

func TestPairEventsClassifiesEndings(t *testing.T) {
	now := at("2026-08-28 12:00:00")
	events := []event{
		{When: at("2026-08-01 10:00:00"), Kind: eventBoot},
		{When: at("2026-08-03 10:00:00"), Kind: eventShutdown},
		{When: at("2026-08-03 10:05:00"), Kind: eventBoot},
		// No shutdown before the next boot: the machine went down hard.
		{When: at("2026-08-10 09:00:00"), Kind: eventBoot},
	}

	boots := pairEvents(events, now)
	if len(boots) != 3 {
		t.Fatalf("got %d boots, want 3", len(boots))
	}

	if !boots[0].Clean || !boots[0].CleanKnown {
		t.Errorf("first boot ended at a shutdown record, want clean")
	}
	if boots[0].Uptime != 48*time.Hour {
		t.Errorf("first uptime = %v, want 48h", boots[0].Uptime)
	}
	if boots[1].Clean || !boots[1].CleanKnown {
		t.Errorf("second boot ended at another boot, want a known-unclean verdict")
	}
	if !boots[2].Current || !boots[2].End.IsZero() {
		t.Errorf("trailing boot should be the run in progress with no end")
	}
	if boots[2].Uptime != now.Sub(at("2026-08-10 09:00:00")) {
		t.Errorf("current uptime = %v, want now minus boot", boots[2].Uptime)
	}
}

// A reboot logged in the same second as its shutdown is still a clean
// stop, so the shutdown has to sort first.
func TestPairEventsTieBreaksShutdownFirst(t *testing.T) {
	now := at("2026-08-28 12:00:00")
	events := []event{
		{When: at("2026-08-01 10:00:00"), Kind: eventBoot},
		{When: at("2026-08-02 10:00:00"), Kind: eventBoot},
		{When: at("2026-08-02 10:00:00"), Kind: eventShutdown},
	}

	boots := pairEvents(events, now)
	if len(boots) != 2 {
		t.Fatalf("got %d boots, want 2", len(boots))
	}
	if !boots[0].Clean {
		t.Errorf("boot ending on a same-second shutdown should be clean")
	}
}

func TestDedupeEventsDropsRepeats(t *testing.T) {
	now := at("2026-08-28 12:00:00")
	events := []event{
		{When: at("2026-08-01 10:00:00"), Kind: eventBoot},
		{When: at("2026-08-03 10:00:00"), Kind: eventShutdown},
		{When: at("2026-08-03 10:00:20"), Kind: eventShutdown},
		{When: at("2026-08-03 10:05:00"), Kind: eventBoot},
	}

	boots := pairEvents(events, now)
	if len(boots) != 2 {
		t.Fatalf("got %d boots, want 2", len(boots))
	}
	if boots[0].End != at("2026-08-03 10:00:00") {
		t.Errorf("end = %v, want the first of the duplicate shutdowns", boots[0].End)
	}
}

// The same boot seen through last(1) and through the running kernel must
// collapse to one session, keeping the kernel's exact timestamp.
func TestMergeBootsPrefersPreciseSource(t *testing.T) {
	coarse := Boot{Boot: at("2026-08-19 18:10:00"), Uptime: 100 * time.Hour, Current: true, Source: "wtmp"}
	exact := Boot{Boot: at("2026-08-19 18:10:04"), Uptime: 99 * time.Hour, Current: true, Source: "live", System: "Darwin 25.6.0"}

	merged := mergeBoots([]Boot{coarse}, []Boot{exact})
	if len(merged) != 1 {
		t.Fatalf("got %d boots, want 1", len(merged))
	}
	if !merged[0].Boot.Equal(exact.Boot) {
		t.Errorf("boot = %v, want the kernel's exact time %v", merged[0].Boot, exact.Boot)
	}
	if merged[0].Uptime != 99*time.Hour {
		t.Errorf("uptime = %v, want the live figure, not the coarser longer one", merged[0].Uptime)
	}
	if merged[0].System != "Darwin 25.6.0" {
		t.Errorf("system = %q, want it carried over", merged[0].System)
	}
}

// A stored record is a snapshot, so a longer uptime from the login
// database is the better estimate of how the run actually ended.
func TestMergeBootsTakesLongerUptimeFromLog(t *testing.T) {
	stored := Boot{Boot: at("2026-07-08 22:53:00"), Uptime: 100 * time.Hour, Source: "state"}
	logged := Boot{Boot: at("2026-07-08 22:53:00"), Uptime: 395 * time.Hour,
		End: at("2026-07-25 10:39:00"), Clean: true, CleanKnown: true, Source: "wtmp"}

	merged := mergeBoots([]Boot{stored}, []Boot{logged})
	if len(merged) != 1 {
		t.Fatalf("got %d boots, want 1", len(merged))
	}
	if merged[0].Uptime != 395*time.Hour {
		t.Errorf("uptime = %v, want the longer logged value", merged[0].Uptime)
	}
	if !merged[0].CleanKnown || !merged[0].Clean {
		t.Errorf("the log's clean verdict should survive the merge")
	}
}

func TestMergeBootsKeepsDistinctBoots(t *testing.T) {
	a := Boot{Boot: at("2026-08-19 18:10:00"), Source: "wtmp"}
	b := Boot{Boot: at("2026-08-19 18:30:00"), Source: "wtmp"}

	if got := len(mergeBoots([]Boot{a}, []Boot{b})); got != 2 {
		t.Errorf("got %d boots, want 2 — 20 minutes apart is not the same boot", got)
	}
}

func TestSummarize(t *testing.T) {
	ranked := byUptime([]Boot{
		{Boot: at("2026-07-08 22:53:00"), Uptime: 400 * time.Hour, Clean: true, CleanKnown: true},
		{Boot: at("2026-08-19 18:10:00"), Uptime: 200 * time.Hour, Current: true},
		{Boot: at("2026-08-07 20:33:00"), Uptime: 300 * time.Hour, CleanKnown: true},
		{Boot: at("2026-08-05 08:14:00"), Uptime: 50 * time.Hour},
	})

	sum := summarize(ranked)
	if sum.Total != 4 {
		t.Errorf("total = %d, want 4", sum.Total)
	}
	if sum.CurrentRank != 3 {
		t.Errorf("current rank = %d, want 3", sum.CurrentRank)
	}
	if sum.ToNextRank != 100*time.Hour {
		t.Errorf("to next rank = %v, want 100h", sum.ToNextRank)
	}
	if sum.ToRecord != 200*time.Hour {
		t.Errorf("to record = %v, want 200h", sum.ToRecord)
	}
	if sum.Unclean != 1 {
		t.Errorf("unclean = %d, want 1 — the unknown-ending boot must not count", sum.Unclean)
	}
	if !sum.Since.Equal(at("2026-07-08 22:53:00")) {
		t.Errorf("since = %v, want the earliest boot", sum.Since)
	}
}

func TestFormatDuration(t *testing.T) {
	cases := []struct {
		in   time.Duration
		want string
	}{
		{16*24*time.Hour + 11*time.Hour + 46*time.Minute, "16d 11h 46m"},
		{11*time.Hour + 15*time.Minute, "11h 15m"},
		{45 * time.Second, "0m"},
		{-time.Hour, "0m"},
		{24 * time.Hour, "1d 0h 0m"},
	}
	for _, c := range cases {
		if got := formatDuration(c.in); got != c.want {
			t.Errorf("formatDuration(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestStatus(t *testing.T) {
	cases := []struct {
		b    Boot
		want string
	}{
		{Boot{Current: true}, "current"},
		{Boot{Clean: true, CleanKnown: true}, "clean"},
		{Boot{CleanKnown: true}, "unclean"},
		{Boot{}, "unknown"},
	}
	for _, c := range cases {
		if got := status(c.b); got != c.want {
			t.Errorf("status(%+v) = %q, want %q", c.b, got, c.want)
		}
	}
}

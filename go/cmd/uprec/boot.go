package main

import (
	"fmt"
	"sort"
	"strings"
	"time"
)

// Boot is one boot session: when the machine came up, how long it stayed
// up, and how that run ended.
type Boot struct {
	Boot    time.Time
	Uptime  time.Duration
	End     time.Time // zero while the run is still in progress
	Current bool
	Clean   bool // a matching shutdown record was found
	// CleanKnown separates "ended cleanly" from "no source could say".
	// uptimed's format does not record how a run ended, so a history
	// recovered from it alone must not claim every boot was clean.
	CleanKnown bool
	System     string
	Source     string // live, wtmp, uptimed, state
}

// eventKind distinguishes the two record types every platform's login
// database agrees on: the machine came up, or it was told to go down.
type eventKind int

const (
	eventBoot eventKind = iota
	eventShutdown
)

// event is one raw record from a login database, before boots and
// shutdowns are paired into sessions.
type event struct {
	When time.Time
	Kind eventKind
}

// pairEvents turns a raw event stream into boot sessions. A boot ends at
// the next event of any kind: a shutdown means a clean stop, another boot
// means the machine went down without recording one (a crash, a power
// cut, or a hard reset). A trailing boot with nothing after it is the run
// still in progress.
func pairEvents(events []event, now time.Time) []Boot {
	sorted := make([]event, len(events))
	copy(sorted, events)
	// Shutdown sorts before boot on an exact tie: a reboot logged in the
	// same second as the shutdown that preceded it is still a clean stop.
	sort.SliceStable(sorted, func(i, j int) bool {
		if sorted[i].When.Equal(sorted[j].When) {
			return sorted[i].Kind == eventShutdown && sorted[j].Kind == eventBoot
		}
		return sorted[i].When.Before(sorted[j].When)
	})
	sorted = dedupeEvents(sorted)

	var boots []Boot
	for i, e := range sorted {
		if e.Kind != eventBoot {
			continue
		}
		if i == len(sorted)-1 {
			boots = append(boots, Boot{
				Boot:    e.When,
				Uptime:  now.Sub(e.When),
				Current: true,
				Source:  "wtmp",
			})
			continue
		}
		next := sorted[i+1]
		boots = append(boots, Boot{
			Boot:       e.When,
			Uptime:     next.When.Sub(e.When),
			End:        next.When,
			Clean:      next.Kind == eventShutdown,
			CleanKnown: true,
			Source:     "wtmp",
		})
	}
	return boots
}

// dedupeEvents drops repeats of the same kind logged within a minute of
// each other, which some shutdown paths write more than once.
func dedupeEvents(sorted []event) []event {
	out := make([]event, 0, len(sorted))
	for _, e := range sorted {
		if n := len(out); n > 0 && out[n-1].Kind == e.Kind &&
			e.When.Sub(out[n-1].When) < time.Minute {
			continue
		}
		out = append(out, e)
	}
	return out
}

// mergeTolerance is how far apart two records of the same boot may sit
// before they count as different boots. uptimed derives its boot epoch by
// subtracting uptime from the current time, so its timestamps drift a
// second or two from the login database's.
const mergeTolerance = 2 * time.Minute

// mergeBoots folds every source into one history, combining records that
// describe the same boot.
func mergeBoots(sets ...[]Boot) []Boot {
	var all []Boot
	for _, s := range sets {
		all = append(all, s...)
	}
	sort.SliceStable(all, func(i, j int) bool { return all[i].Boot.Before(all[j].Boot) })

	out := make([]Boot, 0, len(all))
	for _, b := range all {
		if n := len(out); n > 0 && b.Boot.Sub(out[n-1].Boot) <= mergeTolerance {
			out[n-1] = combine(out[n-1], b)
			continue
		}
		out = append(out, b)
	}
	return out
}

// sourceRank orders sources by how precisely they timestamp a boot. The
// running kernel is exact; stored records keep whole seconds; macOS's
// last(1) prints whole minutes, so a boot recovered from it can sit up to
// a minute early.
func sourceRank(source string) int {
	switch source {
	case "live":
		return 3
	case "state", "uptimed":
		return 2
	default:
		return 1
	}
}

// combine reconciles two records of the same boot. The more precise
// source's timestamps win outright rather than being averaged or maxed
// against a coarser one, and every flag is preserved from whichever
// source knew about it.
func combine(a, b Boot) Boot {
	hi, lo := a, b
	if sourceRank(b.Source) > sourceRank(a.Source) {
		hi, lo = b, a
	}

	out := hi
	// A stored record is only a snapshot, taken while the run was still
	// going, so a longer uptime is the better estimate — unless the
	// precise source is the running kernel, which already knows exactly.
	if lo.Uptime > out.Uptime && hi.Source != "live" {
		out.Uptime, out.End = lo.Uptime, lo.End
	}
	out.Current = a.Current || b.Current
	if !out.CleanKnown && lo.CleanKnown {
		out.Clean, out.CleanKnown = lo.Clean, true
	}
	if out.System == "" {
		out.System = lo.System
	}
	if out.Current {
		out.End = time.Time{}
	}
	return out
}

// byUptime ranks sessions longest-first, the order uprecords displays.
func byUptime(boots []Boot) []Boot {
	out := make([]Boot, len(boots))
	copy(out, boots)
	sort.SliceStable(out, func(i, j int) bool { return out[i].Uptime > out[j].Uptime })
	return out
}

// Summary is the at-a-glance view: where the current run sits, what it
// has to beat, and how often this machine goes down without warning.
type Summary struct {
	Total       int
	Unclean     int
	CurrentRank int           // 1-based; 0 when there is no current run
	Record      Boot          // longest session on record
	ToNextRank  time.Duration // how long until the current run climbs one place
	ToRecord    time.Duration // how long until it takes first place
	Since       time.Time     // start of the earliest session on record
}

func summarize(ranked []Boot) Summary {
	s := Summary{Total: len(ranked)}
	if len(ranked) == 0 {
		return s
	}
	s.Record = ranked[0]
	s.Since = ranked[0].Boot

	for i, b := range ranked {
		if b.Boot.Before(s.Since) {
			s.Since = b.Boot
		}
		if !b.Current && b.CleanKnown && !b.Clean {
			s.Unclean++
		}
		if b.Current {
			s.CurrentRank = i + 1
			if i > 0 {
				s.ToNextRank = ranked[i-1].Uptime - b.Uptime
				s.ToRecord = ranked[0].Uptime - b.Uptime
			}
		}
	}
	return s
}

// formatDuration renders a span as "16d 11h 46m", dropping leading units
// that are zero so short runs stay readable.
func formatDuration(d time.Duration) string {
	if d < 0 {
		d = 0
	}
	total := int64(d / time.Second)
	days := total / 86400
	hours := (total % 86400) / 3600
	minutes := (total % 3600) / 60

	var parts []string
	if days > 0 {
		parts = append(parts, fmt.Sprintf("%dd", days))
	}
	if hours > 0 || days > 0 {
		parts = append(parts, fmt.Sprintf("%dh", hours))
	}
	parts = append(parts, fmt.Sprintf("%dm", minutes))
	return strings.Join(parts, " ")
}

const stampFormat = "2006-01-02 15:04"

// status labels how a run ended, for the table's last column.
func status(b Boot) string {
	switch {
	case b.Current:
		return "current"
	case !b.CleanKnown:
		return "unknown"
	case b.Clean:
		return "clean"
	default:
		return "unclean"
	}
}

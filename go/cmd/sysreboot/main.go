// Command sysreboot is an ultra-fast reboot advisor: a one-or-two-line
// report on whether this machine needs a restart, with no heavyweight
// dependencies and (on Linux) an authoritative signal instead of a guess.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
)

// Stats is gathered per-platform (platform_darwin.go / platform_linux.go)
// and scored/formatted here.
type Stats struct {
	UptimeSeconds          float64
	Load1, Load5, Load15   float64
	Cores                  int
	MemTotal, MemAvailable uint64 // bytes
	SwapTotal, SwapUsed    uint64 // bytes
	Compressed             uint64 // bytes held by the macOS memory compressor (0 elsewhere)
	Pressure               string // kernel's own verdict: "normal", "warn", "critical", or "" if unknown
	RebootRequired         bool   // authoritative signal (Linux: /var/run/reboot-required)
	RebootReason           string
}

func main() {
	oneline := flag.Bool("1", false, "Squash the report onto a single line")
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	flag.BoolVar(oneline, "oneline", false, "Squash the report onto a single line (alias for -1)")
	flag.Parse()

	stats, err := gather()
	if err != nil {
		fmt.Fprintf(os.Stderr, "sysreboot: %v\n", err)
		os.Exit(3)
	}

	score := rebootScore(stats)
	emoji, label := verdict(score, stats.RebootRequired)

	if *jsonOut {
		printJSON(stats, score, label)
		os.Exit(exitCode(score, stats.RebootRequired))
	}

	printReport(stats, score, emoji, label, *oneline)
	os.Exit(exitCode(score, stats.RebootRequired))
}

// rebootScore mirrors the old syscheck.py heuristic, with memory pressure
// weighted heavily enough to reach "advised" on its own: uptime up to 25,
// load up to 25, available memory up to 20, swap up to 60, kernel pressure
// up to 40. Swap is measured against RAM rather than swap total, because
// macOS grows its swap file on demand — "67% of swap used" says nothing,
// while "6 GB swapped on an 8 GB machine" means it will freeze. Kept
// deliberately simple — a fallback for when there's no authoritative
// signal, not a precision instrument.
func rebootScore(s *Stats) int {
	score := 0.0

	days := s.UptimeSeconds / 86400.0
	if days > 30 {
		days = 30
	}
	score += days / 30.0 * 25.0

	cores := float64(s.Cores)
	if cores < 1 {
		cores = 1
	}
	if s.Load1 > cores {
		score += 15
	} else if s.Load1 > 0.75*cores {
		score += 10
	}
	if s.Load5 > cores {
		score += 10
	}

	if s.MemTotal > 0 {
		freeRatio := float64(s.MemAvailable) / float64(s.MemTotal)
		if freeRatio < 0.10 {
			score += 20
		} else if freeRatio < 0.20 {
			score += 10
		}
	}

	switch ratio := swapRAMRatio(s); {
	case ratio >= swapHeavyRatio:
		score += 60
	case ratio >= swapHighRatio:
		score += 35
	case ratio >= swapTightRatio:
		score += 15
	}

	switch s.Pressure {
	case "critical":
		score += 40
	case "warn":
		score += 15
	}

	if score > 100 {
		score = 100
	}
	return int(score + 0.5)
}

// Swap-to-RAM thresholds: a quarter of RAM swapped is getting tight, half
// is where an 8 GB Mac starts stalling on wake, three quarters is freezing.
const (
	swapTightRatio = 0.25
	swapHighRatio  = 0.50
	swapHeavyRatio = 0.75
)

func swapRAMRatio(s *Stats) float64 {
	if s.MemTotal == 0 {
		return 0
	}
	return float64(s.SwapUsed) / float64(s.MemTotal)
}

// memWarnings names the memory limits that are likely causing trouble,
// most serious first, each with what to do about it. Empty when memory
// looks healthy.
func memWarnings(s *Stats) []string {
	var out []string
	switch s.Pressure {
	case "critical":
		out = append(out, "kernel reports critical memory pressure — quit big apps now")
	case "warn":
		out = append(out, "kernel reports memory pressure")
	}
	ratio := swapRAMRatio(s)
	swapped := fmt.Sprintf("%s swapped (%.0f%% of RAM)", byteSize(s.SwapUsed), ratio*100)
	switch {
	case ratio >= swapHeavyRatio:
		out = append(out, swapped+" — expect freezes; quit big apps or reboot")
	case ratio >= swapHighRatio:
		out = append(out, swapped+" — likely sluggish; quit big apps (run `mem`)")
	case ratio >= swapTightRatio:
		out = append(out, swapped+" — getting tight")
	}
	if s.MemTotal > 0 && float64(s.MemAvailable)/float64(s.MemTotal) < 0.10 {
		out = append(out, fmt.Sprintf("only %d%% of RAM available", freePercent(s.MemAvailable, s.MemTotal)))
	}
	return out
}

func verdict(score int, rebootRequired bool) (emoji, label string) {
	ok, warn, crit := "✅", "⚠️ ", "🔴"
	if !utf8Locale() {
		ok, warn, crit = "[OK]", "[!] ", "[X]"
	}

	if rebootRequired {
		return crit, "REBOOT REQUIRED"
	}
	switch {
	case score < 30:
		return ok, "No reboot needed"
	case score < 70:
		return warn, "Reboot optional"
	default:
		return crit, "Reboot advised"
	}
}

// separator returns the stats-line joiner: a middle dot when the locale
// can render it, a plain hyphen otherwise (common on minimal headless
// installs where LANG is left at "C"/"POSIX").
func separator() string {
	if utf8Locale() {
		return " · "
	}
	return " - "
}

// dash separates a verdict from its detail reason (e.g. "REBOOT REQUIRED —
// pending kernel update"). Same ASCII fallback as separator, but kept
// distinct so the UTF-8 output can still visually tell the two apart.
func dash() string {
	if utf8Locale() {
		return " — "
	}
	return " - "
}

// utf8Locale checks LC_ALL/LC_CTYPE/LANG in POSIX priority order for a
// UTF-8 locale. Not foolproof (a UTF-8-capable terminal with a non-UTF-8
// LANG will still get the ASCII fallback), but matches what most CLI
// tools (git, ripgrep, htop) already use to make this call.
func utf8Locale() bool {
	for _, key := range []string{"LC_ALL", "LC_CTYPE", "LANG"} {
		if v := os.Getenv(key); v != "" {
			return strings.Contains(strings.ToUpper(v), "UTF-8") ||
				strings.Contains(strings.ToUpper(v), "UTF8")
		}
	}
	return false
}

func exitCode(score int, rebootRequired bool) int {
	switch {
	case rebootRequired || score >= 70:
		return 2
	case score >= 30:
		return 1
	default:
		return 0
	}
}

func printReport(s *Stats, score int, emoji, label string, oneline bool) {
	sep := separator()

	headline := fmt.Sprintf("%s %s (score %d%%)", emoji, label, score)
	if s.RebootRequired && s.RebootReason != "" {
		headline = fmt.Sprintf("%s %s%s%s", emoji, label, dash(), s.RebootReason)
	}

	stats := fmt.Sprintf(
		"up %s%sload %.2f/%.2f/%.2f (%d cores)%smem %d%% free%s",
		formatDuration(s.UptimeSeconds), sep,
		s.Load1, s.Load5, s.Load15,
		s.Cores, sep,
		freePercent(s.MemAvailable, s.MemTotal),
		swapSuffix(s.SwapUsed, s.SwapTotal),
	)

	warnings := memWarnings(s)
	warnMark := "⚠️ "
	if !utf8Locale() {
		warnMark = "[!] "
	}

	if oneline {
		line := headline + sep + stats
		if len(warnings) > 0 {
			line += sep + warnMark + warnings[0]
		}
		fmt.Println(line)
		return
	}
	fmt.Println(headline)
	fmt.Println(stats)
	for _, w := range warnings {
		fmt.Println(warnMark + w)
	}
}

func printJSON(s *Stats, score int, label string) {
	out := map[string]any{
		"uptime_seconds":  int64(s.UptimeSeconds),
		"load1":           s.Load1,
		"load5":           s.Load5,
		"load15":          s.Load15,
		"cores":           s.Cores,
		"mem_total":       s.MemTotal,
		"mem_available":   s.MemAvailable,
		"swap_total":      s.SwapTotal,
		"swap_used":       s.SwapUsed,
		"compressed":      s.Compressed,
		"mem_pressure":    s.Pressure,
		"warnings":        nonNil(memWarnings(s)),
		"reboot_required": s.RebootRequired,
		"reboot_reason":   s.RebootReason,
		"score":           score,
		"verdict":         label,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}

func freePercent(available, total uint64) int {
	if total == 0 {
		return 0
	}
	return int(float64(available) / float64(total) * 100)
}

// swapSuffix shows swap as an absolute size: on macOS the swap total
// grows on demand, so a percentage of it is meaningless.
func swapSuffix(used, total uint64) string {
	if total == 0 && used == 0 {
		return ""
	}
	return fmt.Sprintf("%sswap %s", separator(), byteSize(used))
}

func nonNil(list []string) []string {
	if list == nil {
		return []string{}
	}
	return list
}

var siUnits = []string{"B", "KB", "MB", "GB", "TB"}

func byteSize(size uint64) string {
	f := float64(size)
	for i, unit := range siUnits {
		if f < 1000 || i == len(siUnits)-1 {
			if i == 0 {
				return fmt.Sprintf("%d %s", size, unit)
			}
			return fmt.Sprintf("%.1f %s", f, unit)
		}
		f /= 1000
	}
	return ""
}

func formatDuration(seconds float64) string {
	total := int64(seconds)
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
	if days == 0 {
		parts = append(parts, fmt.Sprintf("%dm", minutes))
	}
	return strings.Join(parts, " ")
}

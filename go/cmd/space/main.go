// Command space is a fast disk-usage summary: total/used/free per mount
// point with a colored terminal table (or a quiet, script-friendly line
// format), replacing the old Python `space` tool's Rich-table startup cost.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// row is one resolved mount point plus the raw stats needed to sort,
// dedupe, and render it.
type row struct {
	path  string
	total uint64
	free  uint64
	dev   uint64
}

func main() {
	sizeSort := flag.Bool("s", false, "Sort by size, largest first")
	flag.BoolVar(sizeSort, "size", false, "Sort by size, largest first (alias for -s)")
	quiet := flag.Bool("q", false, "Plain pipe-delimited output, no table or color")
	flag.BoolVar(quiet, "quiet", false, "Plain pipe-delimited output (alias for -q)")
	all := flag.Bool("a", false, "Show all mount points, including duplicates")
	flag.BoolVar(all, "all", false, "Show all mount points (alias for -a)")
	showTotal := flag.Bool("t", false, "Show a combined totals row")
	flag.BoolVar(showTotal, "total", false, "Show a combined totals row (alias for -t)")
	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	flag.Parse()

	rows := gatherRows(resolvePaths(flag.Args()))

	if *sizeSort {
		sort.SliceStable(rows, func(i, j int) bool { return rows[i].total > rows[j].total })
	} else {
		sort.SliceStable(rows, func(i, j int) bool { return rows[i].path < rows[j].path })
	}

	if !*all {
		rows = dedupeByDevice(rows)
	}

	var totalRow *row
	if *showTotal && len(rows) > 1 {
		t := row{path: "TOTAL"}
		for _, r := range rows {
			t.total += r.total
			t.free += r.free
		}
		totalRow = &t
	}

	if *jsonOut {
		printJSON(rows, totalRow)
		return
	}

	if *quiet || !isTerminal() {
		printPlain(rows, totalRow)
		return
	}
	printTable(rows, totalRow)
}

func printJSON(rows []row, totalRow *row) {
	mounts := make([]map[string]any, 0, len(rows))
	for _, r := range rows {
		mounts = append(mounts, jsonRow(r))
	}
	out := map[string]any{"mounts": mounts}
	if totalRow != nil {
		out["total"] = jsonRow(*totalRow)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}

func jsonRow(r row) map[string]any {
	used := r.total - r.free
	return map[string]any{
		"path":        r.path,
		"total_bytes": r.total,
		"used_bytes":  used,
		"free_bytes":  r.free,
		"usage_pct":   percentOf(used, r.total),
	}
}

// resolvePaths mirrors the old syscheck.py-era space.py behaviour: explicit
// paths that exist win outright; otherwise explicit args are treated as
// substrings to match against /mnt/* entries; with no args at all, every
// /mnt/* entry plus / is used.
func resolvePaths(argPaths []string) []string {
	return resolvePathsFrom("/mnt", argPaths)
}

func resolvePathsFrom(mntDir string, argPaths []string) []string {
	var mounts []string
	if entries, err := os.ReadDir(mntDir); err == nil {
		for _, e := range entries {
			mounts = append(mounts, filepath.Join(mntDir, e.Name()))
		}
	}

	var found []string
	for _, p := range argPaths {
		if _, err := os.Stat(p); err == nil {
			found = append(found, p)
		}
	}

	if len(found) == 0 && len(argPaths) > 0 {
		for _, m := range mounts {
			for _, needle := range argPaths {
				if strings.Contains(m, needle) {
					found = append(found, m)
					break
				}
			}
		}
	}

	if len(found) == 0 {
		found = append(mounts, "/")
	}

	return found
}

func gatherRows(paths []string) []row {
	rows := make([]row, 0, len(paths))
	for _, p := range paths {
		st, err := statfs(p)
		if err != nil {
			continue
		}
		rows = append(rows, row{path: p, total: st.total, free: st.free, dev: st.dev})
	}
	return rows
}

// dedupeByDevice keeps the first row seen per device, so callers should
// sort before calling this if sort order should decide which path "wins"
// for a given device (matches the Python tool's sort-then-dedupe order).
func dedupeByDevice(rows []row) []row {
	seen := make(map[uint64]struct{}, len(rows))
	out := make([]row, 0, len(rows))
	for _, r := range rows {
		if _, ok := seen[r.dev]; ok {
			continue
		}
		seen[r.dev] = struct{}{}
		out = append(out, r)
	}
	return out
}

func percentOf(used, total uint64) float64 {
	if total == 0 {
		return 0
	}
	return float64(used) / float64(total) * 100
}

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

// utf8Locale checks LC_ALL/LC_CTYPE/LANG in POSIX priority order for a
// UTF-8 locale, same heuristic as sysreboot uses for its emoji fallback.
func utf8Locale() bool {
	for _, key := range []string{"LC_ALL", "LC_CTYPE", "LANG"} {
		if v := os.Getenv(key); v != "" {
			return strings.Contains(strings.ToUpper(v), "UTF-8") ||
				strings.Contains(strings.ToUpper(v), "UTF8")
		}
	}
	return false
}

func printPlain(rows []row, totalRow *row) {
	for _, r := range rows {
		printPlainRow(r)
	}
	if totalRow != nil {
		fmt.Println(strings.Repeat("─", 21) + "┼" + strings.Repeat("─", 12) + "┼" +
			strings.Repeat("─", 12) + "┼" + strings.Repeat("─", 12) + "┼" + strings.Repeat("─", 7))
		printPlainRow(*totalRow)
	}
}

func printPlainRow(r row) {
	used := r.total - r.free
	pct := percentOf(used, r.total)
	fmt.Printf("%-20s | %10s | %10s | %10s | %5.2f%%\n",
		r.path, byteSize(r.total), byteSize(used), byteSize(r.free), pct)
}

var siUnits = []string{"bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"}

// byteSize formats a byte count the same way the Python bytes.byte_size()
// helper does at its default base=1000: whole bytes below 1000, otherwise
// two decimals with thousands separators at the largest unit that keeps
// the value under 1000.
func byteSize(size uint64) string {
	f := float64(size)
	for i, unit := range siUnits {
		if f < 1000 || i == len(siUnits)-1 {
			if unit == "bytes" {
				if size == 1 {
					return "1 byte"
				}
				return fmt.Sprintf("%d bytes", size)
			}
			return commaFloat(f, 2) + " " + unit
		}
		f /= 1000
	}
	return ""
}

func commaFloat(f float64, decimals int) string {
	s := strconv.FormatFloat(f, 'f', decimals, 64)
	neg := strings.HasPrefix(s, "-")
	if neg {
		s = s[1:]
	}
	intPart, fracPart, hasFrac := strings.Cut(s, ".")

	var b strings.Builder
	n := len(intPart)
	for i, c := range intPart {
		if i > 0 && (n-i)%3 == 0 {
			b.WriteByte(',')
		}
		b.WriteRune(c)
	}
	out := b.String()
	if hasFrac {
		out += "." + fracPart
	}
	if neg {
		out = "-" + out
	}
	return out
}

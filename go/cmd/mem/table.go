package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

const colorReset = "\x1b[0m"

// colors mirrors the palette space/main.go uses, so every rogkit Go table
// looks like part of the same tool.
type colors struct {
	name, ok, warn, crit, header string
}

func trueColorPalette() colors {
	return colors{
		name:   "\x1b[1;38;2;255;128;191m", // bold #ff80bf
		ok:     "\x1b[38;2;78;205;196m",    // #4ecdc4
		warn:   "\x1b[38;2;244;211;94m",    // #f4d35e
		crit:   "\x1b[1;38;2;255;107;107m", // bold #ff6b6b
		header: "\x1b[1;36m",               // bold cyan
	}
}

func basicPalette() colors {
	return colors{
		name:   "\x1b[1;35m",
		ok:     "\x1b[32m",
		warn:   "\x1b[33m",
		crit:   "\x1b[1;31m",
		header: "\x1b[1;36m",
	}
}

func supportsTrueColor() bool {
	ct := strings.ToLower(os.Getenv("COLORTERM"))
	if ct == "truecolor" || ct == "24bit" {
		return true
	}
	switch os.Getenv("TERM") {
	case "linux", "dumb", "":
		return false
	default:
		return true
	}
}

func activePalette() colors {
	if supportsTrueColor() {
		return trueColorPalette()
	}
	return basicPalette()
}

func utf8Locale() bool {
	for _, key := range []string{"LC_ALL", "LC_CTYPE", "LANG"} {
		if v := os.Getenv(key); v != "" {
			return strings.Contains(strings.ToUpper(v), "UTF-8") ||
				strings.Contains(strings.ToUpper(v), "UTF8")
		}
	}
	return false
}

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

// tableRow is one rendered line: formatted cells plus a parallel ANSI style
// per cell (empty string means no color).
type tableRow struct {
	cells      []string
	cellStyles []string
}

// severityStyle picks a color by %MEM the same way space picks by %usage:
// green under 10%, yellow 10-25%, red above.
func severityStyle(c colors, pctMem float64) string {
	switch {
	case pctMem >= 25:
		return c.crit
	case pctMem >= 10:
		return c.warn
	default:
		return c.ok
	}
}

func newSummaryHeader(c colors) tableRow {
	return tableRow{
		cells:      []string{"Name", "Procs", "Mem", "%Mem"},
		cellStyles: []string{c.header, c.header, c.header, c.header},
	}
}

var summaryRightAlign = []bool{false, true, true, true}

func formatSummaryRow(c colors, g group, totalMem uint64) tableRow {
	pct := percentOf(g.rss, totalMem)
	style := severityStyle(c, pct)
	return tableRow{
		cells:      []string{g.name, strconv.Itoa(g.procs), byteSize(g.rss), fmt.Sprintf("%.1f%%", pct)},
		cellStyles: []string{c.name, style, style, style},
	}
}

func newFilteredHeader(c colors) tableRow {
	return tableRow{
		cells:      []string{"PID", "Name", "Mem", "%Mem"},
		cellStyles: []string{c.header, c.header, c.header, c.header},
	}
}

var filteredRightAlign = []bool{true, false, true, true}

func formatFilteredRow(c colors, p proc, totalMem uint64) tableRow {
	pct := percentOf(p.rss, totalMem)
	style := severityStyle(c, pct)
	return tableRow{
		cells:      []string{strconv.Itoa(p.pid), p.name, byteSize(p.rss), fmt.Sprintf("%.1f%%", pct)},
		cellStyles: []string{c.name, style, style, style},
	}
}

func formatTotalRow(c colors, labelCol int, label string, rss uint64, totalMem uint64, cols int) tableRow {
	pct := percentOf(rss, totalMem)
	cells := make([]string, cols)
	cells[labelCol] = label
	cells[cols-2] = byteSize(rss)
	cells[cols-1] = fmt.Sprintf("%.1f%%", pct)
	styles := make([]string, cols)
	for i := range styles {
		styles[i] = c.header
	}
	return tableRow{cells: cells, cellStyles: styles}
}

// boxSet is the set of border glyphs for one rendering mode: full
// box-drawing when the locale is UTF-8, plain ASCII otherwise.
type boxSet struct {
	vert                       string
	topL, topM, topR, topH     string
	headL, headM, headR, headH string
	secL, secM, secR, secH     string
	botL, botM, botR, botH     string
}

func newBoxSet(utf8 bool) boxSet {
	if !utf8 {
		return boxSet{
			vert: "|",
			topL: "+", topM: "+", topR: "+", topH: "-",
			headL: "+", headM: "+", headR: "+", headH: "-",
			secL: "+", secM: "+", secR: "+", secH: "-",
			botL: "+", botM: "+", botR: "+", botH: "-",
		}
	}
	return boxSet{
		vert: "│",
		topL: "┏", topM: "┳", topR: "┓", topH: "━",
		headL: "┡", headM: "╇", headR: "┩", headH: "━",
		secL: "├", secM: "┼", secR: "┤", secH: "─",
		botL: "└", botM: "┴", botR: "┘", botH: "─",
	}
}

func horizontalLine(widths []int, l, m, r, h string) string {
	parts := make([]string, len(widths))
	for i, w := range widths {
		parts[i] = strings.Repeat(h, w+2)
	}
	return l + strings.Join(parts, m) + r
}

func dataLine(tr tableRow, widths []int, rightAlign []bool, vert string) string {
	var b strings.Builder
	b.WriteString(vert)
	for i, c := range tr.cells {
		w := widths[i]
		pad := w - len([]rune(c))
		var padded string
		if rightAlign[i] {
			padded = strings.Repeat(" ", pad) + c
		} else {
			padded = c + strings.Repeat(" ", pad)
		}
		cellText := " " + padded + " "
		if style := tr.cellStyles[i]; style != "" {
			cellText = style + cellText + colorReset
		}
		b.WriteString(cellText)
		b.WriteString(vert)
	}
	return b.String()
}

func columnWidths(header tableRow, rows []tableRow) []int {
	widths := make([]int, len(header.cells))
	for i, c := range header.cells {
		widths[i] = len([]rune(c))
	}
	for _, tr := range rows {
		for i, c := range tr.cells {
			if l := len([]rune(c)); l > widths[i] {
				widths[i] = l
			}
		}
	}
	return widths
}

func printTable(header tableRow, rows []tableRow, hasTotal bool, rightAlign []bool) {
	widths := columnWidths(header, rows)
	b := newBoxSet(utf8Locale())

	fmt.Println(horizontalLine(widths, b.topL, b.topM, b.topR, b.topH))
	fmt.Println(dataLine(header, widths, rightAlign, b.vert))
	fmt.Println(horizontalLine(widths, b.headL, b.headM, b.headR, b.headH))

	for i, tr := range rows {
		if hasTotal && i == len(rows)-1 && len(rows) > 1 {
			fmt.Println(horizontalLine(widths, b.secL, b.secM, b.secR, b.secH))
		}
		fmt.Println(dataLine(tr, widths, rightAlign, b.vert))
	}

	fmt.Println(horizontalLine(widths, b.botL, b.botM, b.botR, b.botH))
}

func printPlain(header tableRow, rows []tableRow, hasTotal bool) {
	for i, tr := range rows {
		if hasTotal && i == len(rows)-1 && len(rows) > 1 {
			fmt.Println(strings.Repeat("-", 40))
		}
		fmt.Println(strings.Join(tr.cells, "\t"))
	}
}

func percentOf(part, total uint64) float64 {
	if total == 0 {
		return 0
	}
	return float64(part) / float64(total) * 100
}

var siUnits = []string{"bytes", "KB", "MB", "GB", "TB", "PB"}

// byteSize formats a byte count the same way space's byteSize() does:
// whole bytes below 1000, otherwise two decimals at the largest unit that
// keeps the value under 1000.
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
			return strconv.FormatFloat(f, 'f', 2, 64) + " " + unit
		}
		f /= 1000
	}
	return ""
}

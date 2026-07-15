package main

import (
	"fmt"
	"os"
	"strings"
)

const colorReset = "\x1b[0m"

// colors are 24-bit ANSI codes matching the exact hex values the Python
// tool's Rich theme used (Theme({"magenta": "bold #ff80bf", "green":
// "#4ecdc4", "yellow": "#f4d35e", "red": "#ff6b6b"})) — the standard
// 16-color ANSI names (plain green/yellow/red/magenta) are a much harsher
// palette and were reported hard to read next to the original.
type colors struct {
	path, ok, warn, crit, header string
}

func trueColorPalette() colors {
	return colors{
		path:   "\x1b[1;38;2;255;128;191m", // bold #ff80bf
		ok:     "\x1b[38;2;78;205;196m",    // #4ecdc4
		warn:   "\x1b[38;2;244;211;94m",    // #f4d35e
		crit:   "\x1b[1;38;2;255;107;107m", // bold #ff6b6b
		header: "\x1b[1;36m",               // bold cyan, unchanged from Rich's default header_style
	}
}

// basicPalette is the fallback for terminals that can't do 24-bit color
// (e.g. the Pi's raw TERM=linux console) — closest standard ANSI colors,
// still distinct from each other even if less true to the original hues.
func basicPalette() colors {
	return colors{
		path:   "\x1b[1;35m",
		ok:     "\x1b[32m",
		warn:   "\x1b[33m",
		crit:   "\x1b[1;31m",
		header: "\x1b[1;36m",
	}
}

// supportsTrueColor mirrors the common COLORTERM/TERM heuristic (bat,
// delta, starship): trust an explicit COLORTERM=truecolor/24bit, then
// assume yes except on the raw Linux console or a dumb terminal, both of
// which cap out at the standard 16-color palette.
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

// tableRow is one rendered line: five formatted cells plus a parallel
// ANSI style to apply per cell (empty string means no color).
type tableRow struct {
	cells      []string
	cellStyles []string
}

func newHeaderRow(c colors) tableRow {
	return tableRow{
		cells:      []string{"Path", "Total", "Used", "Free", "Usage"},
		cellStyles: []string{c.header, c.header, c.header, c.header, c.header},
	}
}

var rightAlign = []bool{false, true, true, true, true}

func formatRow(c colors, path string, total, free uint64) tableRow {
	used := total - free
	pct := percentOf(used, total)
	severity := c.ok
	switch {
	case pct >= 95:
		severity = c.crit
	case pct >= 80:
		severity = c.warn
	}
	return tableRow{
		cells:      []string{path, byteSize(total), byteSize(used), byteSize(free), fmt.Sprintf("%.2f%%", pct)},
		cellStyles: []string{c.path, severity, severity, severity, severity},
	}
}

func formatTotalRow(c colors, path string, total, free uint64) tableRow {
	tr := formatRow(c, path, total, free)
	for i := range tr.cellStyles {
		tr.cellStyles[i] = c.header
	}
	return tr
}

// boxSet is the set of border glyphs for one rendering mode: full
// box-drawing when the locale is UTF-8, plain ASCII otherwise (same
// fallback approach sysreboot uses for its emoji/separator output).
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

func dataLine(tr tableRow, widths []int, vert string) string {
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

func printTable(rows []row, totalRow *row) {
	c := activePalette()

	trs := make([]tableRow, 0, len(rows)+1)
	for _, r := range rows {
		trs = append(trs, formatRow(c, r.path, r.total, r.free))
	}
	if totalRow != nil {
		trs = append(trs, formatTotalRow(c, totalRow.path, totalRow.total, totalRow.free))
	}

	header := newHeaderRow(c)
	widths := columnWidths(header, trs)
	b := newBoxSet(utf8Locale())

	fmt.Println(horizontalLine(widths, b.topL, b.topM, b.topR, b.topH))
	fmt.Println(dataLine(header, widths, b.vert))
	fmt.Println(horizontalLine(widths, b.headL, b.headM, b.headR, b.headH))

	for i, tr := range trs {
		if totalRow != nil && i == len(trs)-1 && len(trs) > 1 {
			fmt.Println(horizontalLine(widths, b.secL, b.secM, b.secR, b.secH))
		}
		fmt.Println(dataLine(tr, widths, b.vert))
	}

	fmt.Println(horizontalLine(widths, b.botL, b.botM, b.botR, b.botH))
}

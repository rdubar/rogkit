package main

import (
	"fmt"
	"strings"
)

const (
	colorReset    = "\x1b[0m"
	colorGreen    = "\x1b[32m"
	colorYellow   = "\x1b[33m"
	colorRedBold  = "\x1b[1;31m"
	colorCyanBold = "\x1b[1;36m"
	colorMagenta  = "\x1b[35m"
)

// tableRow is one rendered line: five formatted cells plus a parallel
// ANSI style to apply per cell (empty string means no color).
type tableRow struct {
	cells      []string
	cellStyles []string
}

var headerRow = tableRow{
	cells:      []string{"Path", "Total", "Used", "Free", "Usage"},
	cellStyles: []string{colorCyanBold, colorCyanBold, colorCyanBold, colorCyanBold, colorCyanBold},
}

var rightAlign = []bool{false, true, true, true, true}

func formatRow(path string, total, free uint64) tableRow {
	used := total - free
	pct := percentOf(used, total)
	severity := colorGreen
	switch {
	case pct >= 95:
		severity = colorRedBold
	case pct >= 80:
		severity = colorYellow
	}
	return tableRow{
		cells:      []string{path, byteSize(total), byteSize(used), byteSize(free), fmt.Sprintf("%.2f%%", pct)},
		cellStyles: []string{colorMagenta, severity, severity, severity, severity},
	}
}

func formatTotalRow(path string, total, free uint64) tableRow {
	tr := formatRow(path, total, free)
	for i := range tr.cellStyles {
		tr.cellStyles[i] = colorCyanBold
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

func columnWidths(rows []tableRow) []int {
	widths := make([]int, len(headerRow.cells))
	for i, c := range headerRow.cells {
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
	trs := make([]tableRow, 0, len(rows)+1)
	for _, r := range rows {
		trs = append(trs, formatRow(r.path, r.total, r.free))
	}
	if totalRow != nil {
		trs = append(trs, formatTotalRow(totalRow.path, totalRow.total, totalRow.free))
	}

	widths := columnWidths(trs)
	b := newBoxSet(utf8Locale())

	fmt.Println(horizontalLine(widths, b.topL, b.topM, b.topR, b.topH))
	fmt.Println(dataLine(headerRow, widths, b.vert))
	fmt.Println(horizontalLine(widths, b.headL, b.headM, b.headR, b.headH))

	for i, tr := range trs {
		if totalRow != nil && i == len(trs)-1 && len(trs) > 1 {
			fmt.Println(horizontalLine(widths, b.secL, b.secM, b.secR, b.secH))
		}
		fmt.Println(dataLine(tr, widths, b.vert))
	}

	fmt.Println(horizontalLine(widths, b.botL, b.botM, b.botR, b.botH))
}

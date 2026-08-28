package main

import (
	"fmt"
	"os"
	"strings"
)

const colorReset = "\x1b[0m"

// colors mirrors the palette space uses, so the two tools look like the
// same tool when they appear side by side in a primer run.
type colors struct {
	mark, ok, warn, crit, header string
}

func trueColorPalette() colors {
	return colors{
		mark:   "\x1b[1;38;2;255;128;191m", // bold #ff80bf
		ok:     "\x1b[38;2;78;205;196m",    // #4ecdc4
		warn:   "\x1b[38;2;244;211;94m",    // #f4d35e
		crit:   "\x1b[1;38;2;255;107;107m", // bold #ff6b6b
		header: "\x1b[1;36m",               // bold cyan
	}
}

// basicPalette is the fallback for terminals without 24-bit color, such
// as a Pi's raw TERM=linux console.
func basicPalette() colors {
	return colors{
		mark:   "\x1b[1;35m",
		ok:     "\x1b[32m",
		warn:   "\x1b[33m",
		crit:   "\x1b[1;31m",
		header: "\x1b[1;36m",
	}
}

// supportsTrueColor follows the usual COLORTERM/TERM heuristic.
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

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

// utf8Locale checks LC_ALL/LC_CTYPE/LANG in POSIX priority order, the
// same heuristic sysreboot and space use before emitting non-ASCII.
func utf8Locale() bool {
	for _, key := range []string{"LC_ALL", "LC_CTYPE", "LANG"} {
		if v := os.Getenv(key); v != "" {
			return strings.Contains(strings.ToUpper(v), "UTF-8") ||
				strings.Contains(strings.ToUpper(v), "UTF8")
		}
	}
	return false
}

func separator() string {
	if utf8Locale() {
		return " · "
	}
	return " - "
}

// marker flags the run in progress, the same "->" uprecords uses.
func marker(b Boot) string {
	if b.Current {
		return "->"
	}
	return "  "
}

type tableRow struct {
	cells      []string
	cellStyles []string
}

var rightAlign = []bool{false, true, false, false, false}

func newHeaderRow(c colors) tableRow {
	cells := []string{"Rank", "Uptime", "Booted", "Ended", "Status"}
	styles := make([]string, len(cells))
	for i := range styles {
		styles[i] = c.header
	}
	return tableRow{cells: cells, cellStyles: styles}
}

func formatRow(c colors, rank int, b Boot) tableRow {
	severity := c.ok
	switch status(b) {
	case "current":
		severity = c.mark
	case "unclean":
		severity = c.crit
	case "unknown":
		severity = c.warn
	}

	ended := "-"
	if !b.End.IsZero() {
		ended = b.End.Format(stampFormat)
	}

	return tableRow{
		cells: []string{
			fmt.Sprintf("%s %d", marker(b), rank),
			formatDuration(b.Uptime),
			b.Boot.Format(stampFormat),
			ended,
			status(b),
		},
		cellStyles: []string{severity, severity, severity, severity, severity},
	}
}

type boxSet struct {
	vert                       string
	topL, topM, topR, topH     string
	headL, headM, headR, headH string
	botL, botM, botR, botH     string
}

func newBoxSet(utf8 bool) boxSet {
	if !utf8 {
		return boxSet{
			vert: "|",
			topL: "+", topM: "+", topR: "+", topH: "-",
			headL: "+", headM: "+", headR: "+", headH: "-",
			botL: "+", botM: "+", botR: "+", botH: "-",
		}
	}
	return boxSet{
		vert: "│",
		topL: "┏", topM: "┳", topR: "┓", topH: "━",
		headL: "┡", headM: "╇", headR: "┩", headH: "━",
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
		pad := widths[i] - len([]rune(c))
		padded := c + strings.Repeat(" ", pad)
		if rightAlign[i] {
			padded = strings.Repeat(" ", pad) + c
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

func printTable(shown []Boot, sum Summary) {
	c := activePalette()

	trs := make([]tableRow, 0, len(shown))
	for i, b := range shown {
		trs = append(trs, formatRow(c, i+1, b))
	}

	header := newHeaderRow(c)
	widths := columnWidths(header, trs)
	box := newBoxSet(utf8Locale())

	fmt.Println(horizontalLine(widths, box.topL, box.topM, box.topR, box.topH))
	fmt.Println(dataLine(header, widths, box.vert))
	fmt.Println(horizontalLine(widths, box.headL, box.headM, box.headR, box.headH))
	for _, tr := range trs {
		fmt.Println(dataLine(tr, widths, box.vert))
	}
	fmt.Println(horizontalLine(widths, box.botL, box.botM, box.botR, box.botH))

	for _, line := range footerLines(sum) {
		fmt.Println(line)
	}
}

// footerLines report what the current run still has to beat, then the
// span and reliability of the history it is being judged against.
func footerLines(sum Summary) []string {
	sep := separator()
	var lines []string

	if sum.CurrentRank > 1 {
		lines = append(lines, fmt.Sprintf("%s to #%d%s%s to #1",
			formatDuration(sum.ToNextRank), sum.CurrentRank-1, sep,
			formatDuration(sum.ToRecord)))
	}

	tail := fmt.Sprintf("%s since %s", plural(sum.Total, "boot"), sum.Since.Format("2006-01-02"))
	if sum.Unclean > 0 {
		tail += fmt.Sprintf("%s%d unclean", sep, sum.Unclean)
	}
	return append(lines, tail)
}

func plural(n int, noun string) string {
	if n == 1 {
		return fmt.Sprintf("%d %s", n, noun)
	}
	return fmt.Sprintf("%d %ss", n, noun)
}

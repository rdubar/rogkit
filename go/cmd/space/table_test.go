package main

import "testing"

func TestFormatRowSeverity(t *testing.T) {
	c := trueColorPalette()
	cases := []struct {
		total, free uint64
		wantStyle   string
	}{
		{100, 50, c.ok},   // 50% used
		{100, 15, c.warn}, // 85% used
		{100, 2, c.crit},  // 98% used
	}
	for _, tc := range cases {
		tr := formatRow(c, "/x", tc.total, tc.free)
		if tr.cellStyles[1] != tc.wantStyle {
			t.Errorf("total=%d free=%d: got style %q, want %q", tc.total, tc.free, tr.cellStyles[1], tc.wantStyle)
		}
	}
}

func TestFormatTotalRowAllHeaderStyle(t *testing.T) {
	c := trueColorPalette()
	tr := formatTotalRow(c, "TOTAL", 100, 2)
	for i, style := range tr.cellStyles {
		if style != c.header {
			t.Errorf("cell %d: got style %q, want %q", i, style, c.header)
		}
	}
}

func TestColumnWidths(t *testing.T) {
	c := trueColorPalette()
	header := newHeaderRow(c)
	rows := []tableRow{
		formatRow(c, "/mnt/very-long-path-name", 100, 50),
	}
	widths := columnWidths(header, rows)
	if widths[0] != len("/mnt/very-long-path-name") {
		t.Fatalf("expected path column width to grow to fit content, got %d", widths[0])
	}
}

func TestHorizontalLineWidth(t *testing.T) {
	b := newBoxSet(true)
	line := horizontalLine([]int{3, 5}, b.topL, b.topM, b.topR, b.topH)
	// "┏" + 5 (3+2) + "┳" + 7 (5+2) + "┓"
	wantRunes := 1 + 5 + 1 + 7 + 1
	if got := len([]rune(line)); got != wantRunes {
		t.Fatalf("expected %d runes, got %d (%q)", wantRunes, got, line)
	}
}

func TestSupportsTrueColor(t *testing.T) {
	t.Setenv("COLORTERM", "truecolor")
	t.Setenv("TERM", "xterm-256color")
	if !supportsTrueColor() {
		t.Fatal("expected COLORTERM=truecolor to report true-color support")
	}

	t.Setenv("COLORTERM", "")
	t.Setenv("TERM", "linux")
	if supportsTrueColor() {
		t.Fatal("expected TERM=linux (raw console) to report no true-color support")
	}

	t.Setenv("TERM", "xterm-256color")
	if !supportsTrueColor() {
		t.Fatal("expected an unrecognised-but-not-raw TERM to default to true-color support")
	}
}

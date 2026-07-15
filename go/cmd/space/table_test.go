package main

import "testing"

func TestFormatRowSeverity(t *testing.T) {
	cases := []struct {
		total, free uint64
		wantStyle   string
	}{
		{100, 50, colorGreen},  // 50% used
		{100, 15, colorYellow}, // 85% used
		{100, 2, colorRedBold}, // 98% used
	}
	for _, c := range cases {
		tr := formatRow("/x", c.total, c.free)
		if tr.cellStyles[1] != c.wantStyle {
			t.Errorf("total=%d free=%d: got style %q, want %q", c.total, c.free, tr.cellStyles[1], c.wantStyle)
		}
	}
}

func TestFormatTotalRowAllCyan(t *testing.T) {
	tr := formatTotalRow("TOTAL", 100, 2)
	for i, style := range tr.cellStyles {
		if style != colorCyanBold {
			t.Errorf("cell %d: got style %q, want %q", i, style, colorCyanBold)
		}
	}
}

func TestColumnWidths(t *testing.T) {
	rows := []tableRow{
		formatRow("/mnt/very-long-path-name", 100, 50),
	}
	widths := columnWidths(rows)
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

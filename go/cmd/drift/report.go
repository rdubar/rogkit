package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

const colorReset = "\x1b[0m"

type colors struct {
	collector, info, notable, header string
}

func trueColorPalette() colors {
	return colors{
		collector: "\x1b[1;38;2;255;128;191m", // bold #ff80bf
		info:      "\x1b[38;2;78;205;196m",    // #4ecdc4
		notable:   "\x1b[1;38;2;255;107;107m", // bold #ff6b6b
		header:    "\x1b[1;36m",               // bold cyan
	}
}

func basicPalette() colors {
	return colors{
		collector: "\x1b[1;35m",
		info:      "\x1b[32m",
		notable:   "\x1b[1;31m",
		header:    "\x1b[1;36m",
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

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

// printReport renders the verdict line plus one grouped line per change, in
// the same "verdict + evidence" register as sysreboot/mem.
func printReport(changes []Change, since time.Time, color bool) {
	notable := 0
	for _, c := range changes {
		if c.Severity == severityNotable {
			notable++
		}
	}

	c := colors{}
	if color {
		c = activePalette()
	}

	if len(changes) == 0 {
		fmt.Printf("No changes since %s.\n", relativeTime(since))
		return
	}

	verdict := fmt.Sprintf("%d change(s) since %s", len(changes), relativeTime(since))
	if notable > 0 {
		verdict += fmt.Sprintf(" (%d notable)", notable)
	}
	if color {
		fmt.Println(c.header + verdict + colorReset)
	} else {
		fmt.Println(verdict)
	}
	fmt.Println()

	for _, ch := range changes {
		style := c.info
		if ch.Severity == severityNotable {
			style = c.notable
		}
		label := fmt.Sprintf("%-8s", ch.Collector)
		if color {
			fmt.Printf("%s%s%s  %s\n", c.collector, label, colorReset, colorize(style, ch.Text, color))
		} else {
			fmt.Printf("%s  %s\n", label, ch.Text)
		}
	}
}

func colorize(style, text string, color bool) string {
	if !color || style == "" {
		return text
	}
	return style + text + colorReset
}

func relativeTime(t time.Time) string {
	d := time.Since(t)
	switch {
	case d < time.Hour:
		return fmt.Sprintf("%d minutes ago", int(d.Minutes()))
	case d < 24*time.Hour:
		return fmt.Sprintf("%s %s", t.Format("15:04"), "today")
	case d < 48*time.Hour:
		return fmt.Sprintf("%s yesterday", t.Format("15:04"))
	default:
		return t.Format("2006-01-02 15:04")
	}
}

func printReportJSON(changes []Change, since time.Time) {
	out := make([]map[string]any, 0, len(changes))
	for _, c := range changes {
		notable := c.Severity == severityNotable
		out = append(out, map[string]any{
			"collector": c.Collector,
			"text":      c.Text,
			"notable":   notable,
		})
	}
	notable := 0
	for _, c := range changes {
		if c.Severity == severityNotable {
			notable++
		}
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(map[string]any{
		"since":         since.Format(time.RFC3339),
		"change_count":  len(changes),
		"notable_count": notable,
		"changes":       out,
	})
}

var siUnits = []string{"bytes", "KB", "MB", "GB", "TB", "PB"}

// byteSize formats a byte count the same way space/mem's byteSize() does:
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

package main

import (
	"regexp"
	"strings"
)

// Masking order matters: timestamps and IDs must be replaced before the
// generic bare-number pass, or their digits would already be gone.
var (
	reISOTimestamp    = regexp.MustCompile(`\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?`)
	reSyslogTimestamp = regexp.MustCompile(`\b[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b`)
	reClockTime       = regexp.MustCompile(`\b\d{1,2}:\d{2}:\d{2}(\.\d+)?\b`)
	reUUID            = regexp.MustCompile(`\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b`)
	reHexID           = regexp.MustCompile(`\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{12,}\b`)
	reIPv4            = regexp.MustCompile(`\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`)
	rePath            = regexp.MustCompile(`(?:/[\w.\-]+){2,}`)
	reNumber          = regexp.MustCompile(`\b\d+\b`)
)

// maskLine replaces variable-looking fields with placeholders so structurally
// identical log lines collapse to the same template regardless of their
// specific timestamp, ID, path, or count.
func maskLine(line string) string {
	s := line
	s = reISOTimestamp.ReplaceAllString(s, "<TS>")
	s = reSyslogTimestamp.ReplaceAllString(s, "<TS>")
	s = reClockTime.ReplaceAllString(s, "<TS>")
	s = reUUID.ReplaceAllString(s, "<ID>")
	s = reHexID.ReplaceAllString(s, "<ID>")
	s = reIPv4.ReplaceAllString(s, "<IP>")
	s = rePath.ReplaceAllString(s, "<PATH>")
	s = reNumber.ReplaceAllString(s, "<N>")
	// Collapse whitespace runs so right-aligned/padded columns (common in
	// fixed-width log and table formats — a 7-digit number gets fewer
	// leading spaces than a 5-digit one) don't fragment one logical row
	// shape into several templates that differ only in padding.
	return strings.Join(strings.Fields(s), " ")
}

var errorKeywords = []string{"error", "fail", "fatal", "warn", "panic", "exception", "denied", "refused", "timeout", "critical"}

func isErrorish(line string) bool {
	lower := strings.ToLower(line)
	for _, kw := range errorKeywords {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

// cluster is one masked template plus its occurrence stats.
type cluster struct {
	Pattern  string
	Count    int
	First    int // 1-indexed line number of first occurrence
	Last     int
	Errorish bool
}

// clusterLines masks every non-blank line and groups identical templates,
// preserving first-seen order.
func clusterLines(lines []string) []cluster {
	var order []string
	byPattern := make(map[string]*cluster)
	for i, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		pat := maskLine(line)
		c, ok := byPattern[pat]
		if !ok {
			c = &cluster{Pattern: pat, First: i + 1, Errorish: isErrorish(line)}
			byPattern[pat] = c
			order = append(order, pat)
		}
		c.Count++
		c.Last = i + 1
		if isErrorish(line) {
			c.Errorish = true
		}
	}
	out := make([]cluster, 0, len(order))
	for _, pat := range order {
		out = append(out, *byPattern[pat])
	}
	return out
}

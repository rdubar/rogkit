package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// uptimed writes one line per boot as "uptime:boot_epoch:system". uprec
// reads that format as-is and writes a superset: a fourth field records
// whether the run ended cleanly, which uptimed does not track. Anything
// reading these files should ignore fields it does not recognise, which
// is what parseRecords does with uptimed's three-field lines.
const (
	cleanField   = "clean"
	uncleanField = "unclean"
)

// uptimedPaths lists where the uptimed daemon keeps its records across
// the distributions and package managers that ship it.
func uptimedPaths() []string {
	if p := os.Getenv("UPREC_UPTIMED_RECORDS"); p != "" {
		return []string{p}
	}
	return []string{
		"/var/spool/uptimed/records",        // Debian, Ubuntu, Raspberry Pi OS
		"/var/lib/uptimed/records",          // Fedora, Arch
		"/opt/homebrew/var/uptimed/records", // Homebrew on Apple silicon
		"/usr/local/var/uptimed/records",    // Homebrew on Intel
	}
}

// statePath is uprec's own record file. It lives under the user's state
// directory so no privileges are needed, which is the point: the history
// keeps accumulating on a machine where uptimed was never installed.
func statePath() string {
	if p := os.Getenv("UPREC_STATE"); p != "" {
		return p
	}
	base := os.Getenv("XDG_STATE_HOME")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return ""
		}
		base = filepath.Join(home, ".local", "state")
	}
	return filepath.Join(base, "rogkit", "uprec.records")
}

// readRecords loads a records file, returning nil if it is absent. A
// missing or unreadable file is never an error: every source here is
// best-effort, and the tool still works with whatever the others provide.
func readRecords(path, source string) []Boot {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()

	var boots []Boot
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		if b, ok := parseRecord(scanner.Text()); ok {
			b.Source = source
			boots = append(boots, b)
		}
	}
	return boots
}

// parseRecord reads one "uptime:boot_epoch:system[:clean]" line.
func parseRecord(line string) (Boot, bool) {
	line = strings.TrimSpace(line)
	if line == "" || strings.HasPrefix(line, "#") {
		return Boot{}, false
	}
	fields := strings.Split(line, ":")
	if len(fields) < 2 {
		return Boot{}, false
	}
	secs, err := strconv.ParseInt(fields[0], 10, 64)
	if err != nil {
		return Boot{}, false
	}
	epoch, err := strconv.ParseInt(fields[1], 10, 64)
	if err != nil {
		return Boot{}, false
	}

	b := Boot{
		Boot:   time.Unix(epoch, 0),
		Uptime: time.Duration(secs) * time.Second,
	}
	b.End = b.Boot.Add(b.Uptime)
	if len(fields) > 2 && fields[2] != "unknown" {
		b.System = fields[2]
	}
	// A three-field uptimed line carries no verdict on how the run
	// ended, which stays distinct from a recorded clean shutdown.
	if len(fields) > 3 {
		switch fields[3] {
		case cleanField:
			b.Clean, b.CleanKnown = true, true
		case uncleanField:
			b.Clean, b.CleanKnown = false, true
		}
	}
	return b, true
}

// formatRecord is the inverse of parseRecord.
func formatRecord(b Boot) string {
	system := b.System
	if system == "" {
		system = "unknown"
	}
	// Colons in the system string would corrupt the field split.
	system = strings.ReplaceAll(system, ":", " ")

	line := fmt.Sprintf("%d:%d:%s", int64(b.Uptime/time.Second), b.Boot.Unix(), system)
	if b.CleanKnown && !b.Current {
		if b.Clean {
			line += ":" + cleanField
		} else {
			line += ":" + uncleanField
		}
	}
	return line
}

// saveState writes the merged history back to uprec's own file, so boots
// survive the login database being rotated away. Written to a temporary
// file and renamed, so a crash mid-write cannot truncate the history.
func saveState(path string, boots []Boot) error {
	if path == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}

	var b strings.Builder
	for _, boot := range boots {
		b.WriteString(formatRecord(boot))
		b.WriteByte('\n')
	}

	tmp, err := os.CreateTemp(filepath.Dir(path), ".uprec-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	if _, err := tmp.WriteString(b.String()); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Chmod(tmpName, 0o644); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

// loadStored gathers every records file worth reading: uprec's own state
// first, then the uptimed daemon's if it is installed.
func loadStored() []Boot {
	boots := readRecords(statePath(), "state")
	for _, p := range uptimedPaths() {
		if found := readRecords(p, "uptimed"); found != nil {
			boots = append(boots, found...)
			break
		}
	}
	return boots
}

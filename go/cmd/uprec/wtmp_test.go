package main

import (
	"bytes"
	"compress/gzip"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// utmpRecord builds one 384-byte wtmp entry in host byte order.
func utmpRecord(recType uint16, user string, sec int32) []byte {
	buf := make([]byte, utmpRecordSize)
	order := nativeEndian()
	order.PutUint16(buf[utmpTypeOffset:], recType)
	copy(buf[utmpUserOffset:utmpUserOffset+utmpUserSize], user)
	order.PutUint32(buf[utmpSecOffset:], uint32(sec))
	return buf
}

func TestParseWtmpKeepsOnlyBootAndShutdown(t *testing.T) {
	var raw bytes.Buffer
	raw.Write(utmpRecord(bootTime, "reboot", 1000))
	raw.Write(utmpRecord(7, "rdubar", 1500))          // USER_PROCESS: a login
	raw.Write(utmpRecord(runLevel, "runlevel", 1600)) // not a shutdown
	raw.Write(utmpRecord(runLevel, "shutdown", 2000))
	raw.Write(utmpRecord(bootTime, "reboot", 2100))

	events, err := parseWtmp(&raw, nativeEndian())
	if err != nil {
		t.Fatalf("parseWtmp: %v", err)
	}
	if len(events) != 3 {
		t.Fatalf("got %d events, want 3: %+v", len(events), events)
	}

	want := []event{
		{When: time.Unix(1000, 0), Kind: eventBoot},
		{When: time.Unix(2000, 0), Kind: eventShutdown},
		{When: time.Unix(2100, 0), Kind: eventBoot},
	}
	for i, w := range want {
		if !events[i].When.Equal(w.When) || events[i].Kind != w.Kind {
			t.Errorf("event %d = %+v, want %+v", i, events[i], w)
		}
	}
}

func TestParseWtmpSkipsEmptyTimestamps(t *testing.T) {
	var raw bytes.Buffer
	raw.Write(utmpRecord(bootTime, "reboot", 0))
	raw.Write(utmpRecord(bootTime, "reboot", 1000))

	events, err := parseWtmp(&raw, nativeEndian())
	if err != nil {
		t.Fatalf("parseWtmp: %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("got %d events, want 1 — a zero timestamp is a blank record", len(events))
	}
}

// A wtmp being appended to while it is read can end mid-record; the
// records already decoded should still be returned.
func TestParseWtmpToleratesTruncatedTail(t *testing.T) {
	var raw bytes.Buffer
	raw.Write(utmpRecord(bootTime, "reboot", 1000))
	raw.Write(make([]byte, 40))

	events, err := parseWtmp(&raw, nativeEndian())
	if err != nil {
		t.Fatalf("parseWtmp: %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("got %d events, want 1", len(events))
	}
}

// Rotated generations arrive gzipped on most distributions, and they are
// where a long-running server's history actually lives.
func TestReadWtmpHandlesGzip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "wtmp.1.gz")

	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	gz := gzip.NewWriter(f)
	if _, err := gz.Write(utmpRecord(bootTime, "reboot", 1000)); err != nil {
		t.Fatalf("write: %v", err)
	}
	gz.Close()
	f.Close()

	events, err := readWtmp(path)
	if err != nil {
		t.Fatalf("readWtmp: %v", err)
	}
	if len(events) != 1 || events[0].Kind != eventBoot {
		t.Fatalf("got %+v, want one boot event", events)
	}
}

func TestReadWtmpMissingFile(t *testing.T) {
	if _, err := readWtmp(filepath.Join(t.TempDir(), "absent")); err == nil {
		t.Error("want an error for a missing file, so the caller can skip it")
	}
}

func TestCString(t *testing.T) {
	field := make([]byte, 32)
	copy(field, "shutdown")
	if got := cString(field); got != "shutdown" {
		t.Errorf("cString = %q, want %q", got, "shutdown")
	}
	if got := cString([]byte("nonul")); got != "nonul" {
		t.Errorf("cString without a NUL = %q, want %q", got, "nonul")
	}
}

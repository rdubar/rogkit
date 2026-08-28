package main

import (
	"bytes"
	"compress/gzip"
	"encoding/binary"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Timestamps have to be plausible: the layout detector rejects a
// candidate that decodes anything outside 2000-2100, which is how it
// tells a wrong record size from a right one.
const (
	epochBootA     = 1783547580 // 2026-07-08 22:53 BST
	epochShutdownA = 1784972340 // 2026-07-25 10:39 BST
	epochBootB     = 1784972400
)

// layout384 is glibc with 32-bit time compat (x86_64, 32-bit arches) and
// musl; layout400 is glibc without it, which is what a Raspberry Pi 5
// running 64-bit Pi OS writes.
var (
	layout384 = utmpLayouts[0]
	layout400 = utmpLayouts[1]
)

// utmpRecord builds one wtmp entry in the given layout, host byte order.
func utmpRecord(l utmpLayout, recType uint16, user string, sec int64) []byte {
	buf := make([]byte, l.size)
	order := nativeEndian()
	order.PutUint16(buf[utmpTypeOffset:], recType)
	copy(buf[utmpUserOffset:utmpUserOffset+utmpUserSize], user)
	if l.secWidth == 8 {
		order.PutUint64(buf[l.secOffset:], uint64(sec))
	} else {
		order.PutUint32(buf[l.secOffset:], uint32(sec))
	}
	return buf
}

func sampleWtmp(l utmpLayout) []byte {
	var raw bytes.Buffer
	raw.Write(utmpRecord(l, bootTime, "reboot", epochBootA))
	raw.Write(utmpRecord(l, 7, "rdubar", epochBootA+60))          // USER_PROCESS: a login
	raw.Write(utmpRecord(l, runLevel, "runlevel", epochBootA+90)) // not a shutdown
	raw.Write(utmpRecord(l, runLevel, "shutdown", epochShutdownA))
	raw.Write(utmpRecord(l, bootTime, "reboot", epochBootB))
	return raw.Bytes()
}

// Both record layouts must decode identically, without being told which
// one they are.
func TestParseWtmpBothLayouts(t *testing.T) {
	cases := []struct {
		name string
		l    utmpLayout
	}{
		{"384-byte (x86_64 glibc, musl)", layout384},
		{"400-byte (aarch64 glibc)", layout400},
	}

	want := []event{
		{When: time.Unix(epochBootA, 0), Kind: eventBoot},
		{When: time.Unix(epochShutdownA, 0), Kind: eventShutdown},
		{When: time.Unix(epochBootB, 0), Kind: eventBoot},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			events, err := parseWtmp(bytes.NewReader(sampleWtmp(c.l)), nativeEndian())
			if err != nil {
				t.Fatalf("parseWtmp: %v", err)
			}
			if len(events) != len(want) {
				t.Fatalf("got %d events, want %d: %+v", len(events), len(want), events)
			}
			for i, w := range want {
				if !events[i].When.Equal(w.When) || events[i].Kind != w.Kind {
					t.Errorf("event %d = %+v, want %+v", i, events[i], w)
				}
			}
		})
	}
}

// The detector has to pick the layout that actually wrote the file, not
// merely one whose record size happens to divide it.
func TestDetectLayout(t *testing.T) {
	order := nativeEndian()

	for _, c := range []struct {
		name string
		want utmpLayout
	}{
		{"384", layout384},
		{"400", layout400},
	} {
		t.Run(c.name, func(t *testing.T) {
			got, ok := detectLayout(sampleWtmp(c.want), order)
			if !ok {
				t.Fatal("no layout detected")
			}
			if got.size != c.want.size {
				t.Errorf("detected %d-byte records, want %d", got.size, c.want.size)
			}
		})
	}
}

// A Pi 5's /var/log/wtmp was 66400 bytes: an exact multiple of 400 and
// not of 384, which is what exposed the layout assumption in the first
// place.
func TestDetectLayoutRealPiFileSize(t *testing.T) {
	const size = 66400
	if size%layout400.size != 0 {
		t.Fatalf("%d should divide by %d", size, layout400.size)
	}
	if size%layout384.size == 0 {
		t.Fatalf("%d should not divide by %d", size, layout384.size)
	}

	records := size / layout400.size
	var raw bytes.Buffer
	for i := 0; i < records; i++ {
		raw.Write(utmpRecord(layout400, bootTime, "reboot", int64(epochBootA+i*3600)))
	}

	got, ok := detectLayout(raw.Bytes(), nativeEndian())
	if !ok || got.size != layout400.size {
		t.Fatalf("detected %+v (ok=%v), want the 400-byte layout", got, ok)
	}
}

func TestParseWtmpRejectsGarbage(t *testing.T) {
	garbage := bytes.Repeat([]byte{0xff}, 4096)
	if events := parseWtmpBytes(garbage, nativeEndian()); events != nil {
		t.Errorf("got %+v, want nothing decoded from garbage", events)
	}
}

func TestParseWtmpSkipsEmptyTimestamps(t *testing.T) {
	var raw bytes.Buffer
	raw.Write(utmpRecord(layout384, bootTime, "reboot", 0))
	raw.Write(utmpRecord(layout384, bootTime, "reboot", epochBootA))

	events, err := parseWtmp(&raw, nativeEndian())
	if err != nil {
		t.Fatalf("parseWtmp: %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("got %d events, want 1 — a zero timestamp is a blank record", len(events))
	}
}

// A wtmp being appended to while it is read can end mid-record; the
// records already decoded should still come back.
func TestParseWtmpToleratesTruncatedTail(t *testing.T) {
	var raw bytes.Buffer
	raw.Write(utmpRecord(layout384, bootTime, "reboot", epochBootA))
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
	if _, err := gz.Write(sampleWtmp(layout400)); err != nil {
		t.Fatalf("write: %v", err)
	}
	gz.Close()
	f.Close()

	events, err := readWtmp(path)
	if err != nil {
		t.Fatalf("readWtmp: %v", err)
	}
	if len(events) != 3 {
		t.Fatalf("got %d events, want 3", len(events))
	}
}

func TestReadWtmpMissingFile(t *testing.T) {
	if _, err := readWtmp(filepath.Join(t.TempDir(), "absent")); err == nil {
		t.Error("want an error for a missing file, so the caller can skip it")
	}
}

func TestRecordSecondsWidths(t *testing.T) {
	order := nativeEndian()
	if got := recordSeconds(utmpRecord(layout384, bootTime, "reboot", epochBootA), layout384, order); got != epochBootA {
		t.Errorf("32-bit read = %d, want %d", got, epochBootA)
	}
	if got := recordSeconds(utmpRecord(layout400, bootTime, "reboot", epochBootA), layout400, order); got != epochBootA {
		t.Errorf("64-bit read = %d, want %d", got, epochBootA)
	}
}

func TestNativeEndianMatchesHost(t *testing.T) {
	order := nativeEndian()
	if order != binary.LittleEndian && order != binary.BigEndian {
		t.Fatal("want a concrete byte order")
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

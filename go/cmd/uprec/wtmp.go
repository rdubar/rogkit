package main

import (
	"compress/gzip"
	"encoding/binary"
	"io"
	"os"
	"strings"
	"time"
	"unsafe"
)

// wtmp is a raw dump of glibc's struct utmp, and that struct is not the
// same size everywhere. Where glibc keeps 32-bit-compatible time fields
// (x86_64, and every 32-bit architecture) a record is 384 bytes; where it
// does not (aarch64) ut_session and ut_tv widen to 64 bits and a record
// is 400. musl uses the 384-byte form throughout.
//
// GOARCH cannot settle this: it says nothing about which libc wrote the
// file, and a rotated generation may have been written by a different one
// than is running now. The layout is detected from the data instead.
type utmpLayout struct {
	size      int
	secOffset int
	secWidth  int
}

var utmpLayouts = []utmpLayout{
	{size: 384, secOffset: 340, secWidth: 4}, // glibc with 32-bit time compat, and musl
	{size: 400, secOffset: 344, secWidth: 8}, // glibc without it, e.g. aarch64
}

// Fields before ut_exit sit at the same offset in every layout, so only
// the timestamp has to move.
const (
	utmpTypeOffset = 0
	utmpUserOffset = 44
	utmpUserSize   = 32

	runLevel    = 1 // RUN_LVL: shutdown is logged here, with ut_user "shutdown"
	bootTime    = 2 // BOOT_TIME
	maxUtmpType = 9 // ACCOUNTING, the highest type defined

	// A real record's timestamp falls between 2000-01-01 and 2100-01-01.
	// Anything outside means the bytes being read are not a timestamp,
	// which is how a wrong layout gives itself away.
	minPlausibleTime = 946684800
	maxPlausibleTime = 4102444800
)

// nativeEndian reports the byte order wtmp records were written in.
// wtmp is a raw memory dump, so it is always host order, and Linux runs
// on both big- and little-endian hardware.
func nativeEndian() binary.ByteOrder {
	probe := uint16(1)
	if *(*byte)(unsafe.Pointer(&probe)) == 1 {
		return binary.LittleEndian
	}
	return binary.BigEndian
}

// layoutScore rates how well a candidate layout explains a file. A layout
// whose record size divides the file exactly is always preferred; between
// two that both do, the one decoding more usable timestamps wins.
type layoutScore struct {
	exact bool
	valid int
	ok    bool
}

func (s layoutScore) better(than layoutScore) bool {
	switch {
	case !s.ok:
		return false
	case !than.ok:
		return true
	case s.exact != than.exact:
		return s.exact
	default:
		return s.valid > than.valid
	}
}

// scoreLayout walks the file as if it held records of this layout,
// rejecting outright on anything that cannot occur in a real one.
func scoreLayout(data []byte, l utmpLayout, order binary.ByteOrder) layoutScore {
	if len(data) < l.size {
		return layoutScore{}
	}

	score := layoutScore{exact: len(data)%l.size == 0, ok: true}
	for off := 0; off+l.size <= len(data); off += l.size {
		rec := data[off : off+l.size]
		if order.Uint16(rec[utmpTypeOffset:]) > maxUtmpType {
			return layoutScore{}
		}
		sec := recordSeconds(rec, l, order)
		if sec == 0 {
			continue // a blank record, which says nothing either way
		}
		if sec < minPlausibleTime || sec > maxPlausibleTime {
			return layoutScore{}
		}
		score.valid++
	}
	return score
}

func detectLayout(data []byte, order binary.ByteOrder) (utmpLayout, bool) {
	var best utmpLayout
	var bestScore layoutScore

	for _, l := range utmpLayouts {
		if s := scoreLayout(data, l, order); s.better(bestScore) {
			best, bestScore = l, s
		}
	}
	return best, bestScore.ok
}

func recordSeconds(rec []byte, l utmpLayout, order binary.ByteOrder) int64 {
	if l.secWidth == 8 {
		return int64(order.Uint64(rec[l.secOffset:]))
	}
	return int64(int32(order.Uint32(rec[l.secOffset:])))
}

// parseWtmp decodes a whole login database. The file is read into memory
// because the record layout can only be settled by looking at all of it;
// wtmp generations are small enough (tens of KB to a few MB) for that to
// be cheaper than the alternative of guessing.
func parseWtmp(r io.Reader, order binary.ByteOrder) ([]event, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	return parseWtmpBytes(data, order), nil
}

// parseWtmpBytes keeps only the two record types that bound a boot
// session. A trailing partial record — a wtmp appended to while it was
// being read — is ignored rather than treated as corruption.
func parseWtmpBytes(data []byte, order binary.ByteOrder) []event {
	layout, ok := detectLayout(data, order)
	if !ok {
		return nil
	}

	var events []event
	for off := 0; off+layout.size <= len(data); off += layout.size {
		rec := data[off : off+layout.size]

		recType := order.Uint16(rec[utmpTypeOffset:])
		user := cString(rec[utmpUserOffset : utmpUserOffset+utmpUserSize])
		sec := recordSeconds(rec, layout, order)
		if sec <= 0 {
			continue
		}

		switch {
		case recType == bootTime:
			events = append(events, event{When: time.Unix(sec, 0), Kind: eventBoot})
		case recType == runLevel && user == "shutdown":
			events = append(events, event{When: time.Unix(sec, 0), Kind: eventShutdown})
		}
	}
	return events
}

func readWtmp(path string) ([]event, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var r io.Reader = f
	if strings.HasSuffix(path, ".gz") {
		gz, err := gzip.NewReader(f)
		if err != nil {
			return nil, err
		}
		defer gz.Close()
		r = gz
	}
	return parseWtmp(r, nativeEndian())
}

// cString trims a fixed-width field at its first NUL.
func cString(b []byte) string {
	if i := strings.IndexByte(string(b), 0); i >= 0 {
		return string(b[:i])
	}
	return string(b)
}

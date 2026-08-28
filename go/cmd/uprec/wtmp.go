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

// The wtmp record layout (glibc's struct utmp, also what musl writes):
// 384 bytes on every architecture Linux currently ships, with the
// timestamp stored as a pair of 32-bit fields rather than a time_t.
const (
	utmpRecordSize = 384
	utmpTypeOffset = 0
	utmpUserOffset = 44
	utmpUserSize   = 32
	utmpSecOffset  = 340

	runLevel = 1 // RUN_LVL: shutdown is logged here, with ut_user "shutdown"
	bootTime = 2 // BOOT_TIME
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

// parseWtmp walks fixed-size records, keeping only the two types that
// bound a boot session.
func parseWtmp(r io.Reader, order binary.ByteOrder) ([]event, error) {
	var events []event
	buf := make([]byte, utmpRecordSize)

	for {
		if _, err := io.ReadFull(r, buf); err != nil {
			if err == io.EOF || err == io.ErrUnexpectedEOF {
				return events, nil
			}
			return events, err
		}

		recType := order.Uint16(buf[utmpTypeOffset:])
		user := cString(buf[utmpUserOffset : utmpUserOffset+utmpUserSize])
		sec := int32(order.Uint32(buf[utmpSecOffset:]))
		if sec <= 0 {
			continue
		}

		switch {
		case recType == bootTime:
			events = append(events, event{When: time.Unix(int64(sec), 0), Kind: eventBoot})
		case recType == runLevel && user == "shutdown":
			events = append(events, event{When: time.Unix(int64(sec), 0), Kind: eventShutdown})
		}
	}
}

// cString trims a fixed-width field at its first NUL.
func cString(b []byte) string {
	if i := strings.IndexByte(string(b), 0); i >= 0 {
		return string(b[:i])
	}
	return string(b)
}

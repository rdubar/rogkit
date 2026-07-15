//go:build darwin

package main

import (
	"encoding/binary"
	"testing"
)

func TestParseDarwinHelpers(t *testing.T) {
	t.Run("loadavg", func(t *testing.T) {
		raw := make([]byte, 24)
		binary.LittleEndian.PutUint32(raw[0:4], 2*2048)
		binary.LittleEndian.PutUint32(raw[4:8], 3*2048/2)
		binary.LittleEndian.PutUint32(raw[8:12], 2048/2)
		binary.LittleEndian.PutUint64(raw[16:24], 2048)
		l1, l5, l15, ok := parseLoadAvgRaw(raw)
		if !ok {
			t.Fatal("loadavg raw parse failed")
		}
		if l1 != 2.0 || l5 != 1.5 || l15 != 0.5 {
			t.Fatalf("unexpected loadavg parse: %.2f %.2f %.2f", l1, l5, l15)
		}
	})

	t.Run("vmstat page size", func(t *testing.T) {
		got, ok := parseVMStatPageSize("Mach Virtual Memory Statistics: (page size of 4096 bytes)")
		if !ok || got != 4096 {
			t.Fatalf("unexpected page size parse: ok=%v got=%d", ok, got)
		}
	})

	t.Run("vmstat line", func(t *testing.T) {
		name, count, ok := parseVMStatLine("Pages inactive:                              1234.")
		if !ok || name != "Pages inactive" || count != 1234 {
			t.Fatalf("unexpected vm_stat parse: ok=%v name=%q count=%d", ok, name, count)
		}
	})

	t.Run("swap m", func(t *testing.T) {
		raw := make([]byte, 32)
		binary.LittleEndian.PutUint64(raw[0:8], 16*1024*1024)
		binary.LittleEndian.PutUint64(raw[16:24], 4*1024*1024)
		total, used, ok := parseSwapUsageRaw(raw)
		if !ok || total != 16*1024*1024 || used != 4*1024*1024 {
			t.Fatalf("unexpected swap parse: ok=%v total=%d used=%d", ok, total, used)
		}
	})

	t.Run("swap g", func(t *testing.T) {
		raw := make([]byte, 32)
		binary.LittleEndian.PutUint64(raw[0:8], 1610612736)
		binary.LittleEndian.PutUint64(raw[16:24], 536870912)
		total, used, ok := parseSwapUsageRaw(raw)
		if !ok || total != 1610612736 || used != 536870912 {
			t.Fatalf("unexpected swap parse: ok=%v total=%d used=%d", ok, total, used)
		}
	})
}

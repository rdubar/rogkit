package main

import "testing"

func TestDiagnoseSwapPressureWins(t *testing.T) {
	sys := sysStats{Cores: 4, Load1: 0.5, MemTotal: 8 * 1024 * 1024 * 1024, MemAvailable: 512 * 1024 * 1024, SwapTotal: 4 * 1024 * 1024 * 1024, SwapUsed: 2 * 1024 * 1024 * 1024}
	v := diagnose(sys, true, memGroup{}, false, cpuProc{}, false)
	if !v.Culprit {
		t.Fatalf("expected a culprit for 2GB swap used, got %+v", v)
	}
}

func TestDiagnoseDoesNotCallSwapUsePressureWithHealthyRAM(t *testing.T) {
	sys := sysStats{Cores: 4, Load1: 0.5, MemTotal: 8 * 1024 * 1024 * 1024, MemAvailable: 5 * 1024 * 1024 * 1024, SwapTotal: 4 * 1024 * 1024 * 1024, SwapUsed: 2 * 1024 * 1024 * 1024}
	v := diagnose(sys, true, memGroup{}, false, cpuProc{}, false)
	if v.Culprit {
		t.Fatalf("expected healthy RAM to suppress stale swap-use warning, got %+v", v)
	}
}

func TestDiagnoseCPUBound(t *testing.T) {
	sys := sysStats{Cores: 4, Load1: 8.0} // 2x cores
	top := cpuProc{Name: "mediaanalysisd", PID: 123, PCPU: 340}
	v := diagnose(sys, true, memGroup{}, false, top, true)
	if !v.Culprit {
		t.Fatalf("expected a culprit for load 2x cores, got %+v", v)
	}
	if v.Text == "" {
		t.Fatal("expected non-empty diagnosis text")
	}
}

func TestDiagnoseMemoryBound(t *testing.T) {
	sys := sysStats{Cores: 4, Load1: 0.3}
	top := memGroup{Name: "Chrome", RSSBytes: 4 * 1024 * 1024 * 1024, PctMem: 40}
	v := diagnose(sys, true, top, true, cpuProc{}, false)
	if !v.Culprit {
		t.Fatalf("expected a culprit for a process using 40%% RAM, got %+v", v)
	}
}

func TestDiagnoseNothingWrong(t *testing.T) {
	sys := sysStats{Cores: 8, Load1: 1.0}
	top := memGroup{Name: "Finder", RSSBytes: 100 * 1024 * 1024, PctMem: 1.2}
	v := diagnose(sys, true, top, true, cpuProc{}, false)
	if v.Culprit {
		t.Fatalf("expected no culprit under normal load/mem, got %+v", v)
	}
}

func TestDiagnoseGracefulWithNoCollectors(t *testing.T) {
	v := diagnose(sysStats{}, false, memGroup{}, false, cpuProc{}, false)
	if v.Culprit {
		t.Fatalf("expected no culprit when every collector failed, got %+v", v)
	}
	if v.Text == "" {
		t.Fatal("expected a fallback diagnosis text even with no data")
	}
}

func TestByteSize(t *testing.T) {
	if got := byteSize(1024 * 1024 * 1024); got != "1.07 GB" {
		t.Errorf("byteSize(1GiB) = %q, want %q", got, "1.07 GB")
	}
}

func TestDiagnoseHeavySwapDespiteInflatedAvailable(t *testing.T) {
	// The Mac case: 6 GB swapped on 8 GB, but inactive pages keep
	// "available" at 20% so the low-RAM test alone never fired.
	sys := sysStats{Cores: 6, Load1: 2, MemTotal: 8 * 1024 * 1024 * 1024, MemAvailable: 1700 * 1024 * 1024, SwapTotal: 7 * 1024 * 1024 * 1024, SwapUsed: 6 * 1024 * 1024 * 1024}
	top := memGroup{Name: "Codex (Renderer)", RSSBytes: 1800 * 1024 * 1024, PctMem: 21}
	v := diagnose(sys, true, top, true, cpuProc{}, false)
	if !v.Culprit {
		t.Fatalf("expected heavy swap to be a culprit, got %+v", v)
	}
}

func TestDiagnoseKernelCriticalPressure(t *testing.T) {
	sys := sysStats{Cores: 4, MemTotal: 8 * 1024 * 1024 * 1024, MemAvailable: 3 * 1024 * 1024 * 1024, Pressure: "critical"}
	v := diagnose(sys, true, memGroup{}, false, cpuProc{}, false)
	if !v.Culprit {
		t.Fatalf("expected critical kernel pressure to be a culprit, got %+v", v)
	}
}

func TestDiagnoseCarriesWarningsWithoutCulprit(t *testing.T) {
	sys := sysStats{Cores: 6, Load1: 1, MemTotal: 8 * 1024 * 1024 * 1024, MemAvailable: 2 * 1024 * 1024 * 1024, Warnings: []string{"2.8 GB swapped (33% of RAM) — getting tight"}}
	v := diagnose(sys, true, memGroup{}, false, cpuProc{}, false)
	if v.Culprit || len(v.Warnings) != 1 {
		t.Fatalf("expected no culprit but one warning, got %+v", v)
	}
}

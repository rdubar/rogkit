package main

import "fmt"

// Thresholds for "worth mentioning" — deliberately conservative, since a
// wrong confident diagnosis is worse than no diagnosis (flagged explicitly
// in the design brainstorm this tool came from).
const (
	swapNotableBytes         = 1024 * 1024 * 1024 // 1 GB
	memAvailablePctThreshold = 15.0
	loadRatioThreshold       = 1.5
	memPctThreshold          = 25.0
	swapRAMHeavyRatio        = 0.50 // half of RAM swapped: sluggish whatever "available" says
)

type verdict struct {
	Text     string
	Culprit  bool     // true when a specific cause was identified (exit 1)
	Warnings []string // memory limits sysreboot flagged, shown even without a culprit
}

// diagnose runs the checks in escalating order, first match wins: swap
// pressure, then CPU-bound (load vs core count), then a single process
// dominating memory. Each input collector is independently optional — a
// collector that failed just gets skipped rather than aborting the whole
// diagnosis. Thermal and disk-I/O-wait checks are deliberately not
// implemented in v1: both need genuinely platform-specific sampling this
// one-shot tool doesn't have a honest way to do yet.
func diagnose(sys sysStats, sysOK bool, topMem memGroup, memOK bool, topCPU cpuProc, cpuOK bool) verdict {
	v := diagnoseCause(sys, sysOK, topMem, memOK, topCPU, cpuOK)
	if sysOK {
		v.Warnings = sys.Warnings
	}
	if !v.Culprit && len(v.Warnings) > 0 {
		v.Text = "No single culprit, but memory is getting tight."
		if memOK {
			v.Text += fmt.Sprintf(" Biggest: %s at %s.", topMem.Name, byteSize(topMem.RSSBytes))
		}
	}
	return v
}

func diagnoseCause(sys sysStats, sysOK bool, topMem memGroup, memOK bool, topCPU cpuProc, cpuOK bool) verdict {
	if sysOK && swapPressure(sys) {
		text := fmt.Sprintf("Memory-pressured: %s swapped (%.0f%% of RAM)", byteSize(sys.SwapUsed), swapRAMRatio(sys)*100)
		if sys.Pressure == "warn" || sys.Pressure == "critical" {
			text += ", kernel pressure " + sys.Pressure
		}
		if memOK {
			text += fmt.Sprintf(" — biggest is %s using %s (%.0f%% mem)", topMem.Name, byteSize(topMem.RSSBytes), topMem.PctMem)
		}
		return verdict{Text: text, Culprit: true}
	}

	if sysOK && sys.Cores > 0 && sys.Load1/float64(sys.Cores) > loadRatioThreshold {
		text := fmt.Sprintf("CPU-bound: load %.2f on %d cores", sys.Load1, sys.Cores)
		if cpuOK {
			text += fmt.Sprintf(" — %s at %.0f%% CPU (pid %d)", topCPU.Name, topCPU.PCPU, topCPU.PID)
		}
		return verdict{Text: text, Culprit: true}
	}

	if memOK && topMem.PctMem >= memPctThreshold {
		text := fmt.Sprintf("Memory-bound: %s using %s (%.0f%% of RAM)", topMem.Name, byteSize(topMem.RSSBytes), topMem.PctMem)
		return verdict{Text: text, Culprit: true}
	}

	return verdict{Text: "Nothing obviously wrong.", Culprit: false}
}

// swapPressure fires on the kernel's own critical verdict, on heavy swap
// measured against RAM (macOS counts inactive pages as available, so the
// available-RAM test alone stays quiet while the machine freezes), or on
// notable swap with genuinely low available RAM.
func swapPressure(sys sysStats) bool {
	if sys.Pressure == "critical" {
		return true
	}
	if sys.MemTotal == 0 || sys.SwapUsed < swapNotableBytes {
		return false
	}
	if swapRAMRatio(sys) >= swapRAMHeavyRatio {
		return true
	}
	return float64(sys.MemAvailable)/float64(sys.MemTotal)*100 < memAvailablePctThreshold
}

func swapRAMRatio(sys sysStats) float64 {
	if sys.MemTotal == 0 {
		return 0
	}
	return float64(sys.SwapUsed) / float64(sys.MemTotal)
}

var siUnits = []string{"bytes", "KB", "MB", "GB", "TB", "PB"}

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
			return fmt.Sprintf("%.2f %s", f, unit)
		}
		f /= 1000
	}
	return ""
}

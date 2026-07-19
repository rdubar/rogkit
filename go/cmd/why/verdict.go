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
)

type verdict struct {
	Text    string
	Culprit bool // true when a specific cause was identified (exit 1)
}

// diagnose runs the checks in escalating order, first match wins: swap
// pressure, then CPU-bound (load vs core count), then a single process
// dominating memory. Each input collector is independently optional — a
// collector that failed just gets skipped rather than aborting the whole
// diagnosis. Thermal and disk-I/O-wait checks are deliberately not
// implemented in v1: both need genuinely platform-specific sampling this
// one-shot tool doesn't have a honest way to do yet.
func diagnose(sys sysStats, sysOK bool, topMem memGroup, memOK bool, topCPU cpuProc, cpuOK bool) verdict {
	if sysOK && swapPressure(sys) {
		text := fmt.Sprintf("Memory-pressured: %s swap in use with low available RAM", byteSize(sys.SwapUsed))
		if memOK {
			text += fmt.Sprintf(" — %s using %s (%.0f%% mem)", topMem.Name, byteSize(topMem.RSSBytes), topMem.PctMem)
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

func swapPressure(sys sysStats) bool {
	if sys.SwapTotal == 0 || sys.SwapUsed < swapNotableBytes || sys.MemTotal == 0 {
		return false
	}
	return float64(sys.MemAvailable)/float64(sys.MemTotal)*100 < memAvailablePctThreshold
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

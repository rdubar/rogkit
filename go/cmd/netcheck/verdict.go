package main

import "fmt"

// Thresholds are deliberately conservative — same rationale as why: a wrong
// confident diagnosis is worse than no diagnosis. Typical broadband clears
// all of these comfortably, so tripping one is a real signal, not noise.
const (
	dnsSlowMs         = 300.0
	latencyHighMs     = 150.0
	throughputLowMbps = 5.0
)

// platformHints groups the per-OS "go look here next" suggestions surfaced
// once a check trips. Populated by platform_darwin.go / platform_linux.go.
type platformHints struct {
	NoConnectivity []string
	DNS            []string
	Latency        []string
	Throughput     []string
}

type verdict struct {
	Text    string
	Culprit bool // true when a specific cause was identified (exit 1)
	Hints   []string
}

// diagnose runs the checks in escalating order, first match wins: total
// connectivity loss, then DNS, then latency, then throughput. Each input is
// independently optional — a check that failed to even run just gets
// skipped rather than aborting the whole diagnosis.
func diagnose(s netStats, hints platformHints) verdict {
	if !s.DNSOK && !s.LatencyOK {
		return verdict{Text: "No internet connectivity detected.", Culprit: true, Hints: hints.NoConnectivity}
	}

	if s.DNSOK && s.DNSMs > dnsSlowMs {
		return verdict{
			Text:    fmt.Sprintf("DNS resolution slow: %.0fms", s.DNSMs),
			Culprit: true,
			Hints:   hints.DNS,
		}
	}

	if s.LatencyOK && s.LatencyMs > latencyHighMs {
		return verdict{
			Text:    fmt.Sprintf("High latency: %.0fms to nearest public resolver", s.LatencyMs),
			Culprit: true,
			Hints:   hints.Latency,
		}
	}

	if s.ThroughputOK && s.ThroughputMbps < throughputLowMbps {
		return verdict{
			Text:    fmt.Sprintf("Low throughput: %.1f Mbps", s.ThroughputMbps),
			Culprit: true,
			Hints:   hints.Throughput,
		}
	}

	return verdict{Text: "Nothing obviously wrong.", Culprit: false}
}

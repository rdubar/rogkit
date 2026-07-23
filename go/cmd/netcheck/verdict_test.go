package main

import "testing"

var noHints = platformHints{}

func TestDiagnoseNoConnectivity(t *testing.T) {
	v := diagnose(netStats{}, noHints)
	if !v.Culprit {
		t.Fatalf("expected a culprit when both DNS and latency failed, got %+v", v)
	}
}

func TestDiagnoseDNSSlowWins(t *testing.T) {
	s := netStats{DNSMs: 500, DNSOK: true, LatencyMs: 20, LatencyOK: true, ThroughputMbps: 100, ThroughputOK: true}
	v := diagnose(s, noHints)
	if !v.Culprit {
		t.Fatalf("expected a culprit for 500ms DNS, got %+v", v)
	}
}

func TestDiagnoseHighLatency(t *testing.T) {
	s := netStats{DNSMs: 20, DNSOK: true, LatencyMs: 400, LatencyOK: true, ThroughputMbps: 100, ThroughputOK: true}
	v := diagnose(s, noHints)
	if !v.Culprit {
		t.Fatalf("expected a culprit for 400ms latency, got %+v", v)
	}
}

func TestDiagnoseLowThroughput(t *testing.T) {
	s := netStats{DNSMs: 20, DNSOK: true, LatencyMs: 20, LatencyOK: true, ThroughputMbps: 0.5, ThroughputOK: true}
	v := diagnose(s, noHints)
	if !v.Culprit {
		t.Fatalf("expected a culprit for 0.5 Mbps throughput, got %+v", v)
	}
}

func TestDiagnoseNothingWrong(t *testing.T) {
	s := netStats{DNSMs: 20, DNSOK: true, LatencyMs: 15, LatencyOK: true, ThroughputMbps: 250, ThroughputOK: true}
	v := diagnose(s, noHints)
	if v.Culprit {
		t.Fatalf("expected no culprit under healthy conditions, got %+v", v)
	}
}

func TestDiagnoseGracefulWithNoCollectors(t *testing.T) {
	v := diagnose(netStats{}, noHints)
	if v.Text == "" {
		t.Fatal("expected a fallback diagnosis text even with no data")
	}
}

func TestDiagnoseThroughputSkippedWhenNotOK(t *testing.T) {
	s := netStats{DNSMs: 20, DNSOK: true, LatencyMs: 15, LatencyOK: true, ThroughputOK: false}
	v := diagnose(s, noHints)
	if v.Culprit {
		t.Fatalf("expected no culprit when throughput collector failed, got %+v", v)
	}
}

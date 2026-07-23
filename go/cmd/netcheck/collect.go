package main

import (
	"context"
	"io"
	"net"
	"net/http"
	"time"
)

// netStats holds the raw measurements. Each pair of fields is independently
// optional — a check that failed or timed out just reports !OK rather than
// aborting the whole diagnosis (same collector-independence pattern as why).
type netStats struct {
	DNSMs          float64
	DNSOK          bool
	LatencyMs      float64
	LatencyOK      bool
	ThroughputMbps float64
	ThroughputOK   bool
}

// latencyTargets are dialed directly by IP:port so the latency measurement
// isn't itself gated on DNS working — a separate, independent signal from
// collectDNS. Two targets guard against one being firewalled or down.
var latencyTargets = []string{"1.1.1.1:443", "8.8.8.8:443"}

func collectDNS() (ms float64, ok bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	start := time.Now()
	if _, err := net.DefaultResolver.LookupHost(ctx, "cloudflare.com"); err != nil {
		return 0, false
	}
	return elapsedMs(start), true
}

func collectLatency() (ms float64, ok bool) {
	best := 0.0
	found := false
	for _, target := range latencyTargets {
		start := time.Now()
		conn, err := net.DialTimeout("tcp", target, 2*time.Second)
		if err != nil {
			continue
		}
		conn.Close()
		elapsed := elapsedMs(start)
		if !found || elapsed < best {
			best = elapsed
			found = true
		}
	}
	return best, found
}

// collectThroughput downloads from Cloudflare's public speed-test endpoint
// under a hard deadline. A slow link just means the copy gets cut short by
// the context — whatever bytes arrived by then still yield an honest (if
// rough) throughput figure, so a partial transfer isn't treated as failure.
func collectThroughput() (mbps float64, ok bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://speed.cloudflare.com/__down?bytes=25000000", nil)
	if err != nil {
		return 0, false
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return 0, false
	}
	defer resp.Body.Close()

	start := time.Now()
	n, _ := io.Copy(io.Discard, resp.Body)
	elapsed := time.Since(start).Seconds()
	if n == 0 || elapsed <= 0 {
		return 0, false
	}
	return float64(n) * 8 / 1e6 / elapsed, true
}

func elapsedMs(start time.Time) float64 {
	return float64(time.Since(start).Microseconds()) / 1000.0
}

//go:build darwin

package main

// platformHintSet returns macOS-specific next steps. networkQuality is the
// built-in, no-install option for a fuller picture than this one-shot check
// can honestly give.
func platformHintSet() platformHints {
	return platformHints{
		NoConnectivity: []string{
			"Check Wi-Fi/cable and router power",
			"`wdutil info` for link-layer status",
		},
		DNS: []string{
			"`scutil --dns` to inspect resolver config",
			"Flush cache: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`",
		},
		Latency: []string{
			"`networkQuality -v` for Apple's fuller latency/responsiveness picture",
			"Check for Wi-Fi congestion in System Settings > Wi-Fi",
		},
		Throughput: []string{
			"`networkQuality -v` for Apple's own throughput numbers",
			"If on Wi-Fi, try wired to isolate the radio",
		},
	}
}

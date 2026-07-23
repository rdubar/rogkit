//go:build linux

package main

import (
	"os"
	"strings"
)

const piModelPath = "/proc/device-tree/model"

const piNote = "On this Pi, wired eth0 tested faster/more consistent than Wi-Fi — see docs/reports/pi5-network-comparison-2026-05-02.md"

// platformHintSet returns Linux-specific next steps, with an extra nudge
// toward wired Ethernet when running on a Raspberry Pi — this repo already
// has a measured comparison for that exact tradeoff.
func platformHintSet() platformHints {
	h := platformHints{
		NoConnectivity: []string{
			"`ip a` and `ip route` to check for a default route",
			"`ethtool <iface>` to check the physical link",
		},
		DNS: []string{
			"`resolvectl status` or `cat /etc/resolv.conf`",
		},
		Latency: []string{
			"`mtr <host>` to see where latency is introduced hop-by-hop",
			"`ip -s link` for interface errors",
		},
		Throughput: []string{
			"`ethtool <iface>` for link speed/duplex",
			"`ip -s link` for retransmits/errors",
		},
	}
	if isRaspberryPi(piModelPath) {
		h.NoConnectivity = append(h.NoConnectivity, piNote)
		h.Latency = append(h.Latency, piNote)
		h.Throughput = append(h.Throughput, piNote)
	}
	return h
}

func isRaspberryPi(modelPath string) bool {
	data, err := os.ReadFile(modelPath)
	if err != nil {
		return false
	}
	return strings.Contains(string(data), "Raspberry Pi")
}

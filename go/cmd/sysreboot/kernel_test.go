package main

import (
	"slices"
	"testing"
)

func TestParseKernelRelease(t *testing.T) {
	cases := []struct {
		release string
		version []int
		flavour string
	}{
		{"6.18.50+rpt-rpi-2712", []int{6, 18, 50}, "+rpt-rpi-2712"},
		{"6.12.73+deb13-amd64", []int{6, 12, 73}, "+deb13-amd64"},
		{"6.8.0-45-generic", []int{6, 8, 0, 45}, "-generic"},
		{"6.6.31-16k+", []int{6, 6, 31}, "-16k+"},
		{"6.1.21-v8+", []int{6, 1, 21}, "-v8+"},
		{"6.1.0", []int{6, 1, 0}, ""},
		{"not-a-kernel", nil, "not-a-kernel"},
		{"", nil, ""},
	}
	for _, c := range cases {
		version, flavour := parseKernelRelease(c.release)
		if !slices.Equal(version, c.version) || flavour != c.flavour {
			t.Errorf("parseKernelRelease(%q) = %v, %q; want %v, %q",
				c.release, version, flavour, c.version, c.flavour)
		}
	}
}

func TestNewerInstalledKernel(t *testing.T) {
	// The Pi 5 this was found on: both flavours of three kernels installed.
	pi := []string{
		"/boot/vmlinuz-6.18.39+rpt-rpi-2712",
		"/boot/vmlinuz-6.18.39+rpt-rpi-v8",
		"/boot/vmlinuz-6.18.50+rpt-rpi-2712",
		"/boot/vmlinuz-6.18.50+rpt-rpi-v8",
		"/boot/vmlinuz-6.18.60+rpt-rpi-2712",
		"/boot/vmlinuz-6.18.60+rpt-rpi-v8",
	}
	cases := []struct {
		name    string
		running string
		images  []string
		want    string
	}{
		{"pending update", "6.18.50+rpt-rpi-2712\n", pi, "6.18.60+rpt-rpi-2712"},
		{"other flavour pending", "6.18.50+rpt-rpi-v8", pi, "6.18.60+rpt-rpi-v8"},
		{"already on newest", "6.18.60+rpt-rpi-2712", pi, ""},
		{"only another flavour is newer", "6.18.60+rpt-rpi-2712",
			[]string{"/boot/vmlinuz-6.18.70+rpt-rpi-v8"}, ""},
		{"compares as numbers, not text", "6.9.0-generic",
			[]string{"/boot/vmlinuz-6.10.0-generic"}, "6.10.0-generic"},
		{"ubuntu abi bump", "6.8.0-45-generic",
			[]string{"/boot/vmlinuz-6.8.0-45-generic", "/boot/vmlinuz-6.8.0-49-generic"}, "6.8.0-49-generic"},
		{"running newer than anything in /boot", "6.18.70+rpt-rpi-2712", pi, ""},
		{"ignores other files", "6.8.0-45-generic",
			[]string{"/boot/config-6.8.0-49-generic", "/boot/vmlinuz"}, ""},
		{"nothing in /boot", "6.18.50+rpt-rpi-2712", nil, ""},
		{"unreadable running release", "", pi, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := newerInstalledKernel(c.running, c.images); got != c.want {
				t.Errorf("newerInstalledKernel(%q) = %q, want %q", c.running, got, c.want)
			}
		})
	}
}

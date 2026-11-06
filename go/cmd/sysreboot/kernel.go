package main

import (
	"path/filepath"
	"strconv"
	"strings"
)

// parseKernelRelease splits a kernel release string into its leading numeric
// version and the flavour that follows it:
//
//	6.18.50+rpt-rpi-2712 -> [6 18 50], "+rpt-rpi-2712"
//	6.8.0-45-generic     -> [6 8 0 45], "-generic"
//	6.6.31-16k+          -> [6 6 31], "-16k+"
//
// A number only counts as version if it stands alone, so flavour parts like
// "16k" stay in the flavour.
func parseKernelRelease(release string) (version []int, flavour string) {
	pos := 0
	for pos < len(release) {
		start := pos
		if len(version) > 0 {
			if c := release[pos]; c != '.' && c != '-' {
				break
			}
			start++
		}
		end := start
		for end < len(release) && release[end] >= '0' && release[end] <= '9' {
			end++
		}
		if end == start {
			break
		}
		if end < len(release) && !strings.ContainsRune(".-+", rune(release[end])) {
			break
		}
		n, err := strconv.Atoi(release[start:end])
		if err != nil {
			break
		}
		version = append(version, n)
		pos = end
	}
	return version, release[pos:]
}

// kernelVersionNewer compares numerically, component by component; with an
// equal prefix, the longer version is the newer one.
func kernelVersionNewer(a, b []int) bool {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return len(a) > len(b)
}

// newerInstalledKernel returns the newest installed kernel of the running
// kernel's flavour if it is newer than the running one, or "" if there is
// none. Flavours must match because a machine can carry kernels it never
// boots: a Raspberry Pi 5 has both rpi-2712 and rpi-v8 installed.
//
// images are paths like /boot/vmlinuz-6.18.60+rpt-rpi-2712. /boot is used
// rather than /lib/modules because removed kernels leave folders behind there.
func newerInstalledKernel(running string, images []string) string {
	newest, flavour := parseKernelRelease(strings.TrimSpace(running))
	if len(newest) == 0 {
		return ""
	}
	found := ""
	for _, image := range images {
		release, ok := strings.CutPrefix(filepath.Base(image), "vmlinuz-")
		if !ok {
			continue
		}
		version, imageFlavour := parseKernelRelease(release)
		if imageFlavour == flavour && kernelVersionNewer(version, newest) {
			newest, found = version, release
		}
	}
	return found
}

//go:build darwin && cgo

package main

/*
#include <libproc.h>
#include <sys/resource.h>

static int phys_footprint(int pid, unsigned long long *out) {
	struct rusage_info_v0 ri;
	if (proc_pid_rusage(pid, RUSAGE_INFO_V0, (rusage_info_t *)&ri) != 0) {
		return -1;
	}
	*out = ri.ri_phys_footprint;
	return 0;
}
*/
import "C"

// applyFootprint swaps each process's RSS for its physical footprint — the
// "Memory" column in Activity Monitor, which includes compressed and
// swapped-out pages. RSS hides exactly those, so under memory pressure the
// real hogs (idle browser tabs, Electron renderers) drop out of the list.
// The kernel only reports footprint for our own processes without root;
// everything else keeps its RSS.
func applyFootprint(procs []proc) {
	for i := range procs {
		var fp C.ulonglong
		if C.phys_footprint(C.int(procs[i].pid), &fp) == 0 && uint64(fp) > 0 {
			procs[i].rss = uint64(fp)
		}
	}
}

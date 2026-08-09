// Command rosetta reports which running processes are executing under
// Rosetta 2 translation on Apple Silicon, grouped by app. The one-shot
// check is a single kern.proc.all sysctl read plus one `ps` call — already
// instant, so no daemon is needed to speed it up. `--watch` instead
// backgrounds a small daemon that fires a macOS notification the moment a
// new app launches under translation; `--stop` tears it down.
package main

import (
	"flag"
	"fmt"
	"os"
	"runtime"
)

func main() {
	if runtime.GOOS != "darwin" || runtime.GOARCH != "arm64" {
		fmt.Fprintf(os.Stderr, "rosetta: Apple Silicon only — Rosetta 2 doesn't exist on %s/%s.\n", runtime.GOOS, runtime.GOARCH)
		os.Exit(1)
	}

	jsonOut := flag.Bool("json", false, "Output JSON for automation")
	quiet := flag.Bool("q", false, "Plain output, no color")
	flag.BoolVar(quiet, "quiet", false, "Plain output (alias for -q)")
	watch := flag.Bool("watch", false, "Start (or confirm) a background watcher that notifies when a new Rosetta process launches")
	stop := flag.Bool("stop", false, "Stop the background watcher")
	daemon := flag.Bool("daemon", false, "internal: run as the background watcher (do not call directly)")
	flag.Parse()

	switch {
	case *daemon:
		runDaemon()
		return
	case *stop:
		stopDaemon()
		return
	case *watch:
		startWatch()
		return
	}

	apps, err := scan()
	if err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: %v\n", err)
		os.Exit(1)
	}

	if *jsonOut {
		printJSON(apps)
		return
	}
	printReport(apps, *quiet || !isTerminal())
}

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

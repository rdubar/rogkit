// Command squeeze distills a log stream into its unique templates: variable
// fields (timestamps, IDs, IPs, paths, numbers) are masked out, structurally
// identical lines are counted once, and --fit budgets the output to roughly
// N tokens by eliding bulk noise first — built for when the primary
// consumer is a context window, not a scrollback buffer.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"sort"
)

func main() {
	fit := flag.Int("fit", 0, "Budget output to roughly N tokens (rarest/error-shaped templates survive first)")
	quiet := flag.Bool("q", false, "Plain output, no color")
	flag.BoolVar(quiet, "quiet", false, "Plain output, no color (alias for -q)")
	flag.Parse()

	path := flag.Arg(0)
	if path == "" && stdinIsTerminal() {
		// No file arg and nothing piped in — reading stdin here would just
		// block silently waiting on terminal input, which looks like a hang.
		fmt.Fprintln(os.Stderr, "squeeze: no input — pass a file (`squeeze app.log`) or pipe one in (`cmd | squeeze`)")
		os.Exit(1)
	}

	lines, err := readLines(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "squeeze: %v\n", err)
		os.Exit(1)
	}

	clusters := clusterLines(lines)
	sort.SliceStable(clusters, func(i, j int) bool { return clusters[i].Count > clusters[j].Count })

	elidedCount, elidedLines := 0, 0
	if *fit > 0 {
		clusters, elidedCount, elidedLines = selectForBudget(clusters, *fit)
	}

	color := !*quiet && isTerminal()
	printClusters(clusters, color)
	if elidedCount > 0 {
		fmt.Printf("… +%d more template(s) elided (~%d lines)\n", elidedCount, elidedLines)
	}
}

// readLines reads from path, or stdin when path is "" or "-".
func readLines(path string) ([]string, error) {
	var f *os.File
	if path == "" || path == "-" {
		f = os.Stdin
	} else {
		var err error
		f, err = os.Open(path)
		if err != nil {
			return nil, err
		}
		defer f.Close()
	}

	var lines []string
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines, scanner.Err()
}

func isTerminal() bool {
	stat, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

func stdinIsTerminal() bool {
	stat, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

const (
	colorReset = "\x1b[0m"
	colorCrit  = "\x1b[1;31m"
)

func printClusters(clusters []cluster, color bool) {
	if len(clusters) == 0 {
		fmt.Println("(no input)")
		return
	}
	for _, c := range clusters {
		line := formatCluster(c)
		if !color {
			fmt.Println(line)
			continue
		}
		if c.Errorish {
			fmt.Println(colorCrit + line + colorReset)
		} else {
			fmt.Println(line)
		}
	}
}

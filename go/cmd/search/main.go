package main

import (
	"os"

	searchcmd "github.com/rdubar/rogkit/go/internal/search"
)

func main() {
	if code := searchcmd.Run(os.Args[1:], os.Stdout, os.Stderr, "search"); code != 0 {
		os.Exit(code)
	}
}

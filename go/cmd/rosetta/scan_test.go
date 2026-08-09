package main

import "testing"

func TestCanonicalAppName(t *testing.T) {
	cases := map[string]string{
		"/Applications/Docker.app/Contents/MacOS/Docker Desktop Helper (Renderer)": "Docker",
		"/Applications/Docker.app/Contents/MacOS/com.docker.backend":               "Docker",
		"/usr/local/bin/DriveThruRPG":                                              "DriveThruRPG",
		"loginwindow Helper":                                                       "loginwindow",
		"loginwindow":                                                              "loginwindow",
	}
	for in, want := range cases {
		if got := canonicalAppName(in); got != want {
			t.Errorf("canonicalAppName(%q) = %q, want %q", in, got, want)
		}
	}
}

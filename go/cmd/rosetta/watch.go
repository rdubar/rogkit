package main

import (
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const pollInterval = 3 * time.Second

// stateDir follows the same inline XDG_STATE_HOME idiom as drift's
// store.go — state, not config, so it stays out of ~/.config/rogkit.
func stateDir() (string, error) {
	base := os.Getenv("XDG_STATE_HOME")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		base = filepath.Join(home, ".local", "state")
	}
	dir := filepath.Join(base, "rogkit", "rosetta")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	return dir, nil
}

func pidFilePath() (string, error) {
	dir, err := stateDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "watch.pid"), nil
}

// runningDaemonPID returns the pid recorded in the pid file if that
// process is still alive, or 0 if there is no live watcher.
func runningDaemonPID() (int, error) {
	path, err := pidFilePath()
	if err != nil {
		return 0, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0, nil
		}
		return 0, err
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return 0, nil
	}
	if err := syscall.Kill(pid, 0); err != nil {
		return 0, nil
	}
	return pid, nil
}

// startWatch spawns a detached copy of this binary with --daemon, unless
// one is already running.
func startWatch() {
	pid, err := runningDaemonPID()
	if err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: %v\n", err)
		os.Exit(1)
	}
	if pid != 0 {
		fmt.Printf("Already watching (pid %d). Run `rosetta --stop` to stop.\n", pid)
		return
	}

	self, err := os.Executable()
	if err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: %v\n", err)
		os.Exit(1)
	}
	cmd := exec.Command(self, "--daemon")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: failed to start watcher: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Watching for new Rosetta process launches in the background (pid %d).\nRun `rosetta --stop` to stop.\n", cmd.Process.Pid)
}

func stopDaemon() {
	pid, err := runningDaemonPID()
	if err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: %v\n", err)
		os.Exit(1)
	}
	if pid == 0 {
		fmt.Println("No watcher running.")
		return
	}
	if err := syscall.Kill(pid, syscall.SIGTERM); err != nil {
		fmt.Fprintf(os.Stderr, "rosetta: failed to stop watcher (pid %d): %v\n", pid, err)
		os.Exit(1)
	}
	path, _ := pidFilePath()
	_ = os.Remove(path)
	fmt.Printf("Stopped watcher (pid %d).\n", pid)
}

// runDaemon polls for translated processes every pollInterval and fires a
// macOS notification the moment a new app name appears that wasn't present
// on the previous poll — edge-triggered so relaunching an app re-notifies
// instead of firing once and going silent forever. The apps already
// translated at watcher-startup are recorded silently so starting --watch
// doesn't immediately fire a notification for every app already running.
func runDaemon() {
	path, err := pidFilePath()
	if err != nil {
		return
	}
	if err := os.WriteFile(path, []byte(strconv.Itoa(os.Getpid())), 0o644); err != nil {
		return
	}
	defer os.Remove(path)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)

	seen := make(map[string]bool)
	if apps, err := scan(); err == nil {
		for _, a := range apps {
			seen[a.Name] = true
		}
	}

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-sig:
			return
		case <-ticker.C:
		}

		apps, err := scan()
		if err != nil {
			continue
		}
		current := make(map[string]bool, len(apps))
		for _, a := range apps {
			current[a.Name] = true
			if !seen[a.Name] {
				notify(a.Name)
			}
		}
		seen = current
	}
}

func notify(appName string) {
	title := "Rosetta"
	msg := fmt.Sprintf("%s just launched under Rosetta translation", appName)
	script := fmt.Sprintf("display notification %s with title %s", quoteAppleScript(msg), quoteAppleScript(title))
	_ = exec.Command("osascript", "-e", script).Run()
}

// quoteAppleScript wraps s in AppleScript string-literal quotes, escaping
// backslashes and double quotes (AppleScript has no other string escapes).
func quoteAppleScript(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	return `"` + s + `"`
}

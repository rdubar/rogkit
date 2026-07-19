package main

import (
	"bufio"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// siblingBinary locates another rogkit Go tool by checking the directory
// drift itself was launched from first (they're all installed to the same
// GOBIN by scripts/build_go.sh), falling back to $PATH — this way drift
// still finds `space`/`mem` even when invoked outside an interactive shell
// (e.g. a LaunchAgent) where the `aliases` file's PATH export never ran.
func siblingBinary(name string) string {
	if exe, err := os.Executable(); err == nil {
		candidate := filepath.Join(filepath.Dir(exe), name)
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
	}
	if path, err := exec.LookPath(name); err == nil {
		return path
	}
	return ""
}

// collectDisk shells out to `space --json` rather than re-implementing
// statfs(2) — composition over a shared internal package, since both
// binaries already ship to the same directory.
func collectDisk() []DiskEntry {
	bin := siblingBinary("space")
	if bin == "" {
		return nil
	}
	out, err := exec.Command(bin, "--json").Output()
	if err != nil {
		return nil
	}
	var parsed struct {
		Mounts []struct {
			Path       string  `json:"path"`
			UsedBytes  uint64  `json:"used_bytes"`
			TotalBytes uint64  `json:"total_bytes"`
			UsagePct   float64 `json:"usage_pct"`
		} `json:"mounts"`
	}
	if err := json.Unmarshal(out, &parsed); err != nil {
		return nil
	}
	entries := make([]DiskEntry, 0, len(parsed.Mounts))
	for _, m := range parsed.Mounts {
		entries = append(entries, DiskEntry{Path: m.Path, UsedBytes: m.UsedBytes, TotalBytes: m.TotalBytes, UsagePct: m.UsagePct})
	}
	return entries
}

// collectMem shells out to `mem --json -n 30` for the top 30 apps by RSS —
// enough to catch anything that grew notably without storing every process
// on the machine in every snapshot.
func collectMem() []MemEntry {
	bin := siblingBinary("mem")
	if bin == "" {
		return nil
	}
	out, err := exec.Command(bin, "--json", "-n", "30").Output()
	if err != nil {
		return nil
	}
	var parsed struct {
		Groups []struct {
			Name     string  `json:"name"`
			RSSBytes uint64  `json:"rss_bytes"`
			PctMem   float64 `json:"pct_mem"`
		} `json:"groups"`
	}
	if err := json.Unmarshal(out, &parsed); err != nil {
		return nil
	}
	entries := make([]MemEntry, 0, len(parsed.Groups))
	for _, g := range parsed.Groups {
		entries = append(entries, MemEntry{Name: g.Name, RSSBytes: g.RSSBytes, PctMem: g.PctMem})
	}
	return entries
}

// collectPackages tries brew (macOS, and Linuxbrew if present) and dpkg-query
// (Debian/Ubuntu Linux), skipping whichever isn't installed. Keys are
// "<manager>:<name>" so the same package name under two managers never
// collides.
func collectPackages() map[string]string {
	pkgs := make(map[string]string)
	if path, err := exec.LookPath("brew"); err == nil {
		if out, err := exec.Command(path, "list", "--versions").Output(); err == nil {
			for k, v := range parseBrewList(out) {
				pkgs["brew:"+k] = v
			}
		}
	}
	if path, err := exec.LookPath("dpkg-query"); err == nil {
		if out, err := exec.Command(path, "-W", "-f=${Package}\t${Version}\n").Output(); err == nil {
			for k, v := range parseDpkgList(out) {
				pkgs["dpkg:"+k] = v
			}
		}
	}
	if len(pkgs) == 0 {
		return nil
	}
	return pkgs
}

func parseBrewList(out []byte) map[string]string {
	pkgs := make(map[string]string)
	scanner := bufio.NewScanner(strings.NewReader(string(out)))
	for scanner.Scan() {
		fields := strings.Fields(scanner.Text())
		if len(fields) < 2 {
			continue
		}
		pkgs[fields[0]] = fields[1]
	}
	return pkgs
}

func parseDpkgList(out []byte) map[string]string {
	pkgs := make(map[string]string)
	scanner := bufio.NewScanner(strings.NewReader(string(out)))
	for scanner.Scan() {
		fields := strings.SplitN(scanner.Text(), "\t", 2)
		if len(fields) != 2 || fields[0] == "" {
			continue
		}
		pkgs[fields[0]] = fields[1]
	}
	return pkgs
}

// collectRepos scans each root's immediate children, and one level deeper
// for children-of-children, for git repos (depth <= 2 from root — covers
// both "~/dev/<repo>" and "~/dev/<group>/<repo>" layouts without a full
// recursive walk).
func collectRepos(roots []string) []RepoEntry {
	var repos []RepoEntry
	for _, root := range roots {
		entries, err := os.ReadDir(root)
		if err != nil {
			continue
		}
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			dir := filepath.Join(root, e.Name())
			if isGitRepo(dir) {
				if r, ok := repoStatus(e.Name(), dir); ok {
					repos = append(repos, r)
				}
				continue
			}
			nested, err := os.ReadDir(dir)
			if err != nil {
				continue
			}
			for _, ne := range nested {
				if !ne.IsDir() {
					continue
				}
				ndir := filepath.Join(dir, ne.Name())
				if isGitRepo(ndir) {
					if r, ok := repoStatus(e.Name()+"/"+ne.Name(), ndir); ok {
						repos = append(repos, r)
					}
				}
			}
		}
	}
	return repos
}

func isGitRepo(dir string) bool {
	info, err := os.Stat(filepath.Join(dir, ".git"))
	return err == nil && (info.IsDir() || info.Mode().IsRegular()) // regular file for worktrees/submodules
}

func repoStatus(name, dir string) (RepoEntry, bool) {
	statusOut, err := exec.Command("git", "-C", dir, "status", "--porcelain").Output()
	if err != nil {
		return RepoEntry{}, false
	}
	dirty := 0
	for _, line := range strings.Split(strings.TrimRight(string(statusOut), "\n"), "\n") {
		if strings.TrimSpace(line) != "" {
			dirty++
		}
	}

	ahead := 0
	if out, err := exec.Command("git", "-C", dir, "rev-list", "--left-right", "--count", "HEAD...@{u}").Output(); err == nil {
		fields := strings.Fields(string(out))
		if len(fields) == 2 {
			ahead, _ = strconv.Atoi(fields[0])
		}
	}

	return RepoEntry{Name: name, Dirty: dirty, Ahead: ahead}, true
}

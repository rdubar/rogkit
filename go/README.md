## Rogkit Go Tools

This directory contains the Go-based command-line utilities that support the rogkit toolchain.

### finder

`finder` is the primary search utility. It offers flexible filtering (glob/substring patterns, case sensitivity, hidden files, depth limits, and `.gitignore`/`.fdignore`/`.ignore` support) and mirrors the behavior of commonly used tools like `fd`. When run with `--time` and `--verbose`, it reports traversal statistics; `--timer` prints just the elapsed time.

### fastfind (experimental)

`fastfind` is an experimental walker optimized around [`github.com/karrick/godirwalk`](https://github.com/karrick/godirwalk). It trades features for maximum throughput:

- always runs directory enumeration concurrently across CPU cores
- only exposes a subset of `finder` flags (no relative paths, size reporting, or include/exclude extension filters)
- traversal order is non-deterministic due to concurrency

Use it when you need the fastest possible scan across very large trees, and be aware that behavior may change as we continue to tune performance.


### search

`search` is a multicore content searcher that builds on the `finder` traversal engine. It scans files with a worker pool (defaulting to `runtime.NumCPU` workers) and short-circuits once an optional match limit is reached. Key features:

- Smart-case matching (or explicit `--ignore-case` / `--case-sensitive`)
- Streaming file reads with boundary-safe substring checks (no `io.ReadAll`)
- Support for include/exclude extensions, path filters, hidden files, depth limits, and ignore files
- Optional `--count`, `--limit`, `--with-size`, `--relative`, and timing/statistics via `--verbose --time`
- Graceful error reporting with `--show-errors`

Example:

```bash
search --path ~/projects --filter '*.go' "panic" "TODO"
```


### uprec

`uprec` reports the longest uptimes a machine has recorded and where the current run ranks among them — the "best uptime ever" figure nothing on a stock mac or Linux box keeps, since `uptime` only knows the boot it is in.

```sh
uprec          # ranked table, current run marked with ->
uprec -1       # up 9d 1h · rank 3 of 7 · record 16d 11h (2026-07-08) · 2 unclean
uprec -q       # plain pipe-delimited rows (also chosen automatically off a TTY)
uprec --json   # full history plus a summary block
uprec -a       # every session, not just the top 10
```

#### Where the history comes from

Whatever exists is read and merged by boot time; nothing is required.

| Source | What it contributes |
|--------|--------------------|
| [`uptimed`](https://github.com/rpodgorny/uptimed/) | A high-score table kept by a daemon that snapshots `/proc/uptime` every minute. Read from `/var/spool/uptimed/records`, `/var/lib/uptimed/records`, or either Homebrew prefix. |
| wtmpdb | Boot and shutdown records on Debian 13+, read via `wtmpdb last`. |
| `wtmp` | Boot and shutdown records on older Linux, including gzipped rotated generations. |
| `last(1)` | The same, on macOS, where the login database lives in the ASL store. |
| The running kernel | The current run, exactly, from `kern.boottime` or `/proc/uptime`. |
| `~/.local/state/rogkit/uprec.records` | uprec's own file, rewritten every run so history outlives log rotation. Uses uptimed's `uptime:boot_epoch:system` format, plus a fourth field recording whether the run ended cleanly. |

#### What it does not do

- **It cannot invent history that was never recorded.** uprec only reports boots that something on the machine wrote down. On a machine where nothing was recording, history starts the first time uprec runs, and no amount of re-running changes that.
- **It does not run a daemon.** Between runs, nothing is watching. A run's length is known exactly only if a shutdown record exists for it; otherwise the best estimate is the last snapshot uprec or uptimed took. This is the reason to install `uptimed`, which snapshots every minute.
- **It does not judge.** No verdict on whether an uptime is good, no reboot advice — that is `sysreboot`'s job.
- **Retention limits how far back it can see.** `wtmp` rotation and journald retention bound the initial recovery. Once uprec has run, its own file preserves what it saw, but it cannot reach back past what was on disk the first time.
- **Timestamps are only as precise as the source.** macOS `last(1)` prints whole minutes, so a boot recovered from it can sit up to a minute early; the running kernel and stored records are exact, and the more precise source wins when they disagree.

#### Status column

| Status | Meaning |
|--------|---------|
| `clean` | A shutdown record was found for that run |
| `unclean` | The next thing logged was another boot — a crash, a power cut, or a hard reset |
| `unknown` | The run ended, but no source recorded how. `uptimed`'s format does not track this, so a history recovered from it alone reports `unknown` rather than claiming every boot was clean |
| `current` | Still running |

The unclean count is often the more useful number: "4 of the last 10 boots were unclean" says more about a server's health than the record itself.

#### Getting better records

On a machine that has never recorded boots — which now includes a stock Debian 13 install, where boot logging moved to wtmpdb and `wtmp` keeps only sessions:

```sh
sudo apt install uptimed wtmpdb        # Debian/Ubuntu/Raspberry Pi OS
sudo systemctl enable --now uptimed    # installing it is not enough
brew install uptimed                   # macOS
brew services start uptimed
```

Installing `uptimed` without enabling it records nothing at all, which is easy to miss because the package looks present.

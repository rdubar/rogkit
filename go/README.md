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



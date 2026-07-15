# Bugs

Standard maintenance backlog for issues found during review or day-to-day use.

## Open

### 2026-07-15 — sysreboot uncommitted changes (code review)

- [P3] `go/cmd/sysreboot/platform_linux.go`: `estimateMemAvailable` fallback fires on `s.MemAvailable == 0`, which conflates "field absent" (pre-3.14 kernel) with "field present and genuinely zero" (severe memory pressure) — under real OOM conditions the heuristic could paper over a legitimate 0 and understate severity.

- [P3] `go/cmd/sysreboot/platform_linux.go`: `readRebootMarkerPath` stats both `/run/reboot-required` and `/var/run/reboot-required` every run; `/var/run` is a standard symlink to `/run` on the tool's own stated target distros (Debian/Ubuntu/Raspberry Pi OS), so the second stat is redundant work rather than real robustness.

## Known Platform Quirks

- Many utilities assume macOS or a Unix-like environment for subprocesses, filesystem layout, or external tools.
- Media utilities have more machine-specific behavior than the simpler text/data helpers and may depend on local paths or optional binaries.

## Feature Ideas

- secrets.toml: split secrets out of `config.toml` — DONE 2026-04-19



- `cdu`: cross-platform AI usage dashboard — one summary line per active AI tool
  Status: idea, worth designing before building
  Goal: replace the per-tool approach (clu for Claude, codu for Codex, …) with a single
  utility that queries each AI's local data store and emits one summary line per provider.
  Default output (one line per provider, e.g.):
    claude   today 42k tok  │ rate 1.2k/5min  │ cost ~$0.18
    codex    today 18k tok  │ 7 threads        │ top-dir: rogkit
  Design principles:
  - Provider-per-module architecture: each provider is a self-contained plugin that
    returns a standard summary dict; `cdu` aggregates and renders them.
  - Cross-platform from day one: no macOS-only paths or subprocess assumptions.
    Each provider must declare which platforms it supports and skip gracefully.
  - Loose schema: providers differ wildly (Claude JSONL vs Codex SQLite vs API-only
    tools), so the shared contract is minimal — name, today_tokens, a short note string.
  - Default: one-line-per-provider summary (like `clu --brief`).
    Flags: `--provider claude` to drill into one, `--json` for structured output.
  Known providers to target:
  - Claude Code: already solved in `clu` — extract that logic as the claude provider.
  - Codex: `~/.codex/state_5.sqlite`, thread-level token/accounting metadata.
  - Others (Gemini CLI, Cursor, Copilot): only if local data exists; skip otherwise.
  Non-goals:
  - Cloud-authoritative totals or billing reconciliation.
  - Keychain / credential access (read-only local files only).
  - Becoming a rewrite of `clu` — migrate clu's logic in, don't break clu users.

## Fixed

### 2026-07-15

- [P1] `go/cmd/sysreboot/main_test.go` had no build tag but referenced Linux-only symbols declared only in `platform_linux.go` (`//go:build linux`), breaking `go build`/`go vet`/`go test ./...` on any non-Linux GOOS — `TestReadRebootMarkerPath`, `TestReadRebootRequiredPkgs`, `TestEstimateMemAvailable` moved into a new `platform_linux_test.go` with `//go:build linux`.

- [P1] `go/cmd/sysreboot/platform_darwin.go`: `readLoadAvg`/`readSwapUsage` had switched to `unix.Sysctl(...)` (raw syscall wrapper) on OIDs that are `CTLTYPE_STRUCT` (`struct loadavg`, `struct xsw_usage`) — the raw syscall returns binary struct bytes, not the formatted text the CLI synthesizes, so this silently zeroed Load1/Load5/Load15 and SwapTotal/SwapUsed with no error surfaced. Fixed by decoding via `unix.SysctlRaw` against the real struct layout (with a text-format fallback), matching the approach already used for `kern.boottime` via `unix.SysctlTimeval`.

- [P4] `go/cmd/sysreboot/platform_darwin.go:37`: stale comment above `readUptimeSysctl` updated to reflect that it uses `unix.SysctlTimeval`, not manual byte decoding.

- [P4] `go/cmd/sysreboot/platform_linux.go`: removed the mutable package-level `rebootMarkerPaths` var in favor of passing candidate paths as a function parameter to `readRebootMarkerPath`, avoiding a `t.Parallel()` race.

### 2026-04-19

- [P2] `url` normalizer mutates credentials — `normalize_url()` now rebuilds netloc from parsed components, lowercasing only the hostname and preserving username/password casing.

- [P3] `note` appends under the wrong section when file is reordered — `append_note()` now finds the next `##` heading after today's section and inserts before it instead of appending to EOF.

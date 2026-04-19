# Bugs

Standard maintenance backlog for issues found during review or day-to-day use.

## Open

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

### 2026-04-19

- [P2] `url` normalizer mutates credentials — `normalize_url()` now rebuilds netloc from parsed components, lowercasing only the hostname and preserving username/password casing.

- [P3] `note` appends under the wrong section when file is reordered — `append_note()` now finds the next `##` heading after today's section and inserts before it instead of appending to EOF.

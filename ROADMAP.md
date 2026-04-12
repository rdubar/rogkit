# rogkit — New Tools Roadmap

Tools identified as genuine gaps vs a standard Unix power-user toolkit.
Both planned batches below are now implemented and covered by tests. The
remaining work is human verification from the README checklist.

---

## Group 1 — Pure stdlib (no new deps)

- [x] **`note`** — Append a timestamped note to `~/notes.md`; `note -l` to list/search
  - `note "remember this"` → `## 2026-04-12 21:30\nremember this\n`
  - `note -l [query]` → print last N entries, optional grep filter
  - Plain stdlib: `pathlib`, `datetime`, `argparse`

- [x] **`json`** — Pretty-print or query JSON from file or stdin
  - `json file.json` or `echo '{}' | json`
  - `-q .key.path` lightweight key extraction (no jq required)
  - `json --keys` to list top-level keys
  - stdlib `json` + Rich syntax highlighting; fast path if `jq` is on PATH

- [x] **`csv`** — Render a CSV as a Rich table in the terminal
  - `csv file.csv` — full table view; `-n 20` for first N rows
  - `-c col1,col2` to select columns; `-s col` to sort by column
  - stdlib `csv` + Rich Table; no pandas

- [x] **`env`** — Pretty-print environment variables with filtering
  - `env` — all vars as sorted Rich table
  - `env PATTERN` — case-insensitive substring filter on variable names
  - `env --val PATTERN` — search values instead of keys
  - stdlib `os.environ`; Rich table with key/value columns

---

## Group 2 — psutil-based (dep already in project)

- [x] **`procs`** — Find and optionally kill processes by fuzzy name
  - `procs foo` — list matching processes by name/command substring (pid, name, cpu%, mem%, cmd)
  - `procs foo --kill` — prompt-confirm kill; `--force` for SIGKILL
  - `psutil.process_iter()` — fully cross-platform (Mac + Linux)
  - Match on process name and command text; keep the interface simple

- [x] **`ports`** — Show listening ports with owning process
  - `ports` — all listening ports as Rich table (port, proto, pid, process name)
  - `ports 8080` — filter to specific port; `ports --proc foo` filter by process
  - `psutil.net_connections()` — cross-platform, no `lsof`/`ss` needed

- [x] **`myip`** — Show local network interfaces and external IP
  - Interfaces section: name, IP, netmask, MAC (via `psutil.net_if_addrs()`)
  - External IP: quick fetch from a reliable endpoint
  - Highlight the default route interface; skip loopback by default

---

## Group 3 — Network & Archive

- [x] **`httpcheck`** — Check HTTP status for one or more URLs
  - `httpcheck url [url ...]` or read URLs from stdin / file (`-f urls.txt`)
  - Shows: status code, redirect chain, response time, content-type
  - `--watch N` to re-check every N seconds
  - `requests` (already in project); Rich table output; exit 1 if any non-2xx

- [x] **`archive`** — Inspect or extract `.tar.gz`, `.zip`, `.tar.bz2`, `.gz`
  - `archive file.tar.gz` — list contents as Rich tree
  - `archive file.tar.gz path/in/archive` — extract single file to stdout
  - `archive -x file.tar.gz [dest/]` — full extract
  - stdlib `tarfile`, `zipfile`, `gzip` — no external deps; fully cross-platform

---

## Next Batch — Proposed Utilities

- [x] **`hash`** — Hash files or stdin with `md5`, `sha1`, `sha256`, or `sha512`
  - `hash file.iso`
  - `cat file.txt | hash --algo sha256`
  - stdlib `hashlib`; good for verification and scripting

- [x] **`url`** — Encode, decode, inspect, and normalize URLs/query strings
  - `url encode "hello world"`
  - `url parse "https://example.com?a=1&b=2"`
  - stdlib `urllib.parse`; high daily-use value

- [x] **`ts`** — Convert timestamps between epoch, ISO8601, local time, and UTC
  - `ts 1712947200`
  - `ts "2026-04-12T10:30:00Z"`
  - stdlib `datetime`; useful for logs and APIs

- [x] **`serve`** — Quick local static file server for the current directory
  - `serve`
  - `serve 9000`
  - stdlib `http.server`; ideal for previews and file sharing on localhost

- [x] **`jwt`** — Decode JWT header/payload without verification for inspection
  - `jwt eyJ...`
  - `pbpaste | jwt`
  - stdlib `base64` + `json`; no auth side effects, just decoding

- [x] **`dedupe`** — Find duplicate files by size and hash under a directory tree
  - `dedupe .`
  - `dedupe ~/Downloads --delete-empty`
  - stdlib `hashlib` + `pathlib`; high-value cleanup tool

---

## Notes

- All tools follow rogkit conventions: `argparse`, Rich with plain-text fallback,
  `get_invoking_cwd()` for CWD, entry in `aliases` file.
- Scaffold each with `/rogkit-tool <name> <description>`.
- `procs` + `ports` + `myip` can share a small `_proc_utils` helper if patterns repeat.
- `json` should degrade gracefully when input is invalid — show the parse error clearly.
- `serve` has been manually confirmed in-shell; the rest of the new commands
  remain tracked in the README human test queue until exercised by hand.

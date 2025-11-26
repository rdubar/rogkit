#!/usr/bin/env bash
# Remove Internet Archive padding directories (.____padding_file) quickly.
set -euo pipefail

ROOT="."
ROOT_ABS=""
CONFIRM="false"
VERBOSE="false"

usage() {
  cat <<'EOF'
padding.sh - find and optionally delete Internet Archive padding directories

Usage:
  padding.sh [--root PATH] [--confirm] [--verbose]

Options:
  --root PATH   Directory to scan (default: current directory).
  --confirm     Actually delete the matching directories. Without this, it is a dry run.
  --verbose     Show commands and per-path status.
  -h, --help    Show this help text.

Behavior:
  - Looks for directories named ".____padding_file".
  - Requires --confirm before deleting anything.
  - Uses `fd` if available for speed, otherwise falls back to find.

Examples:
  padding.sh --root ~/Downloads                  # list matches (no delete)
  padding.sh --root ~/Downloads --confirm        # delete matches
  padding.sh --root ~/Downloads --verbose --confirm
EOF
}

log() { printf '%s\n' "$*"; }
log_verbose() { [ "$VERBOSE" = "true" ] && printf '[verbose] %s\n' "$*"; }

while [ "${1-}" != "" ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --confirm) CONFIRM="true"; shift ;;
    --verbose) VERBOSE="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if ! ROOT_ABS=$(cd "$ROOT" 2>/dev/null && pwd); then
  log "Root path does not exist or is not a directory: $ROOT"
  exit 1
fi

log "Scanning for .____padding_file directories under: $ROOT_ABS"

if command -v fd >/dev/null 2>&1; then
  log_verbose "Using fd for discovery"
  FIND_CMD=(fd ".____padding_file" "$ROOT_ABS" -t d -H -I)
else
  log_verbose "fd not found; falling back to find"
  FIND_CMD=(find "$ROOT_ABS" -type d -name ".____padding_file")
fi

log_verbose "Discovery command: ${FIND_CMD[*]}"

matches=()
while IFS= read -r line; do
  [ -n "$line" ] && matches+=("$line")
done < <("${FIND_CMD[@]}" 2>/dev/null || true)

COUNT=${#matches[@]}
if [ "$COUNT" -eq 0 ]; then
  log "No padding directories found under: $ROOT_ABS"
  exit 0
fi

log "Found $COUNT padding director$( [ "$COUNT" -eq 1 ] && echo "y" || echo "ies"):"
for m in "${matches[@]}"; do
  log "  $m"
done

if [ "$CONFIRM" != "true" ]; then
  log ""
  log "Dry run only. Re-run with --confirm to delete these directories."
  exit 0
fi

log ""
log "Deleting..."
for m in "${matches[@]}"; do
  if [ -d "$m" ]; then
    log_verbose "rm -rf -- $m"
    rm -rf -- "$m"
    log "Deleted: $m"
  else
    log "Skipped (not found): $m"
  fi
done

log "Done."

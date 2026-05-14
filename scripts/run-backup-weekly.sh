#!/usr/bin/env bash
# run-backup-weekly.sh — invoked by the com.rdubar.backup-weekly LaunchAgent.
#
# Runs all configured rogkit backup sets (-b) and notifies via Notification
# Center on completion (success or failure). Logs to ~/Library/Logs/.
#
# To run by hand:
#   ~/dev/rogkit/scripts/run-backup-weekly.sh
#
# Per-machine config lives in ~/.config/rogkit/config.toml; sets are filtered
# by `--list-sets` if you want to inspect what `-b` will touch.

set -uo pipefail

# launchd hands us a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin). Prepend the
# locations where Homebrew and user-installed tools actually live, so age and
# any other brew-installed binary the backup process shells out to are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${UV:-$HOME/.local/bin/uv}"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/rogkit-backup-weekly.log"

mkdir -p "$LOG_DIR"

{
  echo ""
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) — backup -b start on $(hostname -s) ==="

  if [ ! -x "$UV" ]; then
    echo "ERROR: uv not executable at $UV"
    osascript -e 'display notification "Weekly backup FAILED: uv not found." with title "rogkit backup" sound name "Sosumi"' >/dev/null 2>&1 || true
    exit 127
  fi

  "$UV" run --directory "$ROOT_DIR" python -m rogkit_package.bin.backup -b
  rc=$?

  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) — backup -b exit $rc ==="

  if [ "$rc" -eq 0 ]; then
    osascript -e 'display notification "Weekly backup complete." with title "rogkit backup" sound name "Glass"' >/dev/null 2>&1 || true
  else
    osascript -e 'display notification "Weekly backup FAILED — check ~/Library/Logs/rogkit-backup-weekly.log" with title "rogkit backup" sound name "Sosumi"' >/dev/null 2>&1 || true
  fi

  exit "$rc"
} >> "$LOG_FILE" 2>&1

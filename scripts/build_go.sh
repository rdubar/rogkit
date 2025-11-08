#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT_DIR/go"

if ! command -v go >/dev/null 2>&1; then
    echo "Go toolchain not found. Install Go and try again." >&2
    exit 1
fi

if [ ! -d "$GO_DIR" ]; then
    echo "Go directory not found at $GO_DIR" >&2
    exit 1
fi

cd "$GO_DIR"
echo "Building Go commands into $GO_DIR/bin ..."
GOBIN="$GO_DIR/bin" go install ./cmd/...
echo "Done."


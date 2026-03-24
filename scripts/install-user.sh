#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.local/bin"
TARGET_PATH="${TARGET_DIR}/parrot-undercover"

mkdir -p "$TARGET_DIR"
ln -sfn "$ROOT_DIR/bin/parrot-undercover" "$TARGET_PATH"

printf 'Installed %s -> %s\n' "$TARGET_PATH" "$ROOT_DIR/bin/parrot-undercover"

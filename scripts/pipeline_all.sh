#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
  rebuild)
    python cli/mie.py rebuild-everything
    ;;
  update)
    python cli/mie.py update-everything
    ;;
  *)
    echo "Usage: $0 {rebuild|update}" >&2
    exit 1
    ;;
esac


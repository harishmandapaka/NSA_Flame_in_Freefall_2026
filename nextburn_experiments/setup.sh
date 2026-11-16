#!/bin/sh
# NextBurn setup for macOS and Linux: finds Python 3.9 or later and runs setup_nextburn.py.
# Usage: sh setup.sh [--serve] [--pull] [--full] [--no-run] [--no-venv] [--no-open]
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    exec "$py" setup_nextburn.py "$@"
  fi
done
echo "NextBurn needs Python 3.9 or later. Install it from https://www.python.org/downloads/ and run this again." >&2
exit 1

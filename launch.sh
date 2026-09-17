#!/usr/bin/env bash
# HyperBox Launcher Script
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Launch Application
exec /usr/bin/python3 "$DIR/main.py" "$@"

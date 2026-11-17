#!/bin/bash
# Double-click to start Norad. The browser opens by itself.
REPO="__REPO__"
[ -d "$REPO" ] || REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" && exec .venv/bin/norad

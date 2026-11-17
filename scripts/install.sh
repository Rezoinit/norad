#!/bin/bash
# One-time setup on a Mac. Installs what is missing (Homebrew, Python, LabRecorder,
# PsychoPy), then the app, and puts "Start Norad" and "Norad Results" on the Desktop.
set -e
cd "$(dirname "$0")/.."
REPO="$(pwd)"
step() { echo; echo "==> $1"; }

step "Homebrew"
if ! command -v brew >/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done

step "Python 3.11+"
PY=""
for p in python3.13 python3.12 python3.11 python3; do
  if command -v "$p" >/dev/null && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then PY="$p"; break; fi
done
if [ -z "$PY" ]; then brew install python@3.12; PY="$(brew --prefix)/bin/python3.12"; fi

step "LabRecorder (writes the XDF file)"
brew list labrecorder >/dev/null 2>&1 || brew install labstreaminglayer/tap/lsl qt labstreaminglayer/tap/labrecorder

step "PsychoPy (runs the oddball task)"
[ -d /Applications/PsychoPy.app ] || brew install --cask psychopy

step "Norad app"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .
xattr -dr com.apple.quarantine "$REPO" 2>/dev/null || true  # downloaded files: no "unidentified developer" prompts

step "Desktop shortcuts"
mkdir -p Results
sed "s#__REPO__#$REPO#" "scripts/Start Norad.command" > "$HOME/Desktop/Start Norad.command"
chmod +x "$HOME/Desktop/Start Norad.command"
ln -sfn "$REPO/Results" "$HOME/Desktop/Norad Results"

echo
echo "Done. Double-click 'Start Norad' on your Desktop. Recordings are in 'Norad Results'."
echo "Keep this folder where it is: the Desktop shortcut points to it."

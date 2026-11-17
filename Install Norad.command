#!/bin/bash
# Double-click once to install Norad (first time: right-click > Open).
cd "$(dirname "$0")" && bash scripts/install.sh
echo; read -n 1 -s -r -p "Press any key to close this window."

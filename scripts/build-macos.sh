#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
    echo "This script must run on macOS." >&2
    exit 1
fi

cd "$(dirname "$0")/.."
arch="$(python3 -c 'import platform; print(platform.machine())')"
app="CS2-Sensitivity-Generator"

python3 -m PyInstaller --clean --noconfirm --windowed --onedir \
    --name "$app" --target-architecture "$arch" \
    --osx-bundle-identifier io.github.kuangjiuwang.cs2-sensitivity-generator \
    --specpath build --paths src --hidden-import GameController._metadata src/main.py

archive="dist/$app-macOS-$arch.zip"
rm -f "$archive"
ditto -c -k --sequesterRsrc --keepParent "dist/$app.app" "$archive"
echo "Created $archive"

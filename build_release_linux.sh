#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE_VERSION="2.1.00"
APP_NAME="Ignitron Preset Tools v$RELEASE_VERSION"
ENTRY="$ROOT/ignitron_preset_tools_v2.1.py"
BUILD_ROOT="$ROOT/build"
DIST_ROOT="$ROOT/release"
MACHINE="$(uname -m)"
case "$MACHINE" in
  x86_64) ARCH="x64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) ARCH="$MACHINE" ;;
esac
PYINSTALLER_APP="$DIST_ROOT/ignitron-preset-tools"
DIST_PACKAGE="$DIST_ROOT/$APP_NAME Linux-$ARCH"
ARCHIVE_PATH="$DIST_ROOT/$APP_NAME Linux-$ARCH.tar.gz"
FIRMWARE_SOURCE="$ROOT/Ignitron"
FIRMWARE_RELEASE="$DIST_PACKAGE/ignitron firmware"
LEGACY_FIRMWARE_SOURCE="$ROOT/Ignitron 1.9.0"
LEGACY_FIRMWARE_RELEASE="$DIST_PACKAGE/Ignitron 1.9.0"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This script must be run on Linux to build a native Linux package."
  exit 1
fi
if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY"
  exit 1
fi

mkdir -p "$BUILD_ROOT" "$DIST_ROOT"
VENV_ROOT="$BUILD_ROOT/venv-linux-$ARCH"
[[ -x "$VENV_ROOT/bin/python" ]] || python3 -m venv "$VENV_ROOT"
PYTHON="$VENV_ROOT/bin/python"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$ROOT/requirements-build.txt"

DATA_ARGS=()
[[ -d "$ROOT/reference" ]] && DATA_ARGS+=(--add-data "$ROOT/reference:reference")
[[ -f "$ROOT/IPT.ico" ]] && DATA_ARGS+=(--add-data "$ROOT/IPT.ico:.")
[[ -f "$ROOT/Ignitron preset tools logo ASCII 120x60.txt" ]] && DATA_ARGS+=(--add-data "$ROOT/Ignitron preset tools logo ASCII 120x60.txt:.")
for helper in preset_puller.py preset_chart.py preset_converter.py; do
  [[ -f "$ROOT/$helper" ]] && DATA_ARGS+=(--add-data "$ROOT/$helper:.")
done

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "ignitron-preset-tools" \
  --distpath "$DIST_ROOT" \
  --workpath "$BUILD_ROOT/pyinstaller-linux-$ARCH" \
  --specpath "$BUILD_ROOT" \
  "${DATA_ARGS[@]}" \
  "$ENTRY"

rm -rf "$DIST_PACKAGE"
mkdir -p "$DIST_PACKAGE/app"
cp -R "$PYINSTALLER_APP/." "$DIST_PACKAGE/app/"
cp "$ROOT/install_linux.sh" "$ROOT/uninstall_linux.sh" "$DIST_PACKAGE/"
chmod +x "$DIST_PACKAGE/install_linux.sh" "$DIST_PACKAGE/uninstall_linux.sh" "$DIST_PACKAGE/app/ignitron-preset-tools"

if [[ -f "$ROOT/IPT.ico" ]]; then
  ROOT="$ROOT" DIST_PACKAGE="$DIST_PACKAGE" "$PYTHON" - <<'PY'
import os
from pathlib import Path
from PIL import Image

source = Image.open(Path(os.environ["ROOT"]) / "IPT.ico").convert("RGBA")
source.resize((256, 256), Image.Resampling.LANCZOS).save(Path(os.environ["DIST_PACKAGE"]) / "ipt.png")
PY
fi
for document in README.md FIRMWARE.md RELEASE_NOTES.md GITHUB_RELEASE.md LICENSE; do
  [[ -f "$ROOT/$document" ]] && cp "$ROOT/$document" "$DIST_PACKAGE/$document"
done
if [[ -d "$FIRMWARE_SOURCE" ]]; then
  "$PYTHON" "$ROOT/release_tools.py" stage-firmware "$FIRMWARE_SOURCE" "$FIRMWARE_RELEASE"
fi
if [[ -d "$LEGACY_FIRMWARE_SOURCE" ]]; then
  "$PYTHON" "$ROOT/release_tools.py" stage-firmware "$LEGACY_FIRMWARE_SOURCE" "$LEGACY_FIRMWARE_RELEASE"
fi
"$PYTHON" "$ROOT/release_tools.py" verify "$DIST_PACKAGE"

rm -f "$ARCHIVE_PATH"
tar -C "$DIST_ROOT" -czf "$ARCHIVE_PATH" "$(basename "$DIST_PACKAGE")"

echo "Built $APP_NAME for Linux $ARCH"
echo "Package: $DIST_PACKAGE"
echo "Archive: $ARCHIVE_PATH"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RELEASE_VERSION="2.1.00"
APP_NAME="Ignitron Preset Tools v$RELEASE_VERSION"
ENTRY="$ROOT/ignitron_preset_tools_v2.1.py"
BUILD_ROOT="$ROOT/build"
DIST_ROOT="$ROOT/release"
DIST_APP="$DIST_ROOT/$APP_NAME.app"
MACHINE="$(uname -m)"
case "$MACHINE" in
  arm64) ARCH="arm64" ;;
  x86_64) ARCH="x64" ;;
  *) ARCH="$MACHINE" ;;
esac
DIST_PACKAGE="$DIST_ROOT/$APP_NAME macOS-$ARCH"
ZIP_PATH="$DIST_ROOT/$APP_NAME macOS-$ARCH.zip"
FIRMWARE_SOURCE="$ROOT/Ignitron"
FIRMWARE_RELEASE="$DIST_PACKAGE/ignitron firmware"
LEGACY_FIRMWARE_SOURCE="$ROOT/Ignitron 1.9.0"
LEGACY_FIRMWARE_RELEASE="$DIST_PACKAGE/Ignitron 1.9.0"
GENERATED_ICON="$BUILD_ROOT/IPT.icns"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must be run on macOS to build a real .app bundle."
  exit 1
fi
if [[ ! -f "$ENTRY" ]]; then
  echo "Missing entry point: $ENTRY"
  exit 1
fi

mkdir -p "$BUILD_ROOT" "$DIST_ROOT"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-13.0}"
VENV_ROOT="$BUILD_ROOT/venv-macos-$ARCH"
[[ -x "$VENV_ROOT/bin/python" ]] || python3 -m venv "$VENV_ROOT"
PYTHON="$VENV_ROOT/bin/python"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$ROOT/requirements-build.txt"

ICON_ARGS=()
if [[ -f "$ROOT/IPT.icns" ]]; then
  ICON_ARGS=(--icon "$ROOT/IPT.icns")
elif [[ -f "$ROOT/IPT.ico" ]]; then
  ICONSET="$BUILD_ROOT/IPT.iconset"
  rm -rf "$ICONSET" "$GENERATED_ICON"
  mkdir -p "$ICONSET"
  ROOT="$ROOT" ICONSET="$ICONSET" "$PYTHON" - <<'PY'
import os
from pathlib import Path
from PIL import Image

source = Image.open(Path(os.environ["ROOT"]) / "IPT.ico").convert("RGBA")
iconset = Path(os.environ["ICONSET"])
for size in (16, 32, 128, 256, 512):
    source.resize((size, size), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
    double = size * 2
    source.resize((double, double), Image.Resampling.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
PY
  iconutil -c icns "$ICONSET" -o "$GENERATED_ICON"
  ICON_ARGS=(--icon "$GENERATED_ICON")
fi

DATA_ARGS=()
[[ -d "$ROOT/reference" ]] && DATA_ARGS+=(--add-data "$ROOT/reference:reference")
[[ -f "$ROOT/IPT.ico" ]] && DATA_ARGS+=(--add-data "$ROOT/IPT.ico:.")
[[ -f "$ROOT/Ignitron preset tools logo ASCII 120x60.txt" ]] && DATA_ARGS+=(--add-data "$ROOT/Ignitron preset tools logo ASCII 120x60.txt:.")
for helper in preset_puller.py preset_chart.py preset_converter.py; do
  [[ -f "$ROOT/$helper" ]] && DATA_ARGS+=(--add-data "$ROOT/$helper:.")
done

SIGN_ARGS=()
if [[ -n "${MACOS_CODESIGN_IDENTITY:-}" ]]; then
  SIGN_ARGS=(--codesign-identity "$MACOS_CODESIGN_IDENTITY")
fi

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "com.mpkottawa.ignitron-preset-tools" \
  --distpath "$DIST_ROOT" \
  --workpath "$BUILD_ROOT/pyinstaller-macos-$ARCH" \
  --specpath "$BUILD_ROOT" \
  "${ICON_ARGS[@]}" \
  ${SIGN_ARGS[@]+"${SIGN_ARGS[@]}"} \
  "${DATA_ARGS[@]}" \
  "$ENTRY"

rm -rf "$DIST_PACKAGE"
mkdir -p "$DIST_PACKAGE"
cp -R "$DIST_APP" "$DIST_PACKAGE/"
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

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$DIST_PACKAGE" "$ZIP_PATH"

echo "Built $APP_NAME for macOS $ARCH"
echo "App:     $DIST_APP"
echo "Package: $DIST_PACKAGE"
echo "Zip:     $ZIP_PATH"

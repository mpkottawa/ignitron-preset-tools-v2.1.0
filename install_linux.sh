#!/usr/bin/env sh
set -eu

PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_SOURCE="$PACKAGE_DIR/app"
APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/ignitron-preset-tools"
APPLICATIONS_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
BIN_HOME="${HOME}/.local/bin"

if [ ! -x "$APP_SOURCE/ignitron-preset-tools" ]; then
    printf '%s\n' "The packaged application was not found at $APP_SOURCE" >&2
    exit 1
fi

mkdir -p "$APP_HOME" "$APPLICATIONS_HOME" "$ICON_HOME" "$BIN_HOME"
rm -rf "$APP_HOME/app" "$APP_HOME/ignitron firmware" "$APP_HOME/Ignitron 1.9.0"
cp -R "$APP_SOURCE" "$APP_HOME/app"
if [ -d "$PACKAGE_DIR/ignitron firmware" ]; then
    cp -R "$PACKAGE_DIR/ignitron firmware" "$APP_HOME/ignitron firmware"
fi
if [ -d "$PACKAGE_DIR/Ignitron 1.9.0" ]; then
    cp -R "$PACKAGE_DIR/Ignitron 1.9.0" "$APP_HOME/Ignitron 1.9.0"
fi
if [ -f "$PACKAGE_DIR/ipt.png" ]; then
    cp "$PACKAGE_DIR/ipt.png" "$ICON_HOME/ignitron-preset-tools.png"
fi

cat > "$BIN_HOME/ignitron-preset-tools" <<EOF
#!/usr/bin/env sh
exec "$APP_HOME/app/ignitron-preset-tools" "\$@"
EOF
chmod +x "$BIN_HOME/ignitron-preset-tools"

cat > "$APPLICATIONS_HOME/ignitron-preset-tools.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Ignitron Preset Tools 2.1.00
Comment=Build presets and control an Ignitron pedal
Exec=$BIN_HOME/ignitron-preset-tools
Icon=ignitron-preset-tools
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupNotify=true
EOF
chmod +x "$APPLICATIONS_HOME/ignitron-preset-tools.desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPLICATIONS_HOME" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" || true

printf '%s\n' "Installed Ignitron Preset Tools for this user."
printf '%s\n' "Launch it from your app menu or run: $BIN_HOME/ignitron-preset-tools"

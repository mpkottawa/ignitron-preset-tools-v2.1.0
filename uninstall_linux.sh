#!/usr/bin/env sh
set -eu

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
case "${1:-}" in
    "") rm -rf "$DATA_HOME/ignitron-preset-tools/app" "$DATA_HOME/ignitron-preset-tools/firmware templates" ;;
    --purge) rm -rf "$DATA_HOME/ignitron-preset-tools" ;;
    *) printf '%s\n' "Usage: $0 [--purge]" "--purge also deletes firmware projects, presets, captures and backups." >&2; exit 2 ;;
esac
rm -f "$DATA_HOME/applications/ignitron-preset-tools.desktop"
rm -f "$DATA_HOME/icons/hicolor/256x256/apps/ignitron-preset-tools.png"
rm -f "$HOME/.local/bin/ignitron-preset-tools"
printf '%s\n' "Removed the Ignitron Preset Tools application."
if [ "${1:-}" != "--purge" ]; then
    printf '%s\n' "Firmware projects, presets, captures and backups were kept in $DATA_HOME/ignitron-preset-tools."
fi
printf '%s\n' "Your settings in ${XDG_CONFIG_HOME:-$HOME/.config}/ignitron-preset-tools were kept."

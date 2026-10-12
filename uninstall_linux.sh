#!/usr/bin/env sh
set -eu

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DATA_HOME/ignitron-preset-tools"
rm -f "$DATA_HOME/applications/ignitron-preset-tools.desktop"
rm -f "$DATA_HOME/icons/hicolor/256x256/apps/ignitron-preset-tools.png"
rm -f "$HOME/.local/bin/ignitron-preset-tools"
printf '%s\n' "Removed the Ignitron Preset Tools application."
printf '%s\n' "Your settings in ${XDG_CONFIG_HOME:-$HOME/.config}/ignitron-preset-tools were kept."

#!/usr/bin/env bash
# The desktop launcher opens this in the user's normal terminal session.
set -u
PACKAGE_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 1
bash "$PACKAGE_DIR/setup_linux.sh"
status=$?
if [[ "$status" == 0 ]]; then
  APP="${XDG_DATA_HOME:-$HOME/.local/share}/ignitron-preset-tools/app/ignitron-preset-tools"
  if [[ -x "$APP" && ( -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ) ]]; then
    LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ignitron-preset-tools/setup"
    printf '\n%s\n' 'Opening Ignitron Preset Tools. You can close this setup window.'
    nohup "$APP" > "$LOG_DIR/app-launch.log" 2>&1 < /dev/null &
  fi
else
  printf '\n%s\n' 'Installation did not finish. Keep the error above for troubleshooting.'
fi
# Keep success and errors visible instead of closing the terminal immediately.
if [[ -t 0 ]]; then
  read -r -p 'Press Enter to close this setup window. ' answer || true
fi
exit "$status"

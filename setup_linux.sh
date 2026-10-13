#!/usr/bin/env bash
# Bundled or online setup for the published IPT release. Run as your normal user.
set -euo pipefail

RELEASE_VERSION="2.1.02"
RELEASE_URL="https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0/releases/download/v$RELEASE_VERSION"
CHECK_ONLY=false
case "${1:-}" in
  --check) CHECK_ONLY=true ;;
  --help|-h)
    printf '%s\n' "Usage: bash setup_linux.sh [--check]" \
      "Installs IPT $RELEASE_VERSION, native VLC, PlatformIO and USB rules." \
      "Downloads and checks the firmware tools without uploading to a pedal." \
      "Supports Fedora (dnf) and Ubuntu/Debian (apt), x64 and ARM64." \
      "--check shows the plan without downloads or changes. Run without sudo."
    exit 0 ;;
  "") ;;
  *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { printf '%s\n' 'Too many arguments.' >&2; exit 2; }
fail() { printf '\n%s\n' "$*" >&2; exit 1; }
[[ "$(uname -s)" == Linux ]] || fail 'This installer requires Linux.'
[[ "$(id -u)" != 0 ]] || fail 'Run this installer as your normal user, without sudo. It asks for the password when needed.'
case "$(uname -m)" in
  x86_64) ARCH=x64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) fail 'This release supports Linux x64 and ARM64 only.' ;;
esac
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BUNDLED=false
if [[ -e "$SCRIPT_DIR/linux-package.txt" || -d "$SCRIPT_DIR/app" ]]; then
  [[ -f "$SCRIPT_DIR/linux-package.txt" ]] || fail 'This package is incomplete. Extract the entire updated Linux download, then run Install Ignitron again.'
  [[ "$(cat "$SCRIPT_DIR/linux-package.txt")" == "$RELEASE_VERSION $ARCH" ]] || fail "This package does not match IPT $RELEASE_VERSION for Linux-$ARCH. Download the matching Linux package."
  [[ -x "$SCRIPT_DIR/app/ignitron-preset-tools" && -f "$SCRIPT_DIR/install_linux.sh" && -f "$SCRIPT_DIR/ignitron firmware/platformio.ini" && -f "$SCRIPT_DIR/linux-bundle.sha256" ]] || fail 'This package is incomplete. Extract the entire Linux download before installing.'
  BUNDLED=true
fi
[[ ! -e /run/ostree-booted ]] || fail 'Atomic/immutable Linux editions need a separate setup method. This installer supports Fedora with dnf and Ubuntu/Debian with apt.'
[[ -r /etc/os-release ]] || fail 'Cannot identify this Linux distribution.'
# This is the operating system-owned identification file, never a download.
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in
  *fedora*) MANAGER=dnf; PACKAGES=(curl ca-certificates python3 python3-pip git vlc systemd-udev) ;;
  *ubuntu*|*debian*) MANAGER=apt-get; PACKAGES=(curl ca-certificates python3 python3-venv git vlc udev) ;;
  *) fail 'Automatic setup supports Fedora and Ubuntu/Debian. Use the manual Linux guide for this distribution.' ;;
esac
command -v "$MANAGER" >/dev/null || fail "Required package manager is missing: $MANAGER"
case "${XDG_CURRENT_DESKTOP:-}:${DESKTOP_SESSION:-}" in
  *KDE*|*kde*|*plasma*) PACKAGES+=(kdialog kio-fuse) ;;
esac

MISSING=()
for package in "${PACKAGES[@]}"; do
  if [[ "$MANAGER" == dnf ]]; then
    rpm -q "$package" >/dev/null 2>&1 || MISSING+=("$package")
  else
    [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" == 'install ok installed' ]] || MISSING+=("$package")
  fi
done
printf 'Ignitron Preset Tools %s - complete Linux setup\n' "$RELEASE_VERSION"
printf 'System: %s / %s\n' "${PRETTY_NAME:-$ID}" "$ARCH"
printf 'Missing system packages: %s\n' "${MISSING[*]:-none}"
if "$BUNDLED"; then
  printf '%s\n' 'Application source: this extracted Linux package (no app download needed).'
else
  printf '%s\n' 'Application source: verified download from the GitHub release.'
fi
printf '%s\n' 'Setup installs IPT, checks PlatformIO/VLC, installs USB rules, and builds firmware and filesystem.' \
  'Keep the pedal unplugged. Choose its hardware settings in IPT after setup.' \
  'Existing projects, presets and settings are preserved. Internet access is required.'
if "$CHECK_ONLY"; then
  printf '%s\n' 'Check complete. No files, packages or settings were changed.'
  exit 0
fi
command -v sudo >/dev/null || fail 'sudo is required to install system packages and USB permissions. Ask the computer administrator to enable it.'
command -v flock >/dev/null || fail 'The standard util-linux package (flock) is required for setup.'
[[ "${PLATFORMIO_CORE_DIR:-$HOME/.platformio}" == "$HOME/.platformio" ]] || fail 'Unset PLATFORMIO_CORE_DIR before setup so PlatformIO uses the normal desktop-app location.'
APP_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/ignitron-preset-tools"
for process in /proc/[0-9]*/exe; do
  executable=$(readlink "$process" 2>/dev/null) || continue
  [[ "$executable" != "$APP_HOME/app/ignitron-preset-tools" ]] || fail 'Close Ignitron Preset Tools before running setup.'
done

LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/ignitron-preset-tools/setup"
mkdir -p "$LOG_DIR"
exec 9>"$LOG_DIR/setup.lock"
flock -n 9 || fail 'Another IPT setup is running. Wait for it to finish.'
LOG=$(mktemp "$LOG_DIR/setup-$RELEASE_VERSION-XXXXXXXX.log")
exec > >(tee -a "$LOG") 2>&1
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ipt-setup.XXXXXXXX")
PHASE='starting setup'
cleanup() {
  status=$?
  trap - EXIT
  rm -rf -- "$WORK"
  if [[ "$status" != 0 ]]; then
    printf '\nSetup stopped while %s. It is NOT complete.\n' "$PHASE" >&2
    printf 'Correct the error above, then run this installer again. Log: %s\n' "$LOG" >&2
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
step() { PHASE=$1; printf '\n[%s] %s\n' "$2" "$1"; }
download() { curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 --retry 3 --connect-timeout 20 --max-time 900 --output "$2" "$1"; }

step 'checking the IPT package' '1/7'
if "$BUNDLED"; then
  # Verify before asking for privilege or modifying installed files.
  (cd "$SCRIPT_DIR" && sha256sum --check --strict --quiet linux-bundle.sha256)
  PACKAGE="$SCRIPT_DIR"
fi

step 'installing system prerequisites' '2/7'
sudo -v
if [[ ${#MISSING[@]} -gt 0 ]]; then
  if [[ "$MANAGER" == dnf ]]; then
    sudo dnf install -y "${MISSING[@]}"
  else
    sudo apt-get update
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${MISSING[@]}"
  fi
else
  printf '%s\n' 'Required system packages are already installed.'
fi

if ! "$BUNDLED"; then
PHASE='downloading and verifying the IPT release'
printf '\n%s\n' 'Downloading and verifying the IPT application...'
ARCHIVE="Ignitron.Preset.Tools.v$RELEASE_VERSION.Linux-$ARCH.tar.gz"
download "$RELEASE_URL/$ARCHIVE" "$WORK/$ARCHIVE"
download "$RELEASE_URL/SHA256SUMS.txt" "$WORK/SHA256SUMS.txt"
EXPECTED=$(awk -v name="$ARCHIVE" '$2 == name {print $1}' "$WORK/SHA256SUMS.txt")
[[ "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]] || fail 'The release checksum is missing or ambiguous. No downloaded installer was run.'
(cd "$WORK" && printf '%s  %s\n' "$EXPECTED" "$ARCHIVE" | sha256sum -c -)
tar --no-same-owner -xzf "$WORK/$ARCHIVE" -C "$WORK"
PACKAGE="$WORK/Ignitron Preset Tools v$RELEASE_VERSION Linux-$ARCH"
[[ -f "$PACKAGE/install_linux.sh" && -x "$PACKAGE/app/ignitron-preset-tools" ]] || fail 'The verified archive does not contain the expected IPT application.'
fi

step 'installing USB permissions' '3/7'
RULES="$WORK/99-platformio-udev.rules"
download 'https://raw.githubusercontent.com/platformio/platformio-core/develop/platformio/assets/system/99-platformio-udev.rules' "$RULES"
grep -q 'ATTRS{idVendor}=="10c4"' "$RULES" || fail 'The downloaded PlatformIO USB rules do not include the expected CP210x adapter. The existing rule was kept.'
RULE_TARGET=/etc/udev/rules.d/99-platformio-udev.rules
if [[ -f "$RULE_TARGET" ]] && ! cmp -s "$RULES" "$RULE_TARGET"; then
  cp "$RULE_TARGET" "$LOG.previous-udev.rules"
fi
sudo install -m 644 "$RULES" "$RULE_TARGET"
sudo udevadm control --reload-rules
sudo udevadm trigger

step 'installing or locating PlatformIO Core' '4/7'
# Use its standard per-user environment so the desktop app finds it without
# relying on a terminal-only PATH or writing over the user's IPT settings.
PIO="$HOME/.platformio/penv/bin/platformio"
if [[ -x "$PIO" ]] && "$PIO" --version; then
  printf '%s\n' 'Using the existing PlatformIO Core environment.'
else
  download 'https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py' "$WORK/get-platformio.py"
  # Official installer: https://docs.platformio.org/en/latest/core/installation/methods/installer-script.html
  python3 "$WORK/get-platformio.py"
  "$PIO" --version
fi

step 'installing the application and menu shortcut' '5/7'
sh "$PACKAGE/install_linux.sh"
APP="$APP_HOME/app/ignitron-preset-tools"

step 'checking VLC playback' '6/7'
"$APP" --vlc-self-test
"$APP" --vlc-audio-self-test

step 'downloading firmware tools and checking both builds' '7/7'
# Build a temporary copy, never the extracted download or a user's project.
# PlatformIO's shared downloads remain available for the subsequent IPT build.
# Explicit run/buildfs targets never open, erase or upload to the pedal.
cp -R "$PACKAGE/ignitron firmware" "$WORK/firmware-check"
"$PIO" run --project-dir "$WORK/firmware-check" --environment esp32dev
"$PIO" run --project-dir "$WORK/firmware-check" --environment esp32dev --target buildfs

printf '\n%s\n' 'SETUP COMPLETE' \
  'IPT, VLC, PlatformIO and USB permissions are ready. Both build checks passed.' \
  'Open Ignitron Preset Tools from the application menu.' \
  'Review OLED/battery/hardware settings before connecting and flashing your pedal.' \
  'If the pedal was already connected, unplug and reconnect it to apply USB permissions.'
printf 'Installation log: %s\n' "$LOG"

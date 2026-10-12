# Ignitron Preset Tools v2.1.00

IPT v2.1.00 is the desktop control center for building Ignitron preset banks, installing IPT firmware support, flashing firmware/filesystem data, controlling presets over USB, backing up a pedal, capturing presets from the Spark app, and playing backing tracks.

## Native downloads

Choose the archive matching the operating system and CPU:

- `Ignitron Preset Tools v2.1.00 Windows-x64.zip`
- `Ignitron Preset Tools v2.1.00 macOS-arm64.zip` for Apple Silicon
- `Ignitron Preset Tools v2.1.00 macOS-x64.zip` for Intel Macs
- `Ignitron Preset Tools v2.1.00 Linux-x64.tar.gz`
- `Ignitron Preset Tools v2.1.00 Linux-arm64.tar.gz`

Windows users extract the ZIP and run the EXE. Mac users extract the ZIP and move the app to Applications. Linux users should follow the Fedora or Ubuntu/Debian prerequisites in `README.md`, extract the archive from `~/Downloads`, and run `./install_linux.sh` to install for the current user. The IPT installer does not install PlatformIO Core or VLC.

The release workflow builds each application natively. It does not relabel a Windows executable for another operating system.

## Included firmware

- `ignitron firmware` is the ready-to-build IPT v2.1.00 project with the current feature set and prepared preset library.
- `Ignitron 1.9.0` is included separately as the earlier fallback firmware.

The current project defaults to the SH1106 1.3-inch OLED. Review OLED, battery, and GPIO settings before flashing hardware that differs from that profile. See `FIRMWARE.md` in the download for the short setup and recovery guide.

## Highlights

- Preset Bank Builder with generated preset list, UUID list, and PDF.
- One-button firmware plus filesystem build/flash workflow.
- Required IPT firmware support is offered only when missing.
- Hardware GPIO, OLED, battery, AMP blocklist, LED, and timing configuration.
- Pedal Remote with live preset switching, hardware slots, Spark 2 looper, and tuner display.
- Spark Capture with one-shot software AMP mode and automatic return to APP mode.
- Full-pedal and active-bank JSON backup.
- Backing-track library with VLC playback, search, favorites, and seeking.
- ESP32/Ignitron pin and hardware reference.
- Per-user settings in each operating system's standard configuration directory.

## Requirements

- PlatformIO Core for firmware or filesystem builds/uploads.
- VLC for backing-track playback.
- An operating-system serial driver for the pedal's USB-to-UART adapter when one is not already included.
- Linux serial-device permission through PlatformIO udev rules or the distribution's serial group.

## Firmware setup

1. Open IPT and select the Ignitron PlatformIO project.
2. If the Dashboard reports missing support, open **Firmware > IPT 2.1 Setup** and apply it.
3. Choose the PlatformIO environment and detected serial port.
4. Click **Build + Flash FW + FS**.

The default upload speed is `460800`; app serial controls use `115200`.

## Release hygiene

Every native builder uses the same release staging tool. Generated output, local settings, recent paths, window geometry, user home paths, network shares, backups, captures, logs, and other machine-specific data are excluded and the finished package is checked before archiving. The prepared release preset libraries are retained.

See `README.md` for full Windows, macOS, and Linux setup instructions.

Linux packages use the operating system's matched libVLC core and plugins rather than bundling Ubuntu VLC libraries into every distribution package. If VLC initialization fails, IPT reports the native Fedora and Ubuntu/Debian install commands plus the technical failure detail.

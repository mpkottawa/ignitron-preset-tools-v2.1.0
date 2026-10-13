# Ignitron Preset Tools v2.1.02

## Dedicated preset LED stability fix - 2026-10-12

- Fixed visible flicker on the separate FX/letter LEDs when `DEDICATED_PRESET_LEDS` is enabled. Preset mode now updates only the four dedicated preset outputs before applying FX states, instead of clearing every LED on every loop.
- Preserved the existing LED behavior for standard pedals without dedicated preset LEDs.
- Added a regression test that prevents the dedicated preset path from calling `allLedOff()` and pulsing the FX outputs again.
- Updated the application, bundled current firmware, native packages, installers, documentation, and release workflow to v2.1.02.
- Carried forward the bundled Linux installer and all-in-one setup introduced after the initial v2.1.01 publication.

The correction is narrowly scoped and does not require different GPIO assignments. It has automated coverage but still requires physical confirmation by a user with the optional dedicated preset LED hardware.

## Bundled Linux installer refresh - 2026-10-12

- Refreshed both Linux archives with an executable **Install Ignitron** desktop launcher, all-in-one setup and the updated PDF/START-HERE guide.
- Uses and verifies the bundled application instead of downloading the archive again; detects wrong architecture or damaged/incomplete bundles before system installation.
- Opens a terminal for the password and progress, keeps errors visible, and opens IPT after successful setup. Desktop trust/executable confirmation may be required.
- Builds in a temporary firmware copy so the extracted package remains reusable. The standalone online installer is still available.
- Application and firmware payloads, Windows/macOS packages and the v2.1.01 tag are unchanged. Linux archive checksums have changed; use the refreshed SHA256SUMS.txt.

## All-in-one Linux setup - 2026-10-12

- Added `Install-IPT-Linux.sh` as a separate online installer for the existing v2.1.01 release, with source in `setup_linux.sh`.
- Detects Fedora/Ubuntu/Debian and x64/ARM64; installs missing native VLC/Python requirements, PlatformIO Core, USB permissions, IPT, and KDE folder/NAS helpers when applicable.
- Verifies release checksums, checks both VLC backends, and downloads firmware tools while testing firmware and filesystem builds without uploading to a pedal.
- Preserves existing data, stops with an actionable log on failure, and supports a read-only `--check` preview.
- Revised the Linux PDF with a one-file setup route. This initially shipped as a separate download; the later packaging refresh above includes it in both Linux archives.

## Fixes in v2.1.01 - 2026-10-12

This maintenance release follows v2.1.00 with the Linux testing fixes. The application, native archives and bundled current firmware are labelled **2.1.01**. The original v2.1.00 release remains available. Download the archive for your platform and its matching SHA256SUMS.txt.

- Fixed Linux VLC discovery and a PipeWire crash when changing volume before playback. Added a real-audio-backend self-test.
- Added KDE Places folder selection, remembered music locations, and SMB access through the desktop credential/mount services.
- Fixed CP2102 serial control-line resets and kept a verified connection open for Pedal Remote. Orange preset highlighting now means selected only.
- Moved Capture connection work off the GUI thread and wait for the previous USB task to finish. Firmware tasks and app serial tools cannot share the port concurrently.
- Capture now decodes nested and inline preset JSON and preserves different presets with the same name. Routine keepalive messages no longer flood the log.
- Backups reuse the verified port, report interrupted or incomplete transfers, and use unique folders. **Pull listed presets** describes all filenames in PresetList.txt, rather than implying just the active bank.
- Linux upgrades and normal uninstalls preserve working projects, presets, captures and backups. Bundled firmware templates update separately. Settings writes are atomic.
- Both firmware and filesystem must build before an optional erase. Builder exports back up replaced preset JSON and reject ambiguous selected filenames.
- Added the revised **Linux-Install-Guide.pdf**, also available as a separate release download. Published filenames and checksum entries now match.

Close IPT before installing. Use the v2.1.01 installer. The guide's clean-install checklist remains a separate end-to-end test; native CI packaging does not replace testing each amp or Linux distribution.

## v2.1.00 - initial release

This is the first public IPT 2.1 release. The app window, packaged application, archives, documentation, and bundled current firmware use the v2.1.00 version. The first maintenance update is v2.1.01.

- Added the ready-to-build IPT v2.1.00 firmware project to every native package and the GitHub source release.
- Added a separate sanitized Ignitron 1.9.0 firmware project as a fallback and recovery point.
- Both firmware projects now compile successfully and produce valid LittleFS images in the release audit.

## Native Windows, macOS, and Linux releases

- Added native package builders for Windows x64, macOS Apple Silicon, macOS Intel, Linux x64, and Linux ARM64.
- Added a single GitHub Actions workflow that tests all desktop operating systems and publishes architecture-labelled release files.
- Moved settings and backing-track favorites into each operating system's standard per-user configuration folder, with one-time migration from legacy local files.
- Added safe external-process environments for PlatformIO and desktop file-manager launches from frozen macOS/Linux applications.
- Added automatic PlatformIO discovery through `PATH`, normal per-user virtual environments, Homebrew, and common Unix install locations.
- Added native VLC discovery and OS-specific installation guidance.
- Added macOS icon generation, bundle identity, optional Developer ID signing, and separate Intel/Apple Silicon archives.
- Added a Linux user installer, application-menu entry, icon, uninstaller, and x64/ARM64 packages.
- Added POSIX and macOS source launchers.
- Added shared release staging and privacy verification; preset libraries are retained while personal settings, local paths, network shares, and generated runtime files are excluded.
- Added BSD 3-Clause release licensing and portable regression tests with no fixed local baseline path.
- Removed the retired Live Library page and its unreachable implementation from the release source.
- Added a persistent top-right Pedal USB selector shared by every page, with disconnected, USB-ready, and active-tool connection states.
- IPT now watches for newly connected USB serial devices and asks the user to confirm the pedal port. A confirmed or manually selected port is applied throughout the app and saved as `upload_port` in the selected/default PlatformIO environment.
- Firmware flashing now always writes the displayed firmware version plus every selected settings group, reads the saved configuration back, and stops before PlatformIO if any selected value was not applied.
- **Build + Flash FW + FS** now saves and verifies every Firmware-tab value before compiling, independent of the manual Save settings button. The lower checkboxes are identified as IPT 2.1 setup selections instead of a partial-save filter.
- Added **Restore stock** to the Hardware tab. It resets and saves all registered factory GPIO/hardware values, including button, LED, display, battery ADC, battery-status, and dedicated-LED settings, then restores hardware-mapping protection.
- AMP blocking now remembers the last successfully connected Spark address for the current boot, so a Spark MINI BLE state transition during the two-button hold no longer produces a false `NO AMP CONNECTED` result.
- AMP blocking now keeps multiple amps blocked at once and identifies each saved entry by detected model name plus Bluetooth address. At the disconnected Ignitron screen, holding Bank Up + Bank Down opens a list where Bank Up/Down selects an amp. Preset 4 now asks `YOU SURE?`; pressing Preset 4 again confirms the unblock, while navigating or leaving the menu cancels it. Holding both bank switches again exits. The existing boot-time Bank Up + Bank Down shortcut still clears every blocked amp.

## Required firmware injector safety

- Wired the AMP blocklist checkbox to its required source-code injection path; it remains compile-time disabled when unchecked.
- Restored Preset 1 as the AMP-mode startup button in the optional blocklist source template.
- Corrected Spark Capture fallback text to identify switch 1 as the manual AMP-mode boot shortcut.
- Backup filenames now end in `.bak`, preventing `src_dir = .` from compiling saved `.cpp` files.
- Required-only injection now preserves the baseline `SparkDataControl::updateBatteryLevel()` implementation verbatim.
- Required-only injection now uses an explicit protocol-file manifest instead of replacing the entire firmware source tree.
- Battery, OLED, GPIO, button/startup, blocklist, and other optional configuration stays unchanged unless selected.
- PUT transfers now validate Base64 strictly and use verified temporary files with rollback-safe replacement.
- Fixed TUNERSTREAM error handling outside APP mode and replaced blocking raw OLED framebuffer dumps with compact semantic mirror records.
- Reconciled the baseline PlatformIO layout by retaining `src_dir = .` and disabling duplicate `lib_extra_dirs = ${workspacedir}` compilation.
- Added optional baseline regression tests configured through `IGNITRON_BASELINE`.

## ESP32 Hardware Reference

- Rebuilt the interactive pinout for the actual 38-pin NodeMCU-style ESP32 used by the Ignitron piggyback PCB.
- Added all 38 physical header positions in antenna-top/Micro-USB-bottom orientation.
- Reconciled the original PCB schematic, battery schematic, optional 3D-case wiring, and active firmware configuration.
- Added exact SW1-SW6, D1-D6, J1, J2, resistor, battery-divider, UART, flash-pin, and boot-strap details.
- Added an ESP32 Pin -> Ignitron Connection -> Circuit/Purpose table beside the interactive board.
- Added a live hardware profile showing the selected OLED driver, I2C pins/speed, battery configuration, and optional preset LEDs.

## Firmware Startup Stability

- Fresh stock firmware now keeps SH1106 as IPT's default when Screen/OLED support is selected instead of inheriting stock SSD1306; configured IPT projects retain their chosen driver.
- Set the SH1106 1.3-inch OLED driver as the default for the bundled and release firmware.
- Restored the SSD1309 display-transfer clock to 400 kHz while retaining a 100 kHz idle/shared-bus clock.
- Moved LED GPIO initialization out of the global constructor and into Arduino `setup()`.
- All six main LEDs are now explicitly configured and cleared before filesystem, BLE, and OLED initialization.
- Restored the firmware version string and normalized it to the public release version `2.1.00`.

## Backing Tracks

- Added a Backing Tracks page with an IPT-native Artist > Album > Track library browser.
- Added VLC-powered playback for MP3, FLAC, WAV, M4A, AAC, OGG, OPUS, WMA, AIFF, APE, MP4, and WebM files.
- Added play/pause, stop, previous/next, seeking, elapsed/total time, and volume controls.
- The progress slider supports click-to-jump and drag-to-scrub forward or backward, with a live time preview.
- Added a Backing Tracks button in Pedal Remote that opens the player in a separate resizable window.
- Pedal Remote now shows a compact backing-track title, time, and progress bar only while audio is actively playing.
- Added persistent track favorites, starred library entries, and an All Tracks/Favorites view switch.
- Backing-track libraries now open as a collapsed artist list instead of expanding every track.
- Added an artist dropdown that shows the selected artist's collapsed albums, plus Reset and Collapse All controls.
- Added full-library keyword search across artist, album, track filename, and complete path.
- The Backing Tracks popup remembers its exact size and screen position, including a second monitor.
- Fixed Windows multi-monitor restoration by saving absolute window bounds and restoring the outer native window handle.
- The selected backing-track folder and volume are remembered between sessions.
- Double-clicking a track starts playback, and playback advances automatically at the end of a track.

## Earlier IPT 2.1 development changes

## Preview Split-Out

- Removed the Hardware Preset Preview page from IPT 2.1.
- Moved the hardware rendering experiment out as a standalone local prototype for loading a base/dry WAV, selecting bank presets through Ignitron, and caching Spark return audio.

## Firmware + Filesystem

- Enlarged the Firmware, Hardware, and IPT 2.1 Setup tabs and added high-contrast active and hover states.
- Moved **Export + select port** from Preset Builder to the Firmware tab and moved **Load library** into the Bank Layout toolbar.
- A successful **Load library** now continues to the Firmware section and selects its first Firmware tab; failed or cancelled loads remain in Preset Builder.
- Reordered the main workflow so Spark Capture is section 04, directly after Pedal Remote, with Backing Tracks moved to section 05.
- After a visible **Apply selected changes** completes, IPT opens Preset Builder to continue the first-time setup flow; automatic pre-flash application remains on Firmware.
- Added composable firmware-mod checkboxes for required IPT 2.1 support, screen/OLED, AMP blocklist, battery, dedicated LEDs, and FX/timing.
- Added an optional Spark 2 dual-battery firmware setting. IPT injects the guarded telemetry/display support without replacing the project’s pedal-voltage calibration; non-Spark 2 amps keep the normal display, edit mode hides the amp indicator, and looper modes hide the complete status group.
- Fixed fresh LI-ION installations so the Spark 2 telemetry request is enabled before compilation; Build + Flash also detects and repairs projects produced by the earlier misplaced-guard injector.
- Spark Capture now requests a one-shot software reboot into AMP mode; the next reboot returns to the regular APP-mode path without rocker-switch hardware.
- Save and firmware-flash workflows now apply the same checked mod selection, and source replacement creates timestamped backups.
- Merged filesystem upload controls into the Firmware section.
- The Firmware page now validates data, builds filesystem images, uploads filesystem data, and can still upload the filesystem after firmware flashing.
- Removed the separate Upload FS entry from the sidebar and dashboard to keep the release surface cleaner.

## Pedal Remote

- Pedal Remote now detects pedal resets and USB loss, ends the serial session automatically, and immediately clears the connected state.
- Moved tuner display into Pedal Remote.
- Removed the separate Tuner entry from the sidebar and dashboard.
- Removed the live display mirror from Pedal Remote.
- Removed the separate Display Mirror entry from the sidebar and dashboard.
- Firmware can still stream raw OLED framebuffer data as `OLED_HEX`, but Pedal Remote now stays focused on preset switching and tuner readout.
- Added Spark hardware preset buttons for HW bank 1 and HW bank 2, four slots each.
- Added a dedicated Pedal Remote hardware indicator showing connected amp type and reported HW bank count.
- Added a one-shot save option that writes the current amp preset to the clicked Spark hardware slot.
- Added a Spark 2 looper panel inside Pedal Remote with live rec/dub, play/stop, undo/redo, retry, delete, exit, status, and bar/beat visualization.
- Looper controls now open from an Enter Looper button or automatically when firmware reports looper mode after holding preset 4. Transport commands also enter looper mode before sending Spark 2 looper actions.

## Spark Capture

- Spark Capture now ends automatically when it detects a pedal reset, APP-mode return, inactive capture heartbeat, or USB loss while still allowing the intentional BLE-to-Serial restart.
- The persistent top-right USB panel now shows **Remote active** or **Capture active**, then returns to **USB ready** or **Disconnected** as soon as a session ends.
- Holding Bank Up to switch AMP-mode Bluetooth between BLE and Serial now carries the active Spark Capture session across that intentional reboot; unplugging, power-cycling, resetting, ending capture, or losing USB still returns to normal APP mode.
- Merged the separate Pedal Puller into the Spark Capture workspace.
- Added **Pull listed presets** and **Pull full library** buttons for saving connected-pedal presets to timestamped backup folders.
- Kept live Spark app capture in the same page, with one shared USB-port selector and safe single-task serial handling.

Release date: 2026-10-12

## Highlights

- Copied forward the v1.1.1 desktop app, helper scripts, data settings, and reference materials.
- Updated the application to v2.1 branding and a v2.1 entry point.
- Added safer Preset Builder exports with automatic backups for generated list/PDF files.
- Reworked duplicate UUID cleanup so duplicate files are moved to a timestamped backup folder instead of deleted.
- Expanded persistent settings so project and preset library folders can both be remembered.
- Added tuner display support, now surfaced inside Pedal Remote as the live control view.
- Added OLED mirror firmware support, then removed the mirror from Pedal Remote for a cleaner control tab.
- Added a Pedal Remote serial tab for clicking the PresetList bank grid and changing the connected amp through Ignitron.
- Added automatic serial handoff: starting a serial tool stops the previous serial tool without asking for confirmation.
- Added firmware-side `SELECTPRESET bank preset`, `SELECTHW hardware-bank preset`, `STOREHW hardware-bank preset`, `LOOPER ...`, `MIRROR ON/OFF`, and `TUNERSTREAM ON/OFF` serial commands in the bundled working firmware folder.
- Added app discovery for an `Ignitron` firmware folder beside the v2.1 tools.
- Added a launcher, README, requirements file, and a release build script.
- Windows release downloads now expose the bundled firmware as a root-level `ignitron firmware` folder beside the EXE instead of burying it in `_internal`.
- Added a GitHub Actions macOS release workflow that builds the `.app` on a macOS runner and attaches `Ignitron Preset Tools v2.1-macOS.zip` to the release page.

## Upgrade Notes

- Existing v1.1.1 generated build/release artifacts were not copied into the v2.1 workspace.
- The app prefers an `Ignitron` firmware folder beside the IPT 2.1 app/source folder when it looks like a PlatformIO project.
- Duplicate cleanup backup folders are created inside the selected preset library as `_ipt_duplicate_backups`.
- Preset Builder export backups are created inside the selected data/output folder as `_ipt_backups`.

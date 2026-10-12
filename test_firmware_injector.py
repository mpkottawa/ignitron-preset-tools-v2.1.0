import hashlib
import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ipt", ROOT / "ignitron_preset_tools_v2.1.py")
IPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IPT)
RELEASE_SPEC = importlib.util.spec_from_file_location("release_tools", ROOT / "release_tools.py")
RELEASE_TOOLS = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(RELEASE_TOOLS)
BASELINE = Path(os.environ["IGNITRON_BASELINE"]) if os.environ.get("IGNITRON_BASELINE") else None
TEMPLATE = ROOT / "stock/Ignitron-main"
if not TEMPLATE.exists():
    TEMPLATE = ROOT / "Ignitron"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RequiredFirmwareInjectionTests(unittest.TestCase):
    def require_baseline(self):
        if BASELINE is None or not BASELINE.exists():
            self.skipTest(
                "optional firmware baseline not configured; set IGNITRON_BASELINE to enable regression tests"
            )

    def test_required_injection_preserves_every_unselected_file(self):
        self.require_baseline()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(BASELINE, output, ignore=shutil.ignore_patterns(".pio", "backups"))
            before = {
                p.relative_to(output).as_posix(): digest(p)
                for p in output.rglob("*") if p.is_file()
            }
            IPT.inject_required_ipt_support(TEMPLATE, output)
            after = {
                p.relative_to(output).as_posix(): digest(p)
                for p in output.rglob("*") if p.is_file()
            }
            allowed = set(IPT.IPT_REQUIRED_FILES) | {"platformio.ini"}
            self.assertEqual(set(before), set(after))
            for name, original_hash in before.items():
                if name not in allowed:
                    self.assertEqual(original_hash, after[name], name)

    def test_required_injection_preserves_configuration_and_build_layout(self):
        self.require_baseline()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(BASELINE, output, ignore=shutil.ignore_patterns(".pio", "backups"))
            protected = ("src/Config_Definitions.h", "src/SparkButtonHandler.cpp")
            before = {name: (output / name).read_bytes() for name in protected}
            IPT.inject_required_ipt_support(TEMPLATE, output)
            for name, content in before.items():
                self.assertEqual(content, (output / name).read_bytes(), name)

            platformio = (output / "platformio.ini").read_text(errors="replace")
            self.assertIn("src_dir = .", platformio)
            self.assertNotRegex(platformio, r"(?m)^\s*lib_extra_dirs\s*=")
            self.assertIn("; lib_extra_dirs = ${workspacedir}", platformio)

            sketch_bytes = (output / "Ignitron.ino").read_bytes()
            self.assertFalse(sketch_bytes.startswith(b"\xef\xbb\xbf"))
            led_header = (output / "src/SparkLEDControl.h").read_text(errors="replace")
            led_source = (output / "src/SparkLEDControl.cpp").read_text(errors="replace")
            self.assertIn("void begin();", led_header)
            self.assertIn("void SparkLEDControl::begin()", led_source)

    def test_required_injection_preserves_battery_function_and_safe_backups(self):
        self.require_baseline()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(BASELINE, output, ignore=shutil.ignore_patterns(".pio", "backups"))
            baseline_source = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            start, end = IPT._cpp_function_span(
                baseline_source, "void SparkDataControl::updateBatteryLevel()")
            expected = baseline_source[start:end]
            backup_root = output / "backups/ipt_firmware"
            IPT.inject_required_ipt_support(TEMPLATE, output, backup_root)
            injected_source = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            start, end = IPT._cpp_function_span(
                injected_source, "void SparkDataControl::updateBatteryLevel()")
            self.assertEqual(expected, injected_source[start:end])
            backups = list(backup_root.iterdir())
            self.assertTrue(backups)
            self.assertTrue(all(path.suffix == ".bak" for path in backups))

    def test_required_template_has_transfer_safety_fixes(self):
        source = (TEMPLATE / "Ignitron.ino").read_text(errors="replace")
        config = (TEMPLATE / "src/Config_Definitions.h").read_text(errors="replace")
        self.assertIn("ERR BAD_BASE64_LENGTH", source)
        self.assertIn("ERR CHECKSUM_MISMATCH", source)
        self.assertIn("ERR SIZE_OVERFLOW", source)
        self.assertIn('Serial.println("ERR TUNER_REQUIRES_APP_MODE");\n            return;', source)
        self.assertNotIn("ENABLE_AMP_MODE_ROCKER_SWITCH", source)
        self.assertRegex(config, r"(?m)^#define OLED_DRIVER_SH1106\s*$")
        self.assertNotRegex(config, r"(?m)^#define OLED_DRIVER_SSD1306\s*$")

    def test_blocklist_exit_restart_waits_for_button_release(self):
        buttons = (TEMPLATE / "src/SparkButtonHandler.cpp").read_text(errors="replace")
        header = (TEMPLATE / "src/SparkButtonHandler.h").read_text(errors="replace")
        data_source = (TEMPLATE / "src/SparkDataControl.cpp").read_text(errors="replace")
        display_source = (TEMPLATE / "src/SparkDisplayControl.cpp").read_text(errors="replace")
        start, end = IPT._cpp_function_span(
            buttons, "void SparkButtonHandler::readButtons()")
        read_buttons = buttons[start:end]

        self.assertIn("blocklistExitRestartPending_", header)
        self.assertIn("blocklistExitRestartPending_ = true", read_buttons)
        self.assertIn("AMP_BLOCKLIST EXIT_RESTART", read_buttons)
        self.assertIn("spark_dc_->restartESP(false)", read_buttons)
        release_check = read_buttons.index(
            "digitalRead(BUTTON_BANK_UP_GPIO) == LOW")
        restart_check = read_buttons.index("if (blocklistExitRestartPending_)")
        self.assertLess(release_check, restart_check)
        self.assertIn("blocklistCount() + 1", data_source)
        self.assertIn("AMP_BLOCKLIST EXIT_CONFIRM", data_source)
        self.assertIn("AMP_BLOCKLIST EXIT_SELECTED", data_source)
        self.assertIn("REBOOT PEDAL", display_source)
        self.assertIn("UP/DN   P4 SELECT", display_source)

    def test_required_install_guards_optional_amp_blocklist_api(self):
        baseline = ROOT / "Ignitron 1.9.0"
        if not baseline.exists():
            baseline = TEMPLATE
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(baseline, output,
                            ignore=shutil.ignore_patterns(".pio", "backups"))
            IPT.inject_required_ipt_support(TEMPLATE, output)
            source = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            self.assertIn("IPT_AMP_BLOCKLIST_API_GUARD_V1", source)
            self.assertIn("IPT_AMP_BLOCKLIST_CLEAR_GUARD_V1", source)
            self.assertIn("#ifdef ENABLE_IPT_AMP_BLOCKLIST", source)

    def test_stock_battery_enum_is_made_available_to_li_ion_builds(self):
        stock = """#define BATTERY_TYPE_LI_ION 0
#define BATTERY_TYPE_AMP 2
#define BATTERY_TYPE BATTERY_TYPE_LI_ION
#if BATTERY_TYPE == BATTERY_TYPE_LI_ION
const float BATTERY_CAPACITY_VOLTAGE_THRESHOLD_90 = 8.2;
#elif BATTERY_TYPE == BATTERY_TYPE_AMP
const float BATTERY_CAPACITY_VOLTAGE_THRESHOLD_90 = 4000;
enum BatteryChargingStatus {
    BATTERY_CHARGING_STATUS_DISCHARGING,
    BATTERY_CHARGING_STATUS_POWERED
};
#endif
#endif
"""
        normalized = IPT.normalize_battery_charging_status_enum(stock)
        first_endif = normalized.index("#endif")
        enum_position = normalized.index("enum BatteryChargingStatus")
        self.assertGreater(enum_position, first_endif)
        self.assertEqual(1, normalized.count("enum BatteryChargingStatus"))
        self.assertEqual(normalized, IPT.normalize_battery_charging_status_enum(normalized))

    def test_optional_blocklist_mod_is_injected_and_guarded(self):
        self.require_baseline()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(BASELINE, output, ignore=shutil.ignore_patterns(".pio", "backups"))
            IPT.inject_required_ipt_support(TEMPLATE, output)
            IPT.inject_optional_firmware_sources(
                TEMPLATE, output, amp_blocklist=True)
            ino = (output / "Ignitron.ino").read_text(errors="replace")
            self.assertNotIn("IPT_OPTIONAL_AMP_ROCKER_BEGIN", ino)
            self.assertNotIn("ENABLE_AMP_MODE_ROCKER_SWITCH", ino)
            self.assertIn("const bool clearBlockedAmpAtBoot", ino)
            self.assertIn("spark_dc.clearBlockedAmp()", ino)
            buttons = (output / "src/SparkButtonHandler.cpp").read_text(errors="replace")
            self.assertIn("digitalRead(BUTTON_PRESET1_GPIO)", buttons)
            self.assertNotIn("if (digitalRead(BUTTON_PRESET2_GPIO) == HIGH)", buttons)
            bt_header = (output / "src/SparkBTControl.h").read_text(errors="replace")
            bt_source = (output / "src/SparkBTControl.cpp").read_text(errors="replace")
            button_source = (output / "src/SparkButtonHandler.cpp").read_text(errors="replace")
            data_source = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            display_source = (output / "src/SparkDisplayControl.cpp").read_text(errors="replace")
            self.assertIn("lastConnectedAmpAddress_", bt_header)
            self.assertIn("blockedAmpAddresses_", bt_header)
            self.assertIn("blockedAmpNames_", bt_header)
            self.assertIn("removeBlockedAmp", bt_header)
            self.assertIn("using last confirmed connected amp", bt_source)
            self.assertIn("lastConnectedAmpAddress_ = client_->getPeerAddress().toString()", bt_source)
            self.assertIn("while (file.available())", bt_source)
            self.assertIn("isAmpBlocked(advertisedAddress)", bt_source)
            self.assertIn("saveBlockedAmps()", bt_source)
            self.assertIn("sparkAmpName, blockedName, blockedAddress", data_source)
            self.assertIn('showAmpAddressMessage("AMP BLOCKED", blockedName,', data_source)
            self.assertIn("enterBlocklistMenu", data_source)
            self.assertIn("unblockSelectedAmp", data_source)
            self.assertIn("blocklistExitSelected", data_source)
            self.assertIn("blocklistCount() + 1", data_source)
            self.assertIn("blocklistDeletePending_", data_source)
            self.assertIn("AMP_BLOCKLIST DELETE_CONFIRM", data_source)
            self.assertIn("AMP_BLOCKLIST EXIT_CONFIRM", data_source)
            self.assertIn("AMP_BLOCKLIST EXIT_SELECTED", data_source)
            self.assertIn("enterBlocklistMenu", button_source)
            self.assertIn("selectPreviousBlockedAmp", button_source)
            self.assertIn("selectNextBlockedAmp", button_source)
            self.assertIn("BUTTON_PRESET4_GPIO", button_source)
            self.assertIn("blocklistExitRestartPending_", button_source)
            self.assertIn("AMP_BLOCKLIST EXIT_RESTART", button_source)
            button_header = (output / "src/SparkButtonHandler.h").read_text(errors="replace")
            self.assertIn("blocklistExitRestartPending_", button_header)
            self.assertIn("showBlocklistMenu", display_source)
            self.assertIn("UP/DN   P4 DELETE", display_source)
            self.assertIn("REBOOT PEDAL", display_source)
            self.assertIn("UP/DN   P4 SELECT", display_source)
            self.assertIn("YOU SURE? P4 AGAIN", display_source)

    def test_optional_source_install_is_safe_when_source_is_project(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(TEMPLATE, output,
                            ignore=shutil.ignore_patterns(".pio", "backups"))
            changed = IPT.inject_optional_firmware_sources(
                output, output, amp_blocklist=True,
                backup_root=output / "backups/ipt_firmware")
            self.assertTrue(any("already source" in item for item in changed))
            self.assertTrue((output / "Ignitron.ino").exists())

    def test_optional_dual_battery_mod_is_guarded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(TEMPLATE, output,
                            ignore=shutil.ignore_patterns(".pio", "backups"))
            initially_complete = not IPT.inspect_dual_battery_support(output)

            changed = IPT.inject_optional_firmware_sources(
                TEMPLATE, output, dual_battery=True,
                backup_root=output / "backups/ipt_firmware")
            self.assertTrue(changed or initially_complete)
            self.assertEqual([], IPT.inspect_dual_battery_support(output))

            header = (output / "src/SparkDataControl.h").read_text(errors="replace")
            data_control = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            display = (output / "src/SparkDisplayControl.cpp").read_text(errors="replace")
            update_start, update_end = IPT._cpp_function_span(
                data_control, "void SparkDataControl::updateBatteryLevel()"
            )
            request_start, request_end = IPT._cpp_function_span(
                data_control, "void SparkDataControl::checkForUpdates()"
            )
            dual_guard = (
                "#if BATTERY_TYPE == BATTERY_TYPE_AMP || "
                "defined(ENABLE_DUAL_BATTERY_DISPLAY)"
            )
            self.assertIn("#ifdef ENABLE_DUAL_BATTERY_DISPLAY", header)
            self.assertIn("sparkAmpName == AMP_NAME_SPARK_2", header)
            self.assertIn("IPT_DUAL_BATTERY_UPDATE_V1", data_control)
            self.assertIn("IPT_DUAL_BATTERY_REQUEST_V1", data_control)
            self.assertIn("sparkAmpName == AMP_NAME_SPARK_2", data_control)
            self.assertNotIn(dual_guard, data_control[update_start:update_end])
            self.assertIn(dual_guard, data_control[request_start:request_end])
            self.assertIn("IPT_DUAL_BATTERY_DISPLAY_V1", display)
            self.assertIn("sparkDC_->subMode() != SUB_MODE_FX", display)
            self.assertIn("IPT_DUAL_BATTERY_LOOPER_V1", display)
            self.assertIn("statusObject.isAmpBatteryPowered()", display)

            self.assertEqual(
                [],
                IPT.inject_optional_firmware_sources(
                    TEMPLATE, output, dual_battery=True,
                    backup_root=output / "backups/ipt_firmware"),
            )

            # Simulate the manually tested firmware that contains the feature
            # but predates IPT's installation markers. Re-applying must adopt
            # the existing code instead of duplicating C++ declarations.
            for rel_path in (
                    "src/SparkDataControl.h",
                    "src/SparkDataControl.cpp",
                    "src/SparkDisplayControl.cpp"):
                path = output / rel_path
                unmarked = re.sub(
                    r"(?m)^\s*// IPT_DUAL_BATTERY_[A-Z0-9_]+\s*\n",
                    "",
                    path.read_text(errors="replace"),
                )
                path.write_text(unmarked, encoding="utf-8")

            IPT.inject_optional_firmware_sources(
                TEMPLATE, output, dual_battery=True,
                backup_root=output / "backups/ipt_firmware")
            self.assertEqual([], IPT.inspect_dual_battery_support(output))
            header = (output / "src/SparkDataControl.h").read_text(errors="replace")
            data_control = (output / "src/SparkDataControl.cpp").read_text(errors="replace")
            display = (output / "src/SparkDisplayControl.cpp").read_text(errors="replace")
            self.assertEqual(1, header.count("const BatteryLevel ampBatteryDisplayLevel()"))
            self.assertEqual(
                1,
                data_control.count("BatteryLevel SparkDataControl::ampBatteryDisplayLevel_ ="),
            )
            self.assertEqual(1, display.count("switch (sparkDC_->ampBatteryDisplayLevel())"))

    def test_dual_battery_reapply_repairs_misplaced_telemetry_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "firmware"
            shutil.copytree(
                TEMPLATE, output, ignore=shutil.ignore_patterns(".pio", "backups")
            )
            IPT.inject_optional_firmware_sources(
                TEMPLATE, output, dual_battery=True,
                backup_root=output / "backups/ipt_firmware",
            )

            path = output / "src/SparkDataControl.cpp"
            text = path.read_text(errors="replace")
            dual_guard = (
                "#if BATTERY_TYPE == BATTERY_TYPE_AMP || "
                "defined(ENABLE_DUAL_BATTERY_DISPLAY)"
            )
            amp_guard = "#if BATTERY_TYPE == BATTERY_TYPE_AMP"
            update_start, update_end = IPT._cpp_function_span(
                text, "void SparkDataControl::updateBatteryLevel()"
            )
            update_function = text[update_start:update_end].replace(
                amp_guard, dual_guard, 1
            )
            text = text[:update_start] + update_function + text[update_end:]
            request_start, request_end = IPT._cpp_function_span(
                text, "void SparkDataControl::checkForUpdates()"
            )
            request_function = text[request_start:request_end].replace(
                dual_guard, amp_guard, 1
            )
            text = text[:request_start] + request_function + text[request_end:]
            path.write_text(text, encoding="utf-8")

            self.assertTrue(IPT.inspect_dual_battery_support(output))
            changed = IPT.inject_optional_firmware_sources(
                TEMPLATE, output, dual_battery=True,
                backup_root=output / "backups/ipt_firmware",
            )
            self.assertTrue(changed)
            self.assertEqual([], IPT.inspect_dual_battery_support(output))

            repaired = path.read_text(errors="replace")
            update_start, update_end = IPT._cpp_function_span(
                repaired, "void SparkDataControl::updateBatteryLevel()"
            )
            request_start, request_end = IPT._cpp_function_span(
                repaired, "void SparkDataControl::checkForUpdates()"
            )
            self.assertNotIn(dual_guard, repaired[update_start:update_end])
            self.assertIn(dual_guard, repaired[request_start:request_end])

    def test_dual_battery_define_is_added_inside_battery_section(self):
        page = object.__new__(IPT.FirmwareUploadPage)
        config = """#define ENABLE_BATTERY_STATUS_INDICATOR
#ifdef ENABLE_BATTERY_STATUS_INDICATOR
const int BATTERY_VOLTAGE_ADC_PIN = 36;
#endif
"""
        updated = page._set_battery_option_define(
            config, "ENABLE_DUAL_BATTERY_DISPLAY", True)
        self.assertIn("#define ENABLE_DUAL_BATTERY_DISPLAY", updated)
        self.assertLess(
            updated.index("#define ENABLE_DUAL_BATTERY_DISPLAY"),
            updated.index("const int BATTERY_VOLTAGE_ADC_PIN"),
        )

    def test_capture_amp_mode_is_one_shot(self):
        source = (TEMPLATE / "Ignitron.ino").read_text(errors="replace")
        data_control = (TEMPLATE / "src/SparkDataControl.cpp").read_text(errors="replace")
        self.assertIn("if (LittleFS.exists(CAPTURE_MODE_FLAG))", source)
        self.assertIn("LittleFS.remove(CAPTURE_MODE_FLAG);", source)
        self.assertIn('Serial.println("CAPTUREMODE AUTO AMP (ONE SHOT)");', source)
        self.assertIn('u == "CAPTUREKEEPALIVE"', source)
        self.assertIn("CAPTURE_HEARTBEAT_TIMEOUT_MS = 6000", source)
        self.assertIn("CAPTUREMODE USB LOST - RETURNING TO APP MODE", source)
        self.assertIn('u == "CAPTUREEND"', source)
        self.assertIn('Serial.println("OK CAPTUREEND RESTARTING");', source)
        self.assertIn("spark_dc.restartESP(true);", source)
        self.assertIn("int iptPrepareCaptureModeRestart()", source)
        self.assertIn("IPT_CAPTURE_BT_RESTART_V2", data_control)
        self.assertIn("iptPrepareCaptureModeRestart()", data_control)
        self.assertIn("Spark Capture will resume after Bluetooth mode restart", data_control)


class CrossPlatformReleaseTests(unittest.TestCase):
    def test_music_location_accepts_local_folder_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="music folder ") as folder:
            self.assertEqual(Path(folder), IPT.resolve_music_folder(folder))

    def test_music_location_rejects_password_in_smb_address(self):
        with self.assertRaisesRegex(ValueError, "passwords"):
            IPT.resolve_music_folder("smb://user:secret@nas/music")

    def test_music_location_resolves_kde_mount(self):
        with tempfile.TemporaryDirectory() as folder:
            result = SimpleNamespace(returncode=0, stdout=repr((folder,)))
            with mock.patch.object(IPT.sys, "platform", "linux"), mock.patch.object(IPT.shutil, "which", return_value="/usr/bin/gdbus"), mock.patch.object(IPT.subprocess, "run", return_value=result):
                self.assertEqual(Path(folder), IPT.resolve_music_folder("smb://nas/music"))

    def test_volume_is_deferred_until_audio_output_is_playing(self):
        player = mock.Mock()
        player.is_playing.return_value = False
        self.assertFalse(IPT.apply_vlc_volume(player, 80))
        player.audio_set_volume.assert_not_called()
        player.is_playing.return_value = True
        player.audio_set_volume.return_value = 0
        self.assertTrue(IPT.apply_vlc_volume(player, 80))
        player.audio_set_volume.assert_called_once_with(80)

    def test_volume_failure_remains_pending_for_retry(self):
        player = mock.Mock()
        player.is_playing.return_value = True
        player.audio_set_volume.return_value = -1
        self.assertFalse(IPT.apply_vlc_volume(player, 40))

    def test_vlc_none_instance_is_reported_as_runtime_mismatch(self):
        fake_vlc = SimpleNamespace(Instance=lambda *_arguments: None)
        with mock.patch.object(IPT, "load_vlc_module", return_value=fake_vlc):
            with self.assertRaisesRegex(RuntimeError, "core and plugin versions may not match"):
                IPT.create_vlc_instance("--quiet")

    def test_linux_vlc_failure_message_is_actionable_for_both_distro_families(self):
        with mock.patch.object(IPT.sys, "platform", "linux"):
            message = IPT.vlc_install_message("libVLC returned no instance")
        self.assertIn("sudo dnf install vlc", message)
        self.assertIn("sudo apt update && sudo apt install vlc", message)
        self.assertIn("libVLC returned no instance", message)
        self.assertIn("core and plugins", message)

    def test_vlc_self_test_exercises_play_pause_seek_and_stop(self):
        calls = []

        class Resource:
            def release(self):
                calls.append("release")

        class Player(Resource):
            def set_media(self, _media):
                calls.append("set_media")

            def play(self):
                calls.append("play")
                return 0

            def get_state(self):
                return "State.Playing"

            def get_time(self):
                return 0

            def set_pause(self, value):
                calls.append(("pause", value))

            def set_time(self, value):
                calls.append(("seek", value))

            def stop(self):
                calls.append("stop")

        player = Player()

        class Instance(Resource):
            def media_player_new(self):
                return player

            def media_new(self, path):
                self.path = Path(path)
                self.size = self.path.stat().st_size
                return Resource()

        output = []
        with mock.patch.object(IPT, "create_vlc_instance", return_value=Instance()):
            self.assertEqual(0, IPT.run_vlc_self_test(output.append))

        self.assertIn("play", calls)
        self.assertIn(("pause", 1), calls)
        self.assertIn(("seek", 250), calls)
        self.assertIn(("pause", 0), calls)
        self.assertIn("stop", calls)
        self.assertIn("VLC self-test passed", output[0])

    def test_linux_package_uses_system_vlc_and_ci_tests_the_frozen_app(self):
        build_script = (ROOT / "build_release_linux.sh").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/build-release.yml").read_text(encoding="utf-8")
        self.assertIn("libvlc.so*", build_script)
        self.assertIn("libvlccore.so*", build_script)
        self.assertIn("Removing non-portable bundled VLC library", build_script)
        self.assertIn("--vlc-self-test", workflow)
        self.assertIn("Verify packaged Linux VLC runtime", workflow)

    def test_linux_release_documentation_covers_first_build_requirements(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "sudo dnf install curl python3 vlc",
            "sudo apt install curl python3 python3-venv vlc",
            "get-platformio.py",
            '"$HOME/.platformio/penv/bin/platformio" --version',
            "99-platformio-udev.rules",
            '"$HOME/.platformio/penv/bin/platformio" device list',
            "ignitron firmware",
            "Ignitron 1.9.0",
            "run -e esp32dev -t buildfs",
            "Port is busy",
        ):
            self.assertIn(required, readme)

    def test_restore_stock_hardware_resets_every_registered_setting(self):
        def variable(value):
            state = SimpleNamespace(value=value)
            state.get = lambda: state.value
            state.set = lambda new_value: setattr(state, "value", new_value)
            return state

        page = object.__new__(IPT.FirmwareUploadPage)
        page.hardware_pin_vars = {
            name: variable("39") for name in IPT.STOCK_HARDWARE_SETTINGS["pins"]
        }
        for attribute, default in IPT.STOCK_HARDWARE_SETTINGS["variables"].items():
            setattr(page, attribute, variable(not default if isinstance(default, bool) else "39"))
        page.apply_hardware_pins_var = variable(True)
        page.project_var = variable(str(ROOT / "Ignitron"))
        page.app = SimpleNamespace(set_status=lambda _text: None)
        page.append_log = lambda _text: None
        saved_states = []
        page.save_hardware_settings = lambda show_message=False: saved_states.append(
            page.apply_hardware_pins_var.get()) or True

        with mock.patch.object(IPT, "update_settings") as update:
            self.assertTrue(page.restore_stock_hardware_settings(confirm=False))

        self.assertEqual([True], saved_states)
        self.assertFalse(page.apply_hardware_pins_var.get())
        for name, expected in IPT.STOCK_HARDWARE_SETTINGS["pins"].items():
            self.assertEqual(expected, page.hardware_pin_vars[name].get())
        for attribute, expected in IPT.STOCK_HARDWARE_SETTINGS["variables"].items():
            self.assertEqual(expected, getattr(page, attribute).get())
        update.assert_called_once_with(firmware_mod_hardware_pins=False)

    def test_serial_reset_detection_distinguishes_capture_restart(self):
        self.assertTrue(IPT.is_pedal_reset_line("RESET_REASON 3 SOFTWARE_RESET"))
        self.assertTrue(IPT.is_pedal_reset_line("rst:0xc (SW_CPU_RESET)"))
        self.assertTrue(IPT.is_pedal_reset_line("!!! Restarting !!! Resetting Spark mode"))
        self.assertFalse(
            IPT.capture_reset_ends_session(
                "RESET_REASON 3 SOFTWARE_RESET", expected_restart=True
            )
        )
        self.assertTrue(
            IPT.capture_reset_ends_session(
                "!!! Restarting !!! Resetting Spark mode", expected_restart=True
            )
        )
        self.assertTrue(IPT.capture_reset_ends_session("Initializing APP mode"))
        self.assertTrue(IPT.capture_reset_ends_session("ERR CAPTUREKEEPALIVE NOT_ACTIVE"))

    def test_remote_and_capture_publish_specific_header_connection_states(self):
        self.assertEqual("Remote active", IPT.PedalRemotePage.global_connection_text)
        self.assertEqual("Capture active", IPT.CapturePage.global_connection_text)

    def test_fresh_project_uses_sh1106_default_but_configured_project_keeps_driver(self):
        def variable(value):
            state = SimpleNamespace(value=value)
            state.get = lambda: state.value
            state.set = lambda new_value: setattr(state, "value", new_value)
            return state

        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "Ignitron"
            (project / "src").mkdir(parents=True)
            (project / "platformio.ini").write_text(
                "[env:esp32dev]\nboard = esp32dev\n", encoding="utf-8"
            )

            page = object.__new__(IPT.FirmwareUploadPage)
            page.project_var = variable(str(project))
            page.apply_screen_mod_var = variable(True)
            page.apply_amp_blocklist_mod_var = variable(False)
            page.apply_battery_mod_var = variable(False)
            page.apply_led_mod_var = variable(False)
            page.apply_timing_mod_var = variable(False)
            page.env_var = variable("esp32dev")
            page.env_combo = SimpleNamespace(configure=lambda **_kwargs: None)
            page.config_path_var = variable("")
            page.oled_driver_choices = {
                "OLED_DRIVER_SSD1306 - 1.3 inch": "OLED_DRIVER_SSD1306",
                "OLED_DRIVER_SH1106 - 1.3 inch": "OLED_DRIVER_SH1106",
            }
            page.oled_driver_labels_by_define = {
                value: label for label, value in page.oled_driver_choices.items()
            }
            page.oled_driver_var = variable("OLED_DRIVER_SSD1306 - 1.3 inch")
            page.refresh_ports = lambda select_first=False: None
            page.load_env_defaults = lambda: None
            page.load_firmware_settings = lambda show_errors=False: (
                page.oled_driver_var.set("OLED_DRIVER_SSD1306 - 1.3 inch") or True
            )

            with mock.patch.object(IPT, "load_settings", return_value={"firmware_mod_screen": True}):
                page.check_ipt_addon_support = lambda show_message=False: False
                page.load_project_defaults()
                self.assertEqual(
                    "OLED_DRIVER_SH1106 - 1.3 inch", page.oled_driver_var.get()
                )

                page.check_ipt_addon_support = lambda show_message=False: True
                page.load_project_defaults()
                self.assertEqual(
                    "OLED_DRIVER_SSD1306 - 1.3 inch", page.oled_driver_var.get()
                )

    def test_builder_and_firmware_place_workflow_buttons_on_requested_tabs(self):
        source = (ROOT / "ignitron_preset_tools_v2.1.py").read_text(encoding="utf-8")

        builder_start = source.index("class BuilderPage(Page):")
        toolbar_start = source.index("toolbar = tk.Frame(workspace", builder_start)
        toolbar_end = source.index("canvas_wrap = tk.Frame(workspace", toolbar_start)
        builder_toolbar = source[toolbar_start:toolbar_end]
        self.assertIn('text="Load library"', builder_toolbar)
        self.assertIn('command=self.load_library_and_open_firmware', builder_toolbar)
        self.assertNotIn('text="Export + select port"', builder_toolbar)

        firmware_start = source.index("class FirmwareUploadPage(Page):")
        actions_start = source.index("actions = tk.Frame(panel", firmware_start)
        actions_end = source.index("settings_section = tk.Frame(panel", actions_start)
        firmware_actions = source[actions_start:actions_end]
        self.assertIn('text="Export + select port"', firmware_actions)

    def test_sidebar_and_dashboard_place_spark_capture_before_backing_tracks(self):
        source = (ROOT / "ignitron_preset_tools_v2.1.py").read_text(encoding="utf-8")

        sidebar_start = source.index("for key, label, glyph in (")
        sidebar_end = source.index("):", sidebar_start)
        sidebar = source[sidebar_start:sidebar_end]
        self.assertLess(
            sidebar.index('("capture", "Spark Capture", "04")'),
            sidebar.index('("tracks", "Backing Tracks", "05")'),
        )

        cards_start = source.index("cards = (")
        cards_end = source.index("for index, (eyebrow, title, body, page)", cards_start)
        cards = source[cards_start:cards_end]
        self.assertLess(
            cards.index('"Spark Capture"'),
            cards.index('"Backing Tracks"'),
        )

    def test_builder_load_library_opens_first_firmware_tab_after_success(self):
        calls = []
        firmware = SimpleNamespace(
            show_firmware_tab=lambda: calls.append("firmware_tab")
        )
        builder = object.__new__(IPT.BuilderPage)
        builder.app = SimpleNamespace(
            pages={"firmware": firmware},
            show_page=lambda name: calls.append(("show_page", name)),
        )
        builder.load_project_data = lambda show_message=True: calls.append(
            ("load", show_message)
        ) or True

        self.assertTrue(builder.load_library_and_open_firmware())
        self.assertEqual(
            [("load", True), ("show_page", "firmware"), "firmware_tab"], calls
        )

    def test_builder_stays_open_when_library_load_fails(self):
        calls = []
        builder = object.__new__(IPT.BuilderPage)
        builder.app = SimpleNamespace(
            pages={},
            show_page=lambda name: calls.append(("show_page", name)),
        )
        builder.load_project_data = lambda show_message=True: False

        self.assertFalse(builder.load_library_and_open_firmware())
        self.assertEqual([], calls)

    def test_firmware_export_button_delegates_to_preset_builder(self):
        calls = []
        builder = object.__new__(IPT.BuilderPage)
        builder.export_and_upload_filesystem = lambda: calls.append("export") or True
        page = object.__new__(IPT.FirmwareUploadPage)
        page.app = SimpleNamespace(pages={"builder": builder})

        self.assertTrue(page.export_presets_and_select_port())
        self.assertEqual(["export"], calls)

    def test_preflash_selected_save_always_writes_and_verifies_firmware_version(self):
        def variable(value):
            return SimpleNamespace(get=lambda current=value: current)

        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "Ignitron"
            (project / "src").mkdir(parents=True)
            config = project / "src/Config_Definitions.h"
            config.write_text('const string VERSION = "1.9.0";\n', encoding="utf-8")

            page = object.__new__(IPT.FirmwareUploadPage)
            page.app = SimpleNamespace(set_status=lambda _text: None)
            page.project_var = variable(str(project))
            page.fw_version_var = variable("2.1.0")
            page.apply_screen_mod_var = variable(False)
            page.apply_battery_mod_var = variable(False)
            page.apply_timing_mod_var = variable(False)
            page.apply_amp_blocklist_mod_var = variable(False)
            page.apply_led_mod_var = variable(False)
            page.apply_hardware_pins_var = variable(False)
            page.append_log = lambda _text: None

            self.assertTrue(page.save_firmware_settings(show_message=False, selected_only=True))
            self.assertIn('const string VERSION = "2.1.0";', config.read_text(encoding="utf-8"))
            self.assertTrue(page.verify_selected_firmware_settings())

    def test_flash_preparation_applies_then_verifies_before_platformio(self):
        page = object.__new__(IPT.FirmwareUploadPage)
        calls = []
        page.append_log = lambda _text: calls.append("log")
        page.apply_selected_firmware_changes = lambda show_message=False: calls.append("apply") or True
        page.save_firmware_settings = lambda show_message=False, selected_only=True: calls.append(
            ("save", selected_only)) or True
        page.verify_selected_firmware_settings = lambda verify_all=False: calls.append(
            ("verify", verify_all)) or True
        page.use_reliable_upload_speed = lambda: calls.append("speed")
        page.write_platformio_default_env = lambda show_status=True: calls.append("env") or True
        page.write_env_upload_speed = lambda show_status=True: calls.append("upload_speed") or True
        page.write_env_upload_port = lambda show_status=True: calls.append("port") or True

        self.assertTrue(page.prepare_selected_firmware_options(save_config=True))
        self.assertIn(("save", False), calls)
        self.assertIn(("verify", True), calls)
        self.assertLess(calls.index("apply"), calls.index(("save", False)))
        self.assertLess(calls.index(("save", False)), calls.index(("verify", True)))
        self.assertLess(calls.index(("verify", True)), calls.index("env"))

    def test_full_flash_compiles_before_erasing_the_pedal(self):
        def variable(value):
            return SimpleNamespace(get=lambda current=value: current)

        page = object.__new__(IPT.FirmwareUploadPage)
        targets = []
        page.clean_var = variable(True)
        page.erase_var = variable(True)
        page._run_platformio_target = lambda target: targets.append(target) or 0
        page.append_log = lambda _text: None
        page.open_pdf_after_success = None
        page.set_busy = lambda _busy: None
        page.after = lambda _delay, callback: callback()
        page.app = SimpleNamespace(set_status=lambda _text: None)

        page._run_flash_worker()

        self.assertEqual(
            ["clean", "", "buildfs", "erase", "upload", "uploadfs"],
            targets,
        )

    def test_visible_apply_selected_changes_opens_preset_builder(self):
        def variable(value):
            return SimpleNamespace(get=lambda current=value: current)

        page = object.__new__(IPT.FirmwareUploadPage)
        opened_pages = []
        page.app = SimpleNamespace(
            set_status=lambda _text: None,
            show_page=lambda name: opened_pages.append(name),
        )
        page.running = False
        page.project_var = variable(str(ROOT / "Ignitron"))
        page.install_required_support_var = variable(False)
        page.apply_hardware_pins_var = variable(False)
        page.apply_screen_mod_var = variable(False)
        page.apply_amp_blocklist_mod_var = variable(False)
        page.apply_battery_mod_var = variable(False)
        page.apply_led_mod_var = variable(False)
        page.apply_timing_mod_var = variable(False)
        page.save_firmware_settings = lambda show_message=False, selected_only=True: True
        page._write_ipt_setup_log = lambda _text: None

        with mock.patch.object(IPT, "update_settings"), \
                mock.patch.object(IPT.messagebox, "showinfo"):
            self.assertTrue(page.apply_selected_firmware_changes(show_message=True))

        self.assertEqual(["builder"], opened_pages)

    def test_silent_preflash_apply_does_not_leave_firmware(self):
        def variable(value):
            return SimpleNamespace(get=lambda current=value: current)

        page = object.__new__(IPT.FirmwareUploadPage)
        opened_pages = []
        page.app = SimpleNamespace(
            set_status=lambda _text: None,
            show_page=lambda name: opened_pages.append(name),
        )
        page.running = False
        page.project_var = variable(str(ROOT / "Ignitron"))
        page.install_required_support_var = variable(False)
        page.apply_hardware_pins_var = variable(False)
        page.apply_screen_mod_var = variable(False)
        page.apply_amp_blocklist_mod_var = variable(False)
        page.apply_battery_mod_var = variable(False)
        page.apply_led_mod_var = variable(False)
        page.apply_timing_mod_var = variable(False)
        page.save_firmware_settings = lambda show_message=False, selected_only=True: True
        page._write_ipt_setup_log = lambda _text: None

        with mock.patch.object(IPT, "update_settings"):
            self.assertTrue(page.apply_selected_firmware_changes(show_message=False))

        self.assertEqual([], opened_pages)

    def test_serial_handshake_retries_through_boot_without_closing(self):
        clock = [0.0]
        connection = mock.Mock()
        def read(**_kwargs):
            clock[0] += 0.2
            return b"BOOT 90 WAITING_FOR_AMP\n" if clock[0] < 2 else b"IGNITRON_FLASHER 1\n"
        connection.read_until.side_effect = read
        with mock.patch.object(IPT.time, "monotonic", side_effect=lambda: clock[0]), mock.patch.object(IPT.time, "sleep"):
            IPT.verify_ignitron_connection(connection)
        self.assertGreaterEqual(connection.write.call_count, 2)
        connection.close.assert_not_called()
        connection.reset_input_buffer.assert_called_once()

    def test_serial_handshake_rejects_generic_initializing_messages(self):
        clock = [0.0]
        connection = mock.Mock()
        def read(**_kwargs):
            clock[0] += 0.2
            return b"Initializing some other device\n"
        connection.read_until.side_effect = read
        with mock.patch.object(IPT.time, "monotonic", side_effect=lambda: clock[0]), mock.patch.object(IPT.time, "sleep"):
            with self.assertRaisesRegex(TimeoutError, "no Ignitron PING reply"):
                IPT.verify_ignitron_connection(connection, timeout=1)

    def test_serial_handshake_cancellation_does_not_write(self):
        event = mock.Mock()
        event.wait.return_value = True
        connection = mock.Mock()
        with self.assertRaises(InterruptedError):
            IPT.verify_ignitron_connection(connection, stop_event=event)
        connection.write.assert_not_called()

    @unittest.skipUnless(os.name == "posix" and __import__("sys").platform.startswith("linux"), "Linux ioctl test")
    def test_linux_serial_deasserts_both_control_lines_together(self):
        import fcntl
        import struct
        import termios
        class Serial:
            @property
            def dtr(self): return self._dtr_state
            @dtr.setter
            def dtr(self, value): self._dtr_state = value
            @property
            def rts(self): return self._rts_state
            @rts.setter
            def rts(self, value): self._rts_state = value
            def open(self):
                self.fd = 77
                self._update_dtr_state()
                self._update_rts_state()
        with mock.patch.dict("sys.modules", {"serial": SimpleNamespace(Serial=Serial)}), mock.patch.object(fcntl, "ioctl") as ioctl:
            IPT.open_serial_no_reset("/dev/test")
        self.assertTrue(ioctl.call_count)
        for call in ioctl.call_args_list:
            self.assertEqual((77, termios.TIOCMBIC, struct.pack("I", termios.TIOCM_DTR | termios.TIOCM_RTS)), call.args)

    def test_remote_verifies_and_uses_one_connection(self):
        import threading
        page = object.__new__(IPT.PedalRemotePage)
        page.append_log = mock.Mock()
        page.stop_event = threading.Event()
        page.winfo_exists = lambda: False
        page.after = lambda _delay, callback, *args: callback(*args)
        page.app = SimpleNamespace(set_status=mock.Mock())
        for name in ("update_remote_terminal_status", "update_hw_bank_visibility", "update_hardware_indicator", "remote_connected", "send_remote_serial_line", "finish", "handle_detected_serial_end"):
            setattr(page, name, mock.Mock())
        connection = mock.Mock()
        with mock.patch.object(IPT, "open_serial_no_reset", return_value=connection) as opener, mock.patch.object(IPT, "verify_ignitron_connection") as verify:
            IPT.PedalRemotePage.run_tool(page, "/dev/test")
        opener.assert_called_once()
        self.assertIs(connection, verify.call_args.args[0])
        page.remote_connected.assert_called_once_with("/dev/test")
        page.send_remote_serial_line.assert_called_once_with("HWINFO")
        connection.close.assert_called_once()
        page.handle_detected_serial_end.assert_not_called()

    def test_capture_connect_and_backup_do_not_probe_on_the_gui_thread(self):
        import threading
        for active_only in (None, True, False):
            with self.subTest(active_only=active_only):
                page = object.__new__(IPT.CapturePage)
                page.running = False
                page.stop_event = threading.Event()
                page.port_var = SimpleNamespace(get=lambda: "/dev/test")
                page.selected_port = lambda: "/dev/test"
                for name in ("refresh_ports", "update_connection_indicator", "set_action_state",
                             "run_tool", "run_backup", "auto_select_port"):
                    setattr(page, name, mock.Mock())
                page.start_button = mock.Mock()
                page.stop_button = mock.Mock()
                page.connection_state_var = mock.Mock()
                page.app = SimpleNamespace(request_serial_start=mock.Mock(), set_status=mock.Mock())
                with mock.patch.object(IPT, "probe_ignitron_port") as probe, \
                        mock.patch.object(IPT.threading, "Thread") as worker:
                    if active_only is None:
                        page.start()
                    else:
                        page.start_backup(active_only)
                    probe.assert_not_called()
                    page.auto_select_port.assert_not_called()
                    worker.assert_not_called()
                    page.app.request_serial_start.call_args.kwargs["on_ready"]()
                    worker.return_value.start.assert_called_once()
                page.update_connection_indicator.assert_called_once_with(False)
                page.connection_state_var.set.assert_called_with("Connecting...")

    def test_capture_handoff_waits_for_previous_connection_to_finish(self):
        import threading
        app = object.__new__(IPT.IgnitronApp)
        app.pages = {}
        previous = SimpleNamespace(running=True, tool_title="Remote", stop_serial=mock.Mock())
        page = SimpleNamespace(stop_event=threading.Event(), tool_title="Capture", finish=mock.Mock())
        app.active_serial_page = previous
        app.set_status = mock.Mock()
        app.update_global_usb_status = mock.Mock()
        pending = []
        app.after = lambda _delay, callback: pending.append(callback)
        ready = mock.Mock()
        with mock.patch.object(IPT.time, "sleep") as sleep:
            app.request_serial_start(page, on_ready=ready)
            sleep.assert_not_called()
        previous.stop_serial.assert_called_once()
        pending.pop(0)()
        ready.assert_not_called()
        previous.running = False
        pending.pop(0)()
        ready.assert_called_once()
        page.finish.assert_not_called()

    def test_capture_handoff_can_be_cancelled_before_opening_usb(self):
        import threading
        app = object.__new__(IPT.IgnitronApp)
        app.pages = {}
        app.active_serial_page = None
        app.update_global_usb_status = mock.Mock()
        pending = []
        app.after = lambda _delay, callback: pending.append(callback)
        page = SimpleNamespace(stop_event=threading.Event(), finish=mock.Mock())
        ready = mock.Mock()
        app.request_serial_start(page, on_ready=ready)
        page.stop_event.set()
        pending.pop(0)()
        ready.assert_not_called()
        page.finish.assert_called_once()

    def test_capture_verifies_before_requesting_amp_mode_and_reuses_port(self):
        import threading
        page = object.__new__(IPT.CapturePage)
        page.stop_event = threading.Event()
        page.append_log = mock.Mock()
        page.after = mock.Mock()
        page.connection_state_var = mock.Mock()
        connection = mock.Mock()
        connection.read_until.return_value = b"OK CAPTUREMODE READY\n"
        def verify(conn, **kwargs):
            self.assertIs(connection, conn)
            connection.write.assert_not_called()
        with mock.patch.object(IPT, "open_serial_no_reset", return_value=connection) as opener, \
                mock.patch.object(IPT, "verify_ignitron_connection", side_effect=verify):
            result = page._enter_capture_amp_mode("/dev/test")
        self.assertIs(result, connection)
        opener.assert_called_once()
        connection.write.assert_has_calls([mock.call(b"CAPTUREMODE\n"), mock.call(b"CAPTUREKEEPALIVE\n")])
        connection.close.assert_not_called()

    def test_capture_cancel_during_reboot_closes_usb_before_restoring_app_mode(self):
        import threading
        page = object.__new__(IPT.CapturePage)
        page.stop_event = threading.Event()
        page.append_log = mock.Mock()
        page.after = mock.Mock()
        page.connection_state_var = mock.Mock()
        connection = mock.Mock()
        def restarting(**kwargs):
            page.stop_event.set()
            return b"OK CAPTUREMODE RESTARTING\n"
        connection.read_until.side_effect = restarting
        def restore(**kwargs):
            connection.close.assert_called()
            self.assertEqual({"port": "/dev/test"}, kwargs)
        page._return_to_app_mode = mock.Mock(side_effect=restore)
        with mock.patch.object(IPT, "open_serial_no_reset", return_value=connection), \
                mock.patch.object(IPT, "verify_ignitron_connection"):
            with self.assertRaises(InterruptedError):
                page._enter_capture_amp_mode("/dev/test")
        page._return_to_app_mode.assert_called_once()

    @unittest.skipUnless(os.name == "posix", "PTY serial fault test")
    def test_usb_probe_times_out_even_when_input_never_ends_a_line(self):
        import serial
        import threading
        import time
        master, slave = os.openpty()
        # A blocking writer can fill Darwin's PTY buffer after the probe
        # closes its reader, then deadlock os.close(master) during cleanup.
        os.set_blocking(master, False)
        stop = threading.Event()
        def noise():
            while not stop.wait(0.002):
                try:
                    os.write(master, b"x" * 256)
                except BlockingIOError:
                    pass
        writer = threading.Thread(target=noise, daemon=True)
        try:
            connection = serial.Serial(os.ttyname(slave), timeout=0.08)
            writer.start()
            before = time.monotonic()
            with mock.patch.object(IPT, "open_serial_no_reset", return_value=connection):
                self.assertFalse(IPT.probe_ignitron_port(SimpleNamespace(device="test"), timeout=0.2))
            self.assertLess(time.monotonic() - before, 1.0)
            self.assertFalse(connection.is_open)
        finally:
            stop.set()
            if writer.ident is not None:
                writer.join(timeout=1)
                self.assertFalse(writer.is_alive())
            os.close(master)
            os.close(slave)

    def test_auto_detect_does_not_fallback_to_an_unverified_com_port(self):
        stale = SimpleNamespace(
            device="COM6", description="Communications Port", manufacturer="",
            product="", hwid="", vid=None, pid=None,
        )
        pedal = SimpleNamespace(
            device="COM7", description="Silicon Labs CP210x USB to UART Bridge",
            manufacturer="Silicon Labs", product="CP210x USB to UART Bridge",
            hwid="USB VID:PID=10C4:EA60", vid=0x10C4, pid=0xEA60,
        )
        with mock.patch.object(IPT, "list_serial_ports", return_value=[stale, pedal]), \
                mock.patch.object(IPT, "probe_ignitron_port", return_value=False):
            detected, ports = IPT.auto_detect_ignitron_port("COM6")
        self.assertEqual([stale, pedal], ports)
        self.assertIsNone(detected)

    def test_auto_detect_selects_only_the_port_that_answers_as_ignitron(self):
        stale = SimpleNamespace(
            device="COM6", description="Communications Port", manufacturer="",
            product="", hwid="", vid=None, pid=None,
        )
        pedal = SimpleNamespace(
            device="COM7", description="Silicon Labs CP210x USB to UART Bridge",
            manufacturer="Silicon Labs", product="CP210x USB to UART Bridge",
            hwid="USB VID:PID=10C4:EA60", vid=0x10C4, pid=0xEA60,
        )
        with mock.patch.object(IPT, "list_serial_ports", return_value=[stale, pedal]), \
                mock.patch.object(
                    IPT, "probe_ignitron_port",
                    side_effect=lambda port: port.device == "COM7",
                ):
            detected, ports = IPT.auto_detect_ignitron_port("COM6")
        self.assertEqual([stale, pedal], ports)
        self.assertEqual("COM7", detected.device)

    def test_auto_detect_ignores_a_generic_com_port_without_usb_identity(self):
        com1 = SimpleNamespace(
            device="COM1", description="Communications Port", manufacturer="",
            product="", hwid="", vid=None, pid=None,
        )
        with mock.patch.object(IPT, "list_serial_ports", return_value=[com1]), \
                mock.patch.object(IPT, "probe_ignitron_port") as probe:
            detected, ports = IPT.auto_detect_ignitron_port()
        self.assertEqual([com1], ports)
        self.assertIsNone(detected)
        probe.assert_not_called()

    def test_serial_page_keeps_missing_session_port_instead_of_switching_to_com1(self):
        com1 = SimpleNamespace(
            device="COM1", description="Communications Port", manufacturer="",
            product="", hwid="", vid=None, pid=None,
        )

        class Variable:
            def __init__(self, value=""):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        failed = []
        statuses = []
        page = object.__new__(IPT.SerialPage)
        page.port_var = Variable("COM1  |  Communications Port")
        page.port_combo = {}
        page.append_log = lambda _text: None
        page.app = SimpleNamespace(
            session_serial_port="COM7",
            mark_serial_probe_failed=lambda port: failed.append(port),
            set_status=lambda status: statuses.append(status),
        )

        with mock.patch.object(IPT, "list_serial_ports", return_value=[com1]), \
                mock.patch.object(IPT, "probe_ignitron_port") as probe:
            selected = IPT.SerialPage.auto_select_port(page)

        self.assertEqual("", selected)
        self.assertEqual("COM7  |  Not connected", page.port_var.get())
        self.assertEqual(["COM7"], failed)
        self.assertIn("No pedal connected on COM7", statuses)
        probe.assert_not_called()

    def test_repeated_remote_preset_click_keeps_active_cell_selected(self):
        class Cell:
            def __init__(self, background):
                self.default_bg = background
                self.background = background

            def configure(self, **values):
                if "bg" in values:
                    self.background = values["bg"]

        active = Cell(IPT.CARD_ALT)
        active.background = IPT.ORANGE
        other = Cell(IPT.CARD_ALT)
        other.background = "#5a4518"

        page = object.__new__(IPT.PedalRemotePage)
        page.pending_bank = 3
        page.pending_bank_flash_job = None
        page.pending_bank_flash_phase = 1
        page.bank_row_widgets = {3: [active, other]}
        page.active_cell = active
        page.after = lambda _delay, _callback: 99
        paged_banks = []
        page.scroll_pending_bank_into_view = lambda bank: paged_banks.append(bank)

        IPT.PedalRemotePage.flash_pending_bank(page, 3)

        self.assertEqual(IPT.ORANGE, active.background)
        self.assertEqual("#5a4518", other.background)
        self.assertEqual(3, page.pending_bank)
        self.assertEqual(99, page.pending_bank_flash_job)
        self.assertEqual([3], paged_banks)

    def test_pedal_bank_seek_pages_only_when_target_row_is_offscreen(self):
        class Row:
            def __init__(self, top, height=40):
                self.top = top
                self.height = height

            def winfo_y(self):
                return self.top

            def winfo_height(self):
                return self.height

        class Canvas:
            def __init__(self):
                self.scrolls = []

            def update_idletasks(self):
                return None

            def canvasy(self, value):
                return value

            def winfo_height(self):
                return 400

            def yview_scroll(self, amount, unit):
                self.scrolls.append((amount, unit))

        page = object.__new__(IPT.PedalRemotePage)
        page.grid_canvas = Canvas()
        page.bank_row_widgets = {13: [Row(160)], 29: [Row(430)], 2: [Row(-60)]}

        IPT.PedalRemotePage.scroll_pending_bank_into_view(page, 13)
        self.assertEqual([], page.grid_canvas.scrolls)
        IPT.PedalRemotePage.scroll_pending_bank_into_view(page, 29)
        self.assertEqual([(1, "pages")], page.grid_canvas.scrolls)
        IPT.PedalRemotePage.scroll_pending_bank_into_view(page, 2)
        self.assertEqual([(1, "pages"), (-1, "pages")], page.grid_canvas.scrolls)

    def test_preset_confirmation_highlights_without_moving_grid(self):
        class Variable:
            def __init__(self):
                self.value = ""

            def set(self, value):
                self.value = value

        class Cell:
            default_bg = IPT.CARD_ALT

            def __init__(self):
                self.background = self.default_bg

            def configure(self, **values):
                self.background = values.get("bg", self.background)

        scroll_calls = []
        cell = Cell()
        page = object.__new__(IPT.PedalRemotePage)
        page.stop_pending_bank_flash = lambda: None
        page.active_hw_cell = None
        page.active_cell = None
        page.preset_cells = {(13, 3): cell}
        page.grid_canvas = SimpleNamespace(
            yview_moveto=lambda value: scroll_calls.append(value)
        )
        page.current_slot_var = Variable()
        page.current_preset_var = Variable()
        page.draw_current_preset_display = lambda: None

        IPT.PedalRemotePage.set_active_preset(page, 13, 3, "Iron Hammer")

        self.assertEqual(IPT.ORANGE, cell.background)
        self.assertEqual("13-3", page.current_slot_var.value)
        self.assertEqual("Iron Hammer", page.current_preset_var.value)
        self.assertEqual([], scroll_calls)

    def test_remote_terminal_keeps_header_and_send_controls_visible(self):
        source = Path(IPT.__file__).read_text(encoding="utf-8")
        start = source.index("    def show_remote_terminal(self):")
        end = source.index("    def save_remote_terminal_geometry(self):", start)
        terminal_source = source[start:end]
        self.assertIn("fit_popup_geometry_to_screen(", terminal_source)
        self.assertIn("window.geometry(safe_geometry)", terminal_source)
        self.assertIn("window.minsize(", terminal_source)
        self.assertIn('command_row.pack(side="bottom"', terminal_source)
        self.assertIn('wrap="none"', terminal_source)
        self.assertIn("terminal_x_scroll", terminal_source)
        self.assertIn("terminal_y_scroll", terminal_source)
        self.assertLess(
            terminal_source.index("command_row = tk.Frame"),
            terminal_source.index("terminal = tk.Text"),
        )

        class Variable:
            def __init__(self):
                self.value = ""

            def set(self, value):
                self.value = value

        page = object.__new__(IPT.PedalRemotePage)
        page.running = True
        page.connection = object()
        page.selected_port = lambda: "COM7"
        page.remote_terminal_status_var = Variable()
        IPT.PedalRemotePage.update_remote_terminal_status(page)
        self.assertEqual("Connected: COM7 @ 115200", page.remote_terminal_status_var.value)

    def test_remote_terminal_repairs_oversized_offscreen_saved_geometry(self):
        geometry = IPT.fit_popup_geometry_to_screen(
            "1920x1000+-135+266",
            1920,
            1080,
            0,
            0,
            1920,
            1080,
        )
        self.assertEqual("1080x620+420+230", geometry)
        self.assertEqual(
            "1200x700+100+80",
            IPT.fit_popup_geometry_to_screen(
                "1200x700+100+80",
                1920,
                1080,
                0,
                0,
                1920,
                1080,
            ),
        )

    def test_remote_terminal_easter_egg_is_local_and_case_insensitive(self):
        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        shown = []
        serial_writes = []
        page = object.__new__(IPT.PedalRemotePage)
        page.remote_terminal_entry_var = Variable("  rock on  ")
        page.show_remote_terminal_easter_egg = lambda: shown.append(True)
        page.send_remote_serial_line = lambda command, echo=False: serial_writes.append(
            (command, echo)
        )

        IPT.PedalRemotePage.send_remote_terminal_command(page)

        self.assertEqual([True], shown)
        self.assertEqual([], serial_writes)
        self.assertEqual("", page.remote_terminal_entry_var.value)
        self.assertIn("P R E S E T   T O O L S", IPT.REMOTE_TERMINAL_EASTER_EGG_ART)
        self.assertIn("||||", IPT.REMOTE_TERMINAL_EASTER_EGG_ART)
        self.assertIn("[##########]", IPT.REMOTE_TERMINAL_EASTER_EGG_ART)
        lines = IPT.REMOTE_TERMINAL_EASTER_EGG_ART.splitlines()
        self.assertGreaterEqual(len(lines), 60)
        self.assertLessEqual(max(map(len, lines)), 68)

    def test_remote_terminal_loads_and_sizes_compact_ascii_logo_asset(self):
        art = IPT.load_remote_terminal_easter_egg_art()
        lines = art.splitlines()
        self.assertEqual(60, len(lines))
        self.assertEqual(120, max(map(len, lines)))
        self.assertEqual(7, IPT.remote_terminal_art_font_size(art))
        self.assertIn(IPT.REMOTE_TERMINAL_EASTER_EGG_ART_FILE, RELEASE_TOOLS.SOURCE_FILES)
        for script_name in (
            "build_release.ps1",
            "build_release_linux.sh",
            "build_release_mac.sh",
        ):
            script = (ROOT / script_name).read_text(encoding="utf-8")
            self.assertIn(IPT.REMOTE_TERMINAL_EASTER_EGG_ART_FILE, script)

    def test_confirmed_port_updates_only_the_selected_platformio_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            platformio = Path(temp) / "platformio.ini"
            platformio.write_text(
                "[platformio]\n"
                "default_envs = esp32dev\n\n"
                "[env:esp32dev]\n"
                "upload_port = COM6 ; previous pedal\n"
                "upload_speed = 460800\n\n"
                "[env:alternate]\n"
                "upload_port = COM9\n",
                encoding="utf-8",
            )
            self.assertEqual("esp32dev", IPT.parse_platformio_default_env(platformio))
            success, _message = IPT.write_platformio_section_option(
                platformio, "env:esp32dev", "upload_port", "COM7"
            )
            self.assertTrue(success)
            text = platformio.read_text(encoding="utf-8")
            self.assertIn("upload_port = COM7  ; previous pedal", text)
            self.assertIn("[env:alternate]\nupload_port = COM9", text)

    def test_platformio_default_environment_falls_back_to_first_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            platformio = Path(temp) / "platformio.ini"
            platformio.write_text("[env:usbpedal]\nboard = esp32dev\n", encoding="utf-8")
            self.assertEqual("usbpedal", IPT.parse_platformio_default_env(platformio))

    def test_user_data_override_is_writable_and_platform_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.dict(os.environ, {"IGNITRON_CONFIG_DIR": temp}):
                path = IPT.user_data_file("settings.json", migrate_legacy=False)
                self.assertEqual(Path(temp).resolve(), path.parent.resolve())
                IPT.save_settings({"serial_port": "COM7"})
                self.assertEqual("COM7", IPT.load_settings()["serial_port"])

    def test_public_release_versions_agree(self):
        self.assertEqual("2.1.01", IPT.APP_VERSION)
        root = Path(IPT.__file__).parent
        for name in ("build_release_linux.sh", "build_release_mac.sh", "build_release.ps1"):
            self.assertRegex((root / name).read_text(), r'(?:RELEASE_VERSION|ReleaseVersion)\s*=\s*"2\.1\.01"')
        self.assertIn('VERSION = "2.1.01"', (root / "Ignitron/src/Config_Definitions.h").read_text())
        self.assertIn('Name=Ignitron Preset Tools 2.1.01', (root / "install_linux.sh").read_text())
        workflow = (root / ".github/workflows/build-release.yml").read_text()
        for platform in ("Windows", "Linux", "macOS"):
            self.assertIn(f"Ignitron-Preset-Tools-v2.1.01-{platform}", workflow)

    def test_removed_live_library_page_is_not_shipped(self):
        source = Path(IPT.__file__).read_text(encoding="utf-8")
        self.assertNotIn("class LiveLibraryPage", source)
        self.assertNotIn("Live Library", source)

    def test_obsolete_2_0_firmware_change_pdf_is_not_released(self):
        self.assertNotIn(
            "Ignitron_IPT_2.1_Firmware_Changes.pdf",
            RELEASE_TOOLS.SOURCE_FILES,
        )

    def test_bundled_firmware_preset_lists_reference_valid_json(self):
        for project_name in ("Ignitron", "Ignitron 1.9.0"):
            data_dir = ROOT / project_name / "data"
            preset_list = data_dir / "PresetList.txt"
            self.assertTrue(preset_list.exists(), project_name)
            entries = [
                line.strip()
                for line in preset_list.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            self.assertTrue(entries, project_name)
            for entry in entries:
                preset = data_dir / entry
                self.assertTrue(preset.exists(), f"{project_name}: missing {entry}")
                json.loads(preset.read_text(encoding="utf-8"))

    def test_firmware_notebook_uses_large_high_contrast_tabs(self):
        source = Path(IPT.__file__).read_text(encoding="utf-8")
        self.assertIn('ttk.Notebook(self, style="Firmware.TNotebook")', source)
        self.assertIn('"Firmware.TNotebook.Tab"', source)
        self.assertIn('padding=(22, 10)', source)
        self.assertIn('background=[("selected", GOLD), ("active", BORDER)]', source)

    def test_release_firmware_preserves_presets_but_removes_host_ports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "release" / "ignitron firmware"
            (source / "data/config").mkdir(parents=True)
            (source / "src").mkdir()
            (source / "data/Tone.json").write_text('{"Name":"Tone"}\n', encoding="utf-8")
            (source / "data/PresetList.txt").write_text("Tone.json\n", encoding="utf-8")
            (source / "data/config/SparkMode.config").write_text("2\n", encoding="ascii")
            (source / "platformio.ini").write_text(
                "[env:esp32dev]\nupload_port = COM7\nmonitor_port = /dev/ttyUSB0\nupload_speed = 460800\n",
                encoding="utf-8",
            )
            (source / "backups").mkdir()
            (source / "backups/private.txt").write_text("not shipped", encoding="utf-8")

            RELEASE_TOOLS.stage_firmware(source, destination)

            self.assertTrue((destination / "data/Tone.json").exists())
            self.assertFalse((destination / "backups").exists())
            platformio = (destination / "platformio.ini").read_text(encoding="utf-8")
            self.assertNotIn("upload_port", platformio)
            self.assertNotIn("monitor_port", platformio)
            self.assertIn("upload_speed = 460800", platformio)
            self.assertEqual("1", (destination / "data/config/SparkMode.config").read_text().strip())
            RELEASE_TOOLS.verify_release(destination.parent)

    def test_source_release_stages_current_and_1_9_firmware(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            destination = root / "release"
            source.mkdir()
            for name in RELEASE_TOOLS.SOURCE_FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("release fixture\n", encoding="utf-8")
            for name in RELEASE_TOOLS.SOURCE_DIRECTORIES:
                folder = source / name
                folder.mkdir(parents=True)
                (folder / "keep.txt").write_text("kept\n", encoding="utf-8")
            for source_name, _destination_name in RELEASE_TOOLS.FIRMWARE_PROJECTS:
                firmware = source / source_name
                (firmware / "data/config").mkdir(parents=True)
                (firmware / "platformio.ini").write_text(
                    "[env:esp32dev]\nupload_port = COM7\n", encoding="utf-8"
                )
                (firmware / "doxyfile").write_text(
                    "OUTPUT_DIRECTORY = /" + "Users/private/Documents\n", encoding="utf-8"
                )
                (firmware / ".pio").mkdir()
                (firmware / ".pio/private.bin").write_bytes(b"generated")

            RELEASE_TOOLS.stage_source(source, destination)

            for _source_name, destination_name in RELEASE_TOOLS.FIRMWARE_PROJECTS:
                firmware = destination / destination_name
                self.assertTrue((firmware / "platformio.ini").exists())
                self.assertFalse((firmware / ".pio").exists())
                self.assertFalse((firmware / "doxyfile").exists())
                self.assertNotIn(
                    "upload_port",
                    (firmware / "platformio.ini").read_text(encoding="utf-8"),
                )

    def test_release_privacy_check_allows_ports_and_presets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "data/Tone.json").write_text('{"port":"COM7","device":"/dev/ttyUSB0"}', encoding="utf-8")
            RELEASE_TOOLS.verify_release(root)

    def test_release_privacy_check_rejects_settings_and_user_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Assemble the deliberately private example at runtime so the
            # release privacy scanner does not flag its own test fixture.
            private_path = "C:" + "/" + "Users/example/Music"
            (root / "settings.json").write_text(
                json.dumps({"folder": private_path}), encoding="utf-8"
            )
            with self.assertRaises(SystemExit):
                RELEASE_TOOLS.verify_release(root)

    def test_release_privacy_check_rejects_unix_home_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unix_home = "/" + "Users/private/Documents"
            (root / "config.txt").write_text(unix_home, encoding="utf-8")
            with self.assertRaises(SystemExit):
                RELEASE_TOOLS.verify_release(root)

    def test_release_privacy_check_rejects_generated_cache_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache = root / "Ignitron/.pio"
            cache.mkdir(parents=True)
            (cache / "firmware.bin").write_bytes(b"generated")
            with self.assertRaises(SystemExit):
                RELEASE_TOOLS.verify_release(root)


if __name__ == "__main__":
    unittest.main()

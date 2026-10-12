"""Regression checks for install preservation, capture files, and USB backups."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import preset_puller as puller
from preset_capture import PresetCaptureDecoder, save_captured_preset

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('ipt_audit', ROOT / 'ignitron_preset_tools_v2.1.py')
IPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IPT)


class CaptureFilesTests(unittest.TestCase):
    def test_nested_and_inline_json_with_interleaved_heartbeat(self):
        preset = {'UUID': 'one', 'Name': 'Tone', 'Pedals': [{'Name': 'amp', 'Parameters': [0.5]}]}
        decoder = PresetCaptureDecoder()
        self.assertEqual(preset, decoder.feed('JSON STRING: ' + json.dumps(preset)))
        decoder.feed('received from app:')
        result = None
        for line in json.dumps(preset, indent=2).splitlines():
            self.assertIsNone(decoder.feed('OK CAPTUREKEEPALIVE'))
            value = decoder.feed(line)
            if value is not None:
                self.assertIsNone(result)
                result = value
        self.assertEqual(preset, result)

    def test_same_names_and_edited_uuids_never_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            first = {'UUID': 'one', 'Name': 'Same Tone', 'Pedals': []}
            second = {**first, 'UUID': 'two'}
            edited = {**first, 'Pedals': [{'Name': 'amp'}]}
            paths = [save_captured_preset(temp, preset)[0] for preset in (first, second, edited)]
            self.assertEqual(3, len(set(paths)))
            for path, expected in zip(paths, (first, second, edited)):
                self.assertEqual(expected, json.loads(path.read_text()))
            duplicate, created = save_captured_preset(temp, first)
            self.assertEqual(paths[0], duplicate)
            self.assertFalse(created)


class FakeSerial:
    def __init__(self, replies=None):
        self.is_open = True
        self.data = bytearray()
        self.replies = replies or {}
        self.commands = []
        self.timeout = 0.1
        self.lock = threading.Lock()

    def write(self, value):
        command = value.decode().strip()
        self.commands.append(command)
        with self.lock:
            self.data.extend(self.replies.get(command, b''))

    def read(self, count):
        time.sleep(0.002)
        with self.lock:
            data = bytes(self.data[:count])
            del self.data[:count]
        return data

    def close(self):
        self.is_open = False


def preset_reply():
    preset = {'UUID': 'one', 'Name': 'Tone', 'Pedals': []}
    return ('LISTPRESETS_START\nreading preset filename: tone.json\nJSON STRING: ' +
            json.dumps(preset) + '\nLISTPRESETS_DONE\n').encode()


class BackupTests(unittest.TestCase):
    def test_failed_backup_write_does_not_leave_a_completed_file(self):
        connection = FakeSerial({'LISTPRESETS': preset_reply()})
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(puller.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(RuntimeError, 'No valid presets'):
                puller.pull_presets('unused', include_only_active=False, connection=connection,
                                    output_root=temp, open_folder_after=False)
            self.assertEqual([], list(Path(temp).rglob('*.json')))
            self.assertEqual([], list(Path(temp).rglob('*.tmp')))

    def test_full_library_rejects_partial_backup(self):
        reply = preset_reply().replace(b'LISTPRESETS_DONE',
            b'reading preset filename: broken.json\nJSON STRING: {broken}\nLISTPRESETS_DONE')
        connection = FakeSerial({'LISTPRESETS': reply})
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'Incomplete backup'):
                puller.pull_presets('unused', include_only_active=False, connection=connection,
                                    output_root=temp, open_folder_after=False)

    def test_backups_started_in_same_second_have_separate_folders(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(puller, 'timestamp_now', return_value='same'):
            first, _ = puller.resolve_out_paths(temp)
            second, _ = puller.resolve_out_paths(temp)
            self.assertNotEqual(first, second)

    def test_empty_preset_file_is_an_incomplete_backup(self):
        reply = preset_reply().replace(b'LISTPRESETS_DONE',
            b'reading preset filename: empty.json\nLISTPRESETS_DONE')
        connection = FakeSerial({'LISTPRESETS': reply})
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'Incomplete backup'):
                puller.pull_presets('unused', include_only_active=False, connection=connection,
                                    output_root=temp, open_folder_after=False)

    def test_backup_reuses_verified_port_and_leaves_it_open(self):
        connection = FakeSerial({
            'LISTBANKS': b'LISTBANKS_START\n-- Bank 1\ntone.json\nLISTBANKS_DONE\n',
            'LISTPRESETS': preset_reply(),
        })
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(puller.serial, 'Serial') as opener:
            stats = puller.pull_presets('unused', connection=connection, output_root=temp, open_folder_after=False)
            self.assertEqual(1, stats['saved'])
            self.assertEqual(1, len(list(Path(temp).rglob('tone.json'))))
            opener.assert_not_called()
        self.assertTrue(connection.is_open)

    def test_empty_presetlist_does_not_fall_back_to_whole_library(self):
        connection = FakeSerial({'LISTBANKS': b'LISTBANKS_START\nLISTBANKS_DONE\n'})
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'no preset filenames'):
                puller.pull_presets('unused', connection=connection, output_root=temp, open_folder_after=False)
        self.assertNotIn('LISTPRESETS', connection.commands)
        self.assertTrue(connection.is_open)

    def test_read_error_is_reported_without_two_minute_wait(self):
        connection = FakeSerial()
        connection.read = mock.Mock(side_effect=OSError('USB disconnected'))
        before = time.monotonic()
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'USB disconnected'):
                puller.pull_presets('unused', include_only_active=False, connection=connection,
                                    output_root=temp, open_folder_after=False)
        self.assertLess(time.monotonic() - before, 2)

    def test_cancelled_backup_does_not_issue_read_commands(self):
        connection = FakeSerial()
        stop = threading.Event(); stop.set()
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(InterruptedError):
                puller.pull_presets('unused', connection=connection, stop_event=stop,
                                    output_root=temp, open_folder_after=False)
        self.assertEqual([], connection.commands)

    def test_thread_joins_on_supported_python_versions(self):
        reader = puller.SerialReader('unused', connection=FakeSerial())
        reader.start(); self.assertTrue(reader.ready.wait(1)); reader.stop(); reader.join(1)
        self.assertFalse(reader.is_alive())


@unittest.skipUnless(__import__('sys').platform.startswith('linux'), 'Linux installer tests')
class InstallerTests(unittest.TestCase):
    def test_upgrade_and_uninstall_preserve_working_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / 'release with spaces'; package.mkdir()
            fake_home = root / 'test home'; fake_home.mkdir()
            data = root / 'test data'
            env = {**os.environ, 'IPT_TEST_HOME': str(fake_home), 'XDG_DATA_HOME': str(data)}
            # Keep the real HOME unchanged. The fixture substitutes only its
            # expansion in a copy of the scripts to isolate their destinations.
            for name in ('install_linux.sh', 'uninstall_linux.sh'):
                script = (ROOT / name).read_text().replace('${HOME}', '${IPT_TEST_HOME}').replace('$HOME', '${IPT_TEST_HOME}')
                (package / name).write_text(script)
            (package / 'app').mkdir()
            binary = package / 'app/ignitron-preset-tools'
            binary.write_text('#!/bin/sh\nprintf "version-one"\n'); binary.chmod(0o755)
            project = package / 'ignitron firmware'; project.mkdir()
            (project / 'platformio.ini').write_text('original')
            def run(script, *args):
                subprocess.run(['sh', str(package / script), *args], env=env, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            run('install_linux.sh')
            working = data / 'ignitron-preset-tools/ignitron firmware'
            (working / 'platformio.ini').write_text('user configuration')
            for folder in ('captures', 'backups', 'data'):
                (working / folder).mkdir()
                (working / folder / 'user.json').write_text('{"kept": true}')
            before = {str(p.relative_to(working)): p.read_bytes() for p in working.rglob('*') if p.is_file()}
            binary.write_text('#!/bin/sh\nprintf "version-two"\n')
            (project / 'platformio.ini').write_text('new bundled template')
            run('install_linux.sh')
            after = {str(p.relative_to(working)): p.read_bytes() for p in working.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            template = data / 'ignitron-preset-tools/firmware templates/ignitron firmware/platformio.ini'
            self.assertEqual('new bundled template', template.read_text())
            result = subprocess.check_output([str(fake_home / '.local/bin/ignitron-preset-tools')], text=True)
            self.assertEqual('version-two', result)
            desktop = (data / 'applications/ignitron-preset-tools.desktop').read_text()
            self.assertIn('Exec="', desktop)
            run('uninstall_linux.sh')
            self.assertTrue((working / 'captures/user.json').exists())
            self.assertFalse((data / 'ignitron-preset-tools/app').exists())
            run('uninstall_linux.sh', '--purge')
            self.assertFalse((data / 'ignitron-preset-tools').exists())


class WorkflowTests(unittest.TestCase):
    def test_export_backs_up_replaced_json_and_refuses_ambiguous_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; source.mkdir()
            output = root / 'output'; output.mkdir()
            (source / 'tone.json').write_text('{"Name": "new", "Pedals": []}')
            previous = '{"Name": "old", "Pedals": []}'
            (output / 'tone.json').write_text(previous)
            page = object.__new__(IPT.BuilderPage)
            page.output_folder = output
            page.app = SimpleNamespace(set_status=mock.Mock())
            page.bank_count = 1
            page.slots = {(1, slot): 'tone.json' for slot in range(1, 5)}
            page.presets = [{'filename': 'tone.json', 'path': source / 'tone.json', 'uuid': 'ONE',
                             'data': {'Name': 'new', 'Pedals': []}}]
            with mock.patch.object(IPT, 'generate_preset_chart', return_value=output / 'PresetList.pdf'):
                self.assertTrue(page.export(show_message=False, backup_existing=False))
            backups = list((output / '_ipt_backups').glob('tone*.bak'))
            self.assertEqual(1, len(backups))
            self.assertEqual(previous, backups[0].read_text())
            page.presets.append({**page.presets[0], 'data': {'Name': 'different', 'Pedals': []}})
            with mock.patch.object(IPT.messagebox, 'showerror') as dialog:
                self.assertFalse(page.export(show_message=False))
                dialog.assert_called_once()

    def test_filesystem_build_failure_never_reaches_erase(self):
        page = object.__new__(IPT.FirmwareUploadPage)
        page.clean_var = SimpleNamespace(get=lambda: True)
        page.erase_var = SimpleNamespace(get=lambda: True)
        page.app = SimpleNamespace(set_status=mock.Mock())
        page.append_log = mock.Mock()
        page.after = lambda _delay, fn: fn()
        page.set_busy = mock.Mock()
        called = []
        def run(target):
            called.append(target)
            return 1 if target == 'buildfs' else 0
        page._run_platformio_target = run
        page._run_flash_worker()
        self.assertEqual(['clean', '', 'buildfs'], called)
        page.set_busy.assert_called_once_with(False)

    def test_non_object_settings_do_not_crash_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text('[]')
            with mock.patch.object(IPT, 'settings_file', return_value=path):
                self.assertEqual({}, IPT.load_settings())
                IPT.save_settings({'volume': 20})
                self.assertEqual({'volume': 20}, IPT.load_settings())
                with mock.patch.object(IPT.os, 'replace', side_effect=OSError('disk failure')):
                    with self.assertRaises(OSError): IPT.save_settings({'volume': 30})
                self.assertEqual({'volume': 20}, IPT.load_settings())


if __name__ == '__main__':
    unittest.main()

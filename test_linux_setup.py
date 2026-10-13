"""Exercise the online install flow with isolated package/network/privilege tools."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from release_tools import stage_linux_setup

ROOT = Path(__file__).resolve().parent

# These commands never elevate or contact the network. Real tar, sha256sum and
# the real per-user app installer are used against an isolated package/home.
FAKE_TOOL = r'''import json, os, shutil, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
c = json.loads(Path(os.environ['IPT_SETUP_FIXTURE']).read_text())
with open(c['trace'], 'a') as f: f.write(json.dumps([name, *args]) + '\n')
if name == 'id': print(c.get('uid', 1000))
elif name == 'uname': print(c.get('arch', 'x86_64') if args == ['-m'] else 'Linux')
elif name in ('rpm', 'dpkg-query'):
    missing = c.get('missing', [])
    if args[-1] in missing: sys.exit(1)
    if name == 'dpkg-query': print('install ok installed')
elif name == 'sudo':
    if c.get('fail') == 'sudo': sys.exit(1)
    if args == ['-v']: sys.exit(0)
    assert args[0] in ('dnf', 'apt-get', 'install', 'udevadm', 'env'), args
    if args[0] == 'env': assert args[1:3] == ['DEBIAN_FRONTEND=noninteractive', 'apt-get'], args
    if args[0] == 'install':
        assert args[-1] == c['rules'], args
        Path(c['rules']).parent.mkdir(parents=True, exist_ok=True)
        sys.exit(subprocess.call(['/usr/bin/install', *args[1:]]))
    sys.exit(subprocess.call(args))
elif name in ('dnf', 'apt-get', 'udevadm'):
    if c.get('fail') == name: sys.exit(1)
elif name == 'curl':
    if c.get('fail') == 'download': sys.exit(22)
    dest = Path(args[args.index('--output') + 1]); url = args[-1]
    if url.endswith('.tar.gz'): shutil.copyfile(c['archive'], dest)
    elif url.endswith('SHA256SUMS.txt'):
        digest = '0' * 64 if c.get('fail') == 'checksum' else c['sha256']
        dest.write_text(digest + '  ' + c['archive_name'] + '\n')
    elif url.endswith('.rules'):
        dest.write_text('bad response' if c.get('fail') == 'rules' else 'ATTRS{idVendor}=="10c4", MODE="0666"\n')
    elif url.endswith('get-platformio.py'):
        dest.write_text("from pathlib import Path\nimport shutil\np=Path(" + repr(c['pio']) + ")\np.parent.mkdir(parents=True,exist_ok=True)\nshutil.copyfile(" + repr(c['tool']) + ",p)\np.chmod(0o755)\n")
    else: raise AssertionError(url)
elif name in ('platformio', 'pio'):
    if args == ['--version']: print('PlatformIO Core, version 6.2.0')
    else:
        assert args[0] == 'run', args
        assert '--target' not in args or args[-1] == 'buildfs', args
        project = Path(args[args.index('--project-dir') + 1])
        (project / '.pio').mkdir(exist_ok=True)
        if c.get('fail') == 'build' or (c.get('fail') == 'buildfs' and args[-1] == 'buildfs'): sys.exit(1)
elif name == 'ignitron-preset-tools':
    assert args in (['--vlc-self-test'], ['--vlc-audio-self-test']), args
    if c.get('fail') == 'audio' and args == ['--vlc-audio-self-test']: sys.exit(1)
    print('VLC self-test passed')
else: raise AssertionError(name)
'''


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux setup integration tests')
class LinuxSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home with spaces'; self.home.mkdir()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        self.tool = self.bin / 'tool'
        self.tool.write_text('#!/usr/bin/env python3\n' + FAKE_TOOL)
        self.tool.chmod(0o755)
        for name in ('id', 'uname', 'rpm', 'dpkg-query', 'sudo', 'curl', 'dnf', 'apt-get', 'udevadm'):
            (self.bin / name).symlink_to(self.tool)
        self.os_release = self.root / 'os release'
        self.os_release.write_text('ID=fedora\nPRETTY_NAME="Test Fedora"\n')
        self.rules = self.root / 'system/99-platformio-udev.rules'
        self.script = self.root / 'setup_linux.sh'
        source = (ROOT / 'setup_linux.sh').read_text()
        source = source.replace('$HOME', '${IPT_TEST_HOME}')
        source = source.replace('/etc/os-release', shlex.quote(str(self.os_release)))
        source = source.replace('/run/ostree-booted', shlex.quote(str(self.root / 'ostree')))
        source = source.replace('/etc/udev/rules.d/99-platformio-udev.rules', shlex.quote(str(self.rules)))
        self.script.write_text(source)
        self.package = self.root / 'Ignitron Preset Tools v2.1.02 Linux-x64'
        (self.package / 'app').mkdir(parents=True)
        shutil.copy2(self.tool, self.package / 'app/ignitron-preset-tools')
        (self.package / 'install_linux.sh').write_text((ROOT / 'install_linux.sh').read_text().replace('${HOME}', '${IPT_TEST_HOME}').replace('$HOME', '${IPT_TEST_HOME}'))
        (self.package / 'ignitron firmware').mkdir()
        (self.package / 'ignitron firmware/platformio.ini').write_text('[env:esp32dev]\n')
        self.archive = self.root / 'release.tar.gz'
        self.repack()
        self.config_file = self.root / 'fixture.json'
        self.config = {'trace': str(self.root / 'trace'), 'rules': str(self.rules),
                       'archive': str(self.archive), 'archive_name': 'Ignitron.Preset.Tools.v2.1.02.Linux-x64.tar.gz',
                       'sha256': hashlib.sha256(self.archive.read_bytes()).hexdigest(),
                       'pio': str(self.home / '.platformio/penv/bin/platformio'), 'tool': str(self.tool)}
        self.env = {**os.environ, 'IPT_TEST_HOME': str(self.home), 'IPT_SETUP_FIXTURE': str(self.config_file),
                    'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'XDG_DATA_HOME': str(self.home / 'data'), 'XDG_STATE_HOME': str(self.home / 'state'),
                    'XDG_CONFIG_HOME': str(self.home / 'config'), 'XDG_CURRENT_DESKTOP': 'KDE', 'DESKTOP_SESSION': 'plasma'}

    def repack(self):
        with tarfile.open(self.archive, 'w:gz') as archive:
            archive.add(self.package, arcname=self.package.name)

    def run_setup(self, *args):
        self.config_file.write_text(json.dumps(self.config))
        return subprocess.run(['bash', str(self.script), *args], env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=25)

    def commands(self):
        trace = Path(self.config['trace'])
        return [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []

    def bundle(self, arch='x64'):
        for name in ('launch_linux_setup.sh', 'START-HERE-Linux.txt'):
            shutil.copy2(ROOT / name, self.root / name)
        stage_linux_setup(self.root, self.package, '2.1.02', arch)
        self.script = self.package / 'setup_linux.sh'

    def test_bundled_setup_needs_no_app_download_and_leaves_extraction_pristine(self):
        self.bundle()
        before = {p.relative_to(self.package): p.read_bytes() for p in self.package.rglob('*') if p.is_file()}
        result = self.run_setup()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn('SETUP COMPLETE', result.stdout)
        self.assertFalse(any(c[0] == 'curl' and c[-1].endswith(('.tar.gz', 'SHA256SUMS.txt')) for c in self.commands()))
        after = {p.relative_to(self.package): p.read_bytes() for p in self.package.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.package / 'ignitron firmware/.pio').exists())
        self.assertTrue((self.home / 'data/ignitron-preset-tools/app/ignitron-preset-tools').exists())

    def test_wrong_arch_incomplete_and_corrupt_bundles_stop_before_sudo(self):
        self.bundle(arch='arm64')
        self.assert_stopped(self.run_setup())
        (self.package / 'linux-package.txt').write_text('2.1.02 x64\n')
        self.assert_stopped(self.run_setup())  # changed metadata fails manifest
        (self.package / 'linux-package.txt').unlink()
        self.assert_stopped(self.run_setup())
        self.assertFalse(any(c[0] in ('sudo', 'curl') for c in self.commands()))

    def test_launcher_keeps_installer_failure_status(self):
        self.bundle()
        self.script.write_text('exit 7\n')
        result = subprocess.run(['bash', str(self.package / 'launch_linux_setup.sh')],
                                env=self.env, input='', capture_output=True, text=True, timeout=10)
        self.assertEqual(7, result.returncode)
        self.assertIn('Installation did not finish', result.stdout)
        self.assertNotIn('Opening Ignitron', result.stdout)

    def test_desktop_launcher_handles_moved_folder_and_shell_metacharacters(self):
        # Exercise the desktop implementation's actual Exec parsing, not a
        # home-grown split. GI is optional on developer machines/non-Linux CI.
        python = '/usr/bin/python3'
        probe = subprocess.run([python, '-c', 'from gi.repository import Gio'], capture_output=True)
        if probe.returncode:
            self.skipTest('Gio desktop parser is unavailable')
        self.bundle()
        strange = self.root / "Moved 100% ' $folder $(false)"
        self.package.rename(strange)
        launcher = strange / 'launch_linux_setup.sh'
        launcher.write_text('printf success > "$(dirname -- "$0")/launched.txt"\n')
        desktop = strange / 'Install Ignitron.desktop'
        if shutil.which('desktop-file-validate'):
            subprocess.run(['desktop-file-validate', str(desktop)], check=True, capture_output=True)
        desktop.write_text(desktop.read_text().replace('Terminal=true', 'Terminal=false'))
        code = 'from gi.repository import Gio; import sys; app=Gio.DesktopAppInfo.new_from_filename(sys.argv[1]); assert app; assert app.launch([], None)'
        subprocess.run([python, '-c', code, str(desktop)], check=True, capture_output=True, timeout=10)
        import time
        marker = strange / 'launched.txt'
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(0.02)
        self.assertEqual('success', marker.read_text())

    def assert_stopped(self, result):
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertNotIn('SETUP COMPLETE', result.stdout)

    def test_fedora_complete_setup_and_safe_rerun(self):
        self.config['missing'] = ['vlc', 'kdialog', 'kio-fuse']
        result = self.run_setup()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn('SETUP COMPLETE', result.stdout)
        calls = self.commands()
        self.assertIn(['sudo', 'dnf', 'install', '-y', 'vlc', 'kdialog', 'kio-fuse'], calls)
        self.assertTrue(self.rules.exists())
        app_home = self.home / 'data/ignitron-preset-tools'
        working = app_home / 'ignitron firmware/platformio.ini'
        working.write_text('custom hardware settings')
        presets = working.parent / 'data'; presets.mkdir()
        (presets / 'mine.json').write_text('{"kept":true}')
        settings = self.home / 'config/ignitron-preset-tools/settings.json'
        settings.parent.mkdir(parents=True); settings.write_text('{"kept":true}')
        result = self.run_setup()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual('custom hardware settings', working.read_text())
        self.assertEqual('{"kept":true}', settings.read_text())
        self.assertEqual('{"kept":true}', (presets / 'mine.json').read_text())
        downloads = [c[-1] for c in self.commands() if c[0] == 'curl']
        self.assertEqual(1, sum(url.endswith('get-platformio.py') for url in downloads))
        builds = [c for c in self.commands() if c[:2] == ['platformio', 'run']]
        self.assertEqual(4, len(builds))
        self.assertTrue(all(str(app_home) not in c[3] for c in builds))

    def test_debian_arm64_selects_matching_archive_and_venv(self):
        self.os_release.write_text('ID=ubuntu\nID_LIKE=debian\n')
        self.config['arch'] = 'aarch64'
        self.config['missing'] = ['python3-venv', 'vlc']
        new_package = self.package.with_name(self.package.name.replace('x64', 'arm64'))
        self.package.rename(new_package); self.package = new_package
        self.repack()
        self.config['archive_name'] = self.config['archive_name'].replace('x64', 'arm64')
        self.config['sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        result = self.run_setup()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn(['sudo', 'apt-get', 'update'], self.commands())
        self.assertIn(['sudo', 'env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', 'python3-venv', 'vlc'], self.commands())

    def test_check_only_has_no_network_or_installs(self):
        result = self.run_setup('--check')
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertFalse((self.home / 'state').exists())
        self.assertFalse(any(c[0] in ('curl', 'sudo', 'platformio') for c in self.commands()))

    def test_root_unsupported_system_architecture_and_atomic_fail_early(self):
        for change in ('root', 'distro', 'arch', 'atomic'):
            with self.subTest(change=change):
                self.config['uid'] = 0 if change == 'root' else 1000
                self.config['arch'] = 'i686' if change == 'arch' else 'x86_64'
                self.os_release.write_text('ID=arch\n' if change == 'distro' else 'ID=fedora\n')
                if change == 'atomic': (self.root / 'ostree').touch()
                self.assert_stopped(self.run_setup())
        self.assertFalse(any(c[0] in ('curl', 'sudo') for c in self.commands()))

    def test_bad_checksum_stops_before_app_installer_or_usb_changes(self):
        self.config['fail'] = 'checksum'
        self.assert_stopped(self.run_setup())
        self.assertFalse(self.rules.exists())
        self.assertFalse((self.home / 'data').exists())

    def test_failed_package_download_or_password_cannot_report_success(self):
        for failure in ('sudo', 'dnf', 'download'):
            with self.subTest(failure=failure):
                self.config['missing'] = ['vlc']
                self.config['fail'] = failure
                self.assert_stopped(self.run_setup())
                self.assertFalse((self.home / 'data').exists())

    def test_bad_rules_keep_existing_rules(self):
        self.rules.parent.mkdir(); self.rules.write_text('existing')
        self.config['fail'] = 'rules'
        self.assert_stopped(self.run_setup())
        self.assertEqual('existing', self.rules.read_text())

    def test_audio_or_build_failure_never_reports_ready(self):
        for failure in ('audio', 'build', 'buildfs'):
            with self.subTest(failure=failure):
                self.config['fail'] = failure
                self.assert_stopped(self.run_setup())


if __name__ == '__main__':
    unittest.main()

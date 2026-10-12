from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Preformatted, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/ignitron-linux-install-guide.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
fonts=Path('/usr/share/fonts/dejavu-sans-fonts')
if not (fonts/'DejaVuSans.ttf').exists():
    fonts=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/share/fonts/truetype'
for name,file in [('Guide','DejaVuSans.ttf'),('GuideBold','DejaVuSans-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
mono=fonts/'DejaVuSansMono.ttf'
if not mono.exists(): mono=Path('/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf')
pdfmetrics.registerFont(TTFont('GuideMono',str(mono)))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='Guide',boldItalic='GuideBold')
styles={
'body':ParagraphStyle('body',fontName='Guide',fontSize=9.5,leading=13.5,spaceAfter=8,textColor=colors.HexColor('#253345')),
'title':ParagraphStyle('title',fontName='GuideBold',fontSize=23,leading=28,spaceAfter=14,textColor=colors.HexColor('#172638')),
'h':ParagraphStyle('h',fontName='GuideBold',fontSize=12.5,leading=16,spaceBefore=9,spaceAfter=7,textColor=colors.HexColor('#172638')),
'code':ParagraphStyle('code',fontName='GuideMono',fontSize=7.4,leading=10.5,backColor=colors.HexColor('#edf1f5'),borderPadding=8,spaceBefore=4,spaceAfter=12),
'note':ParagraphStyle('note',fontName='Guide',fontSize=9.4,leading=13.5,backColor=colors.HexColor('#fff3d9'),borderPadding=8,spaceBefore=5,spaceAfter=12,textColor=colors.HexColor('#533a0c'))}
story=[]
def p(s):story.append(Paragraph(s,styles['body']))
def h(s):story.append(Paragraph(s,styles['h']))
def note(s):story.append(Paragraph(s,styles['note']))
def code(s):
    for line in s.splitlines():
        assert pdfmetrics.stringWidth(line,'GuideMono',7.4)<512, (len(line),line)
    story.append(Preformatted(s,styles['code']))
def title(n,s):
    if story:story.append(PageBreak())
    p(f'<b>LINUX INSTALLATION / {n:02d}</b>')
    story.append(Paragraph(s,styles['title']))
def link(text,url):return f'<a href="{url}" color="#176d92">{text}</a>'
repo='https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0'

title(1,'Install from one Linux download')
p('<b>Guide revision 0.5 - 12 October 2026.</b> Recommended setup for <b>IPT v2.1.01</b> on Fedora with dnf or Ubuntu/Debian with apt. Atomic/immutable editions and other distributions need a separate setup method.')
note('Keep the pedal unplugged and close IPT. For an existing test PC, back up and reset its profile using page 8 first. Your music stays in its existing local or NAS folder.')
h('A. Download and extract')
p('Open '+link('the v2.1.01 release',repo+'/releases/tag/v2.1.01')+'. Download <b>Linux-x64.tar.gz</b> for a typical Intel/AMD PC, or <b>Linux-arm64.tar.gz</b> for an ARM64 computer. Right-click the download and choose <b>Extract</b>. Open the extracted folder, not the archive viewer. Use the refreshed Linux download containing <b>Install Ignitron.desktop</b>.')
h('B. Double-click Install Ignitron')
p('Open <b>Install Ignitron</b>. If Linux asks, choose <b>Execute</b>, <b>Trust</b> or <b>Allow Launching</b>. Some desktops require right-click > Properties > Permissions > executable first. A terminal setup window opens. Enter your Linux password when asked; characters stay hidden. Run as your normal user, never with sudo before the installer.')
h('C. Wait for SETUP COMPLETE')
p('Setup verifies the included package, installs missing VLC/Python requirements, installs USB rules and PlatformIO Core, installs IPT and its menu entry, checks VLC playback, and builds both firmware and filesystem. KDE users also get Places/NAS helpers. VS Code and Arduino IDE are not required.')
p('Internet is required for dependencies. Initial ESP32 downloads and build checks take several minutes. Setup uses a temporary firmware copy and never flashes or erases the pedal. Existing working projects, presets, captures, backups and settings are preserved.')
note('<b>Checkpoint:</b> wait for <b>SETUP COMPLETE</b>. IPT opens automatically; its menu shortcut is usually under Multimedia. If any stage fails, keep the visible error and log path, fix the reported problem, then rerun Install Ignitron. Logs default to ~/.local/state/ignitron-preset-tools/setup.')
h('D. Continue on page 5')
p('Review OLED, battery and hardware settings before connecting and flashing the pedal. Then test audible backing-track playback and USB features.')
h('If the launcher opens as text')
p('Inside the extracted folder, right-click empty space > <b>Open Terminal Here</b>, then paste:')
code('bash ./launch_linux_setup.sh')
p('<b>Preview only:</b> bash ./setup_linux.sh --check. Pages 2-4 are the manual alternative. START-HERE-Linux.txt repeats these steps. The separate Install-IPT-Linux.sh online download remains available for terminal users.')

title(2,'Manual setup: prerequisites')
p('<b>Manual alternative.</b> If you used the all-in-one installer on page 1 successfully, skip to page 5. The commands on pages 2-4 are for installing each prerequisite and the application separately.')
note('For a manual installation, keep the pedal unplugged until step 10. Run one command block at a time and stop if its checkpoint fails.')
h('1. Check the system')
code('cat /etc/os-release\nuname -m\npython3 --version\ncommand -v curl\ncommand -v vlc')
p('<b>x86_64:</b> choose Linux-x64. <b>aarch64:</b> choose Linux-arm64. The hardware walkthrough uses Fedora KDE x64. Ubuntu/Debian alternatives below and ARM64 packages require their own end-to-end validation.')
h('2. Install the prerequisites')
p('<b>Fedora:</b>')
code('sudo dnf install curl python3 vlc')
p('<b>Ubuntu/Debian:</b>')
code('sudo apt update\nsudo apt install curl python3 python3-venv vlc')
p('If VLC is already installed, the package manager confirms it. Open <b>VLC</b> from the menu, finish its first-run dialog and close it. Use the distribution package: a Flatpak-only VLC installation may not expose libVLC to IPT.')
p('VLC supplies backing-track playback. PlatformIO Core supplies firmware build/upload tools. <b>VS Code and Arduino IDE are not required.</b> IPT includes its own Python/Tk runtime; system Python is used to install PlatformIO. The archive app-only installer does not install these prerequisites; the all-in-one installer on page 1 does.')
p('<b>Checkpoint:</b> the architecture is known, Python/curl work and VLC opens. A sudo password prompt expects your Linux account password; characters are hidden as you type.')

title(3,'Install PlatformIO and USB rules')
h('3. Install PlatformIO Core as your normal user')
code('mkdir -p "$HOME/Downloads"\ncd "$HOME/Downloads"\npio_url="https://raw.githubusercontent.com/platformio"\ncurl -fsSL -o get-platformio.py \\\n  "$pio_url/platformio-core-installer/master/get-platformio.py"\npython3 get-platformio.py\n"$HOME/.platformio/penv/bin/platformio" --version')
p('Do not use sudo for this installer. The final command must print a PlatformIO Core version. The standard executable location is <b>~/.platformio/penv/bin/platformio</b>; IPT checks that location automatically.')
p('On the earlier Fedora/Python 3.14 test, the installer reported a temporary-folder cleanup error after announcing success. If an error appears, retain the output and check the version command. A working version command is the first check; the firmware build later verifies the rest.')
h('4. Install Linux USB permissions')
code('cd "$HOME/Downloads"\nrules_url="https://raw.githubusercontent.com/platformio/platformio-core"\ncurl -fsSL -o 99-platformio-udev.rules \\\n  "$rules_url/develop/platformio/assets/system/99-platformio-udev.rules"\nsudo install -m 644 99-platformio-udev.rules \\\n  /etc/udev/rules.d/99-platformio-udev.rules\nsudo udevadm control --reload-rules\nsudo udevadm trigger')
p('These commands normally finish quietly. The rules apply after unplugging and reconnecting the pedal. Fedora normally includes the CP210x serial driver; do not install random Windows drivers on Linux.')
p('<b>Checkpoint:</b> PlatformIO prints its version and the rule installation completes without errors. Leave the pedal unplugged for now.')
h('Official instructions')
p(link('PlatformIO Core installer','https://docs.platformio.org/en/latest/core/installation/methods/installer-script.html')+'<br/>'+link('PlatformIO Linux USB permissions','https://docs.platformio.org/en/latest/core/installation/udev-rules.html')+'<br/>'+link('Fedora VLC package','https://packages.fedoraproject.org/pkgs/vlc/vlc/'))

title(4,'Download and install the release')
h('5. Download the updated archive and checksums')
p('Open '+link('the v2.1.01 release',repo+'/releases/tag/v2.1.01')+' and confirm the version is <b>v2.1.01</b>. Avoid an earlier saved ZIP or GitHub Actions artifact. The commands below fetch the public release into a new folder.')
code('mkdir -p "$HOME/Downloads"\ncd "$HOME/Downloads"\nipt_download=$(mktemp -d "$PWD/ipt-2.1.01-download.XXXXXX")\ncd "$ipt_download"\nrelease_url="https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0"\nrelease_url="$release_url/releases/download/v2.1.01"\narchive="Ignitron.Preset.Tools.v2.1.01.Linux-x64.tar.gz"\ncurl -fL -o "$archive" "$release_url/$archive"\ncurl -fL -o SHA256SUMS.txt "$release_url/SHA256SUMS.txt"\nsha256sum --ignore-missing -c SHA256SUMS.txt')
p('For ARM64, change <b>Linux-x64</b> to <b>Linux-arm64</b> in the archive assignment and extracted directory below. Keep using this same terminal so the variables remain set.')
note('<b>Checkpoint:</b> the downloaded archive must report OK. If verification fails or checks no file, stop and download both files again. The release uses dots in download filenames; the extracted folder uses spaces.')
h('6. Extract and install without sudo')
code('tar -xzf "$archive"\ncd "Ignitron Preset Tools v2.1.01 Linux-x64"\nsh ./install_linux.sh')
p('Expected: <b>Installed Ignitron Preset Tools for this user.</b> The app appears in the menu, typically under Multimedia. Default location: ~/.local/share/ignitron-preset-tools. The launcher is ~/.local/bin/ignitron-preset-tools. A custom XDG_DATA_HOME changes the data location.')
h('7. Check VLC, then launch IPT')
code('"$HOME/.local/bin/ignitron-preset-tools" --vlc-self-test\n"$HOME/.local/bin/ignitron-preset-tools" --vlc-audio-self-test')
p('Both tests must pass. The second uses the real audio backend with a silent WAV; you will verify audible playback on page 6. Open <b>Ignitron Preset Tools</b> from the application menu. If the menu entry is missing, run the launcher path above without a self-test argument.')

title(5,'Configure and flash the pedal')
h('8. Review the firmware project and hardware')
p('Dashboard should use <b>~/.local/share/ignitron-preset-tools/ignitron firmware</b>. The separate <b>Ignitron 1.9.0</b> folder is the older fallback. Under <b>Firmware &gt; Show setup</b>, confirm PlatformIO, environment <b>esp32dev</b> and upload speed <b>460800</b>. If PlatformIO is missing, browse to ~/.platformio/penv/bin/platformio.')
p('Match the OLED driver, battery type/cells, GPIO and other settings to your own pedal. The supplied default is SH1106 1.3-inch. Our earlier test used SSD1309 2.42-inch and two-cell Li-ion, which is not a universal default. Editing the firmware version label alone does not add firmware features.')
h('9. Validate the preset data')
p('Uncheck <b>Allow filesystem upload when PresetList.txt references missing JSON files</b>, then click <b>Validate data</b>. Continue only when validation succeeds. For a new pedal, the supplied library is a starting point. For an existing pedal, back up valuable presets before replacing its filesystem.')
h('10. Connect USB directly')
p('Use a data-capable USB cable directly to the PC for the first test. Confirm the USB detection prompt and choose the matching port, commonly <b>/dev/ttyUSB0 | CP2102</b>. A bad hub caused intermittent detection during our earlier test. Close any other serial monitor.')
code('"$HOME/.platformio/penv/bin/platformio" device list')
p('<b>Checkpoint:</b> the port appears in both PlatformIO and IPT. If it does not, use the troubleshooting checks on page 7 before flashing.')
h('11. Build and flash through IPT')
p('End any Remote or Capture connection. Leave <b>Erase flash before upload</b> unchecked unless you intentionally need a full erase. Click <b>Build + Flash FW + FS</b>. It saves the displayed settings, downloads missing ESP32 tools/libraries, and builds firmware and filesystem before any requested erase. It then uploads both.')
note('Internet is required for the first build. Downloading dependencies here is normal; a separate terminal build is not required. A filesystem upload replaces the pedal data with the selected project data. Wait until the entire firmware and filesystem sequence reports success.')
p('<b>Checkpoint:</b> the pedal restarts with the expected screen, version and controls, and connects to the Spark amp. Keep the full build log if any stage fails; a successful firmware stage alone is not a successful combined update.')

title(6,'Check the features one at a time')
h('12. Backing Tracks: test a local folder first')
p('Open <b>Backing Tracks</b>. Choose a local folder containing a known audio file. Test play, pause, seek, stop and volume while stopped and while playing. Try search and favorites. Close and reopen IPT and confirm the folder and favorites are remembered. This feature does not require the pedal or a NAS.')
h('13. Optional NAS music on KDE')
p('In Dolphin, open your SMB share and authenticate there first. Add the backing-track folder to Dolphin Places if desired. In IPT use <b>Choose folder</b> for the KDE Places sidebar, or paste your <b>smb://server/share/folder/</b> address into Music Folder and press Enter. Credentials stay with KDE, not in IPT settings.')
p('If the native chooser or SMB bridge is missing on Fedora KDE, install <b>kdialog</b> and <b>kio-fuse</b> with dnf. Other desktops can use an existing mounted local directory. Permission denied for an old mount is a storage-access issue: verify the same location in the file manager. Do not run IPT as root or put a password in the URL.')
h('14. Pedal Remote')
p('Connect the pedal to your Spark amp, choose its USB port and click <b>Connect remote</b>. Confirm the detected amp model and current preset. Click several presets and confirm the amp changes. Only the selected preset should be orange; hovering another preset should not select it. Test applicable hardware slots and tuner, then click <b>End connection</b>.')
h('15. Spark Capture and backups')
p('Click <b>Start capture</b>. IPT requests a temporary reboot into AMP mode. Wait for the connected/listening state. Connect the phone Spark app to Ignitron in Capture mode, using the pedal Bluetooth mode required by your phone. Select a few ToneCloud presets and check for <b>SAVED:</b> entries. Confirm the JSON files under the project captures folder.')
p('Names that collide receive numbered filenames; identical repeats are skipped. End connection and confirm the pedal returns to normal APP mode. <b>Pull listed presets</b> backs up every file named in the pedal PresetList, not just the four presets in the current bank. <b>Pull full library</b> backs up all stored preset JSON. Both write under the project backups folder.')
h('16. Preset Builder')
p('Load a preset library, arrange a small bank and export to a separate test output folder. Inspect the JSON files, lists and generated PDF. Exporting does not change the pedal until you explicitly upload the filesystem. Keep custom presets and capture backups before reorganizing a library.')

title(7,'If a checkpoint fails')
h('Installation or playback')
p('<b>install_linux.sh not found:</b> change into the extracted package folder, then run sh ./install_linux.sh.<br/><b>Missing PlatformIO:</b> run its full-path version check from page 3, restart IPT, and select the executable in Firmware setup.<br/><b>Missing VLC:</b> install the native VLC package from page 2 and restart IPT. If VLC opens but IPT playback fails, retain both self-test outputs and test a local WAV file.')
h('USB or capture')
code('"$HOME/.platformio/penv/bin/platformio" device list\nls -l /dev/ttyUSB0\nid -nG\nfuser -v /dev/ttyUSB0')
p('Replace ttyUSB0 with the reported port. <b>No port:</b> try a direct USB port and another data cable. <b>Permission denied:</b> reinstall/reload the udev rules and reconnect. If using a serial-access group instead, identify the actual device group and sign out/in after adding membership. <b>Busy:</b> close the named process or serial monitor normally. Do not run IPT as root.')
p('<b>Capture waits without saving:</b> the phone must connect to the pedal in AMP mode and select a preset. Heartbeat responses alone do not contain a preset. <b>Pedal restarted during connection:</b> Capture requests one intentional restart; repeated resets or loss of the USB device need investigation. End connection before retrying.')
h('Optional build diagnostics: no upload')
code('cd "$HOME/.local/share/ignitron-preset-tools/ignitron firmware"\n"$HOME/.platformio/penv/bin/platformio" run -e esp32dev\n"$HOME/.platformio/penv/bin/platformio" run -e esp32dev -t buildfs')
p('Both should end in SUCCESS. These are optional diagnostics; the combined IPT button already runs both builds. Do not run them concurrently with another firmware task.')
h('Keep useful evidence')
code('"$HOME/.local/bin/ignitron-preset-tools" 2>&1 | tee "$HOME/ipt-test.log"')
p('Record the failing guide step, action, expected result, actual result and exact error. Include OS/architecture, release SHA256 and amp model. For a native crash, <b>coredumpctl info</b> can identify the fault. Check logs/screenshots for private paths or credentials before posting.')
p('Fixes and issues can be handled entirely from this Linux PC through '+link('the GitHub project',repo)+'. The original development PC is not required. Test the published package as well as source code before marking a problem resolved.')

title(8,'Repeat with a clean app profile')
p('<b>For an existing test PC only.</b> This is a recoverable reset of the IPT profile and PlatformIO installation. It does not reinstall Linux or remove global packages. For a strictly new-OS test, use a clean Linux installation with USB access instead.')
h('A. Back up before changing anything')
p('End all IPT connections, close IPT and unplug the pedal. Copy any custom firmware projects or music stored outside the default IPT folder separately. Keep the saved paths/checksum record from this test. The commands below assume default XDG locations; inspect custom XDG variables before proceeding.')
code('printf "Data: %s\\nConfig: %s\\n" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME"\nbackup="$HOME/Documents/IPT-clean-retest-$(date +%Y%m%d-%H%M%S)"\nmkdir -p "$backup"\ndata_home="${XDG_DATA_HOME:-$HOME/.local/share}"\nconfig_home="${XDG_CONFIG_HOME:-$HOME/.config}"\nif [ -d "$data_home/ignitron-preset-tools" ]; then\n  cp -a "$data_home/ignitron-preset-tools" "$backup/app-data"\nfi\nif [ -d "$config_home/ignitron-preset-tools" ]; then\n  cp -a "$config_home/ignitron-preset-tools" "$backup/settings"\nfi\nprintf "Backup: %s\\n" "$backup"')
p('<b>Checkpoint:</b> open that backup in the file manager and verify your firmware/data, captures, backups and settings are present where expected. Stop if the copy fails. Keep the terminal open for the next block.')
h('B. Move the old profiles aside')
code('if [ -d "$data_home/ignitron-preset-tools" ]; then\n  mv "$data_home/ignitron-preset-tools" "$backup/original-app-data"\nfi\nif [ -d "$config_home/ignitron-preset-tools" ]; then\n  mv "$config_home/ignitron-preset-tools" "$backup/original-settings"\nfi\nif [ -d "$HOME/.platformio" ]; then\n  mv "$HOME/.platformio" "$backup/original-platformio"\nfi')
p('The old launcher/menu entry temporarily points to a moved app; the new installer replaces it. Other PlatformIO projects also lose access to that moved toolchain until installation or restoration. Do not restore settings until the clean test finishes.')
p('To include the <b>missing VLC and missing USB-rules</b> cases, do a separate reviewed removal of those system prerequisites, or use a clean OS. Do not remove shared packages blindly. Then start at page 1. This guide does not use the old destructive uninstaller.')

title(9,'Record the result and recover')
h('Clean-install checklist')
for text in [
'1. OS, architecture and release archive SHA256 recorded.',
'2. Python/curl and native VLC installed or found; VLC opens.',
'3. PlatformIO and USB rules complete; all-in-one setup reports SETUP COMPLETE.',
'4. Release checksum passes; installer and application-menu launch work.',
'5. Both packaged VLC self-tests pass; local audio is audible.',
'6. Correct hardware settings and data validation confirmed.',
'7. Firmware and filesystem uploads succeed after reviewing hardware settings.',
'8. Remote connects, identifies the amp and changes presets without hover selection.',
'9. Capture saves phone presets; ending Capture returns the pedal to APP mode.',
'10. Listed/full-library backups contain readable JSON and report completion.',
'11. Builder export and optional NAS/favorites work; restart retains settings.'
]:p('[  ] '+text)
h('Upgrade and uninstall behavior in v2.1.01')
p('Installing again updates the application and bundled templates while preserving working firmware projects, presets, captures and backups. The new uninstaller removes the app but retains working data and settings. Its <b>--purge</b> option deliberately deletes working data as well, so it is not the preferred clean-test procedure. Old extracted installers/uninstallers may still be destructive; use the v2.1.01 package.')
h('Recovery after the clean test')
p('Close IPT. Keep the newly tested data/profile under a different backup name, then restore the original-app-data and original-settings folders from page 8 to their previous locations. Restore original-platformio only if you need the previous toolchain/cache. Never merge folders over one another without reviewing conflicts. This is not needed for a successful first installation.')
h('Validation scope')
p('Earlier Fedora 44 x64 testing confirmed flashing, real backing-track playback, NAS library access, Remote operations and phone preset capture. The v2.1.01 release also has automated regressions and native CI packaging. Hardware-specific features such as Spark 2 looper/battery telemetry require the corresponding amp. A passing software test cannot certify every Linux distribution, USB adapter or pedal.')
p('Record pass/fail against this exact revised guide. Keep any failures open until the downloaded release passes the same action on this PC. Update the guide when the steps or behavior change.')
p(link('Release and checksums',repo+'/releases/tag/v2.1.01')+' | '+link('Report or review issues',repo+'/issues'))

def footer(c,doc):
    c.setStrokeColor(colors.HexColor('#e2e7ec'));c.line(42,40,570,40)
    c.setFont('Guide',8);c.setFillColor(colors.HexColor('#637083'))
    c.drawString(42,27,'IGNITRON PRESET TOOLS  |  Guide 0.5  |  12 Oct 2026')
    c.drawRightString(570,27,str(doc.page))
doc=SimpleDocTemplate(str(OUT),pagesize=(612,792),rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=54,title='Ignitron Preset Tools - Linux Installation Guide',author='Ignitron Preset Tools')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
shutil.copy2(OUT,ROOT/'Linux-Install-Guide.pdf')
print(OUT)

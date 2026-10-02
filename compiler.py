"""Build SixthSense into an executable with PyInstaller.

It builds into dist/SixthSense-Windows, dist/SixthSense-Linux or dist/SixthSense-macOS
for the current system, and nothing else: it never zips and never changes the
repository.  Setting the version, filing the changelog, zipping, tagging and uploading a release are
releaser.py's work, and the releaser calls this to do the building.

Double-click this file, or run py compiler.py with nothing after it, and it offers a numbered menu of
builds, then waits for Enter at the end so you can hear how it went.  Each choice is one of these flags,
which still work typed out:

    py compiler.py                the folder build: the game's data beside the executable
    py compiler.py --embed        one executable with the sounds and the game's data inside it
    py compiler.py --clean        empty PyInstaller's cache first
    py compiler.py --console      keep a console window, to see why the game will not start
    py compiler.py --onefile      one executable with the game's data still beside it
    py compiler.py --no-game      leave the game's data out
    py compiler.py --dry-run      say what a build would do, build nothing

Every build lands in dist\\SixthSense-Windows, around SixthSense.exe, with the text a player reads beside the executable - the readme,
the changelog and the todo list in a docks\\ folder, as in the repository, and VERSION and the license at
the top.  Those are never put inside it.  The third-party licenses go inside the executable, as
licenses\\, whichever kind of build (since 2026-09-25).  That folder is what releaser.py zips into
dist\\SixthSense-Win-<VERSION>.zip.

The port and the vendored DLLs always go inside the build.  In the folder build the game's own files do
not: the plists and the three map layers are copied next to the executable, into game\\, and the sounds
into game\\sounds\\used and game\\sounds\\unused with their folders, which is where sixthsense/paths.py
looks for them when frozen, used first.  With --embed the same files go inside the executable instead,
and paths.py finds them in the folder it unpacks itself to; that costs a few seconds at every launch.
Nothing else in the original app bundle is copied: the game never opens any of it.

There is no --test yet.  A test build would start the game and read its log; SixthSense does not write a
log, or a crash.txt, so there is nothing for a test run to read.  A windowed build that fails says
why aloud, in one line; build with --console to see the whole traceback.

macOS builds are self-contained .app bundles for the build Python's architecture; --console keeps
the console-folder format for debugging.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.machinery
import importlib.metadata
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
#: The executable's name, before the system's own ending: SixthSense.exe on Windows, SixthSense on Linux.
NAME = 'SixthSense'
ENTRY = 'SixthSense.py'

#: What differs between the systems a build can be made on (tunmi13productions, 2026-09-28;
#: aidocks/project_linux_build_plan.md).  PyInstaller only builds for the system it runs on, so a Windows
#: build is made on Windows and a Linux one on Linux, in WSL or not.  Each system has:
#:     folder     what the build folder is called after SixthSense-, and so the one a release extracts to
#:     exe        the executable's file name
#:     zip        what releaser.py calls the system in the archive's name: SixthSense-Win-<version>.zip
#:     archive    what releaser.py packs the build into: a zip for Windows, which opens one with nothing
#:                installed; a gzipped tar for Linux, which every Linux can open, keeping the executable
#:                bit and symbolic links (tunmi13productions, 2026-09-28)
#:     binaries   the vendored libraries that go inside the build, and the folder each goes to there
#:     licenses   their licenses, which sit beside them in vendor/: the folder each goes to under licenses/
#:                inside the executable, and the files.  Prism's and pygame's are not kept here - they come
#:                out of the installed packages when the build runs (license_files()), so they always match
#:                what was bundled.
#: The NVDA controller client is a Windows DLL, so the Linux build leaves it out; Prism speaks there.
_OPENAL_LICENSES = ('openal-soft', ('vendor/openal/license.txt', 'vendor/openal/license-pffft.txt'))
SYSTEMS = {
    'win32': dict(folder='Windows', exe=NAME + '.exe', zip='Win', archive='zip',
                  binaries=(('vendor/openal/soft_oal.dll', 'vendor/openal'),      # the audio engine itself
                            ('vendor/nvda/nvdaControllerClient64.dll', 'vendor/nvda')),
                  licenses=(_OPENAL_LICENSES,
                            ('nvda-controller-client', ('vendor/nvda/license.txt',)))),
    'linux': dict(folder='Linux', exe=NAME, zip='Linux', archive='tar.gz',
                  binaries=(('vendor/openal/libopenal.so.1', 'vendor/openal'),),
                  licenses=(_OPENAL_LICENSES,)),
    # Native-architecture app.
    'darwin': dict(folder='macOS', exe=NAME, zip='macOS-' + platform.machine(), archive='tar.gz',
                   binaries=(('vendor/openal/libopenal.1.dylib', 'vendor/openal'),),
                   licenses=(('openal-soft', _OPENAL_LICENSES[1] +
                              ('vendor/openal/license-fmt.txt', 'vendor/openal/license-gsl.txt')),)),
}


def system_key(platform: str = sys.platform) -> str | None:
    """The SYSTEMS entry for ``platform`` - sys.platform is 'linux' on every Linux, WSL included - or None
    for a system with no build."""
    if platform in ('win32', 'darwin'):
        return platform
    return 'linux' if platform.startswith('linux') else None


#: The table for the system this runs on; Windows' where there is no build, so the names below still read
#: sensibly while problems_now() says why nothing can be built.
SYSTEM = SYSTEMS[system_key() or 'win32']
#: The folder a build lands in, and the one a release's zip extracts to (tsatria03, 2026-09-25).
FOLDER = NAME + '-' + SYSTEM['folder']

#: what the game cannot run without: the module, and what pip calls it.  pygame, not pygame-ce - the two
#: cannot be installed side by side, and the port is written against pygame.  prismatoid is Prism, which
#: platform/speech.py speaks through for every screen reader but NVDA, and for the SAPI voice.  The game
#: starts without it, but then only an NVDA player hears the key-bindings screen, so no build leaves it out.
PLAY_PACKAGES = (('pygame', 'pygame'), ('prism', 'prismatoid'))
BINARIES = SYSTEM['binaries']
VENDOR_LICENSES = SYSTEM['licenses']
#: What the game reads from its bundle's top folder: the binary plists (the sound list, the monster tables,
#: the weapon tables) and the three map layers.  The rest of the app - the iOS executable and its code
#: signature, the nibs, the images, the Facebook SDK - is never opened, and has no business in a release.
#: The sounds are in folders of their own, which sound_files() copies; *.wav stays here so that an
#: untouched original bundle, whose WAVs are all in its top folder, still builds.
GAME_FILES = ('*.wav', '*.plist', 'g_CH1_E', 'a_CH1_E.txt', 's_CH1_E.txt')
#: copied beside the executable rather than bundled inside it, so the player can open them: what it is
#: called here, and what it is called there.  They are never embedded, --embed or not.  LICENSE has no
#: extension, which is the convention on GitHub but means Windows asks what to open it with, so it ships
#: as a .txt.  The todo list holds only what a player notices, which is why it can ship.  The documents a
#: player reads live in docks\ in the repository, and go into a docks\ folder beside the executable, as
#: they are laid out here; VERSION and the license stay at the top.
DOCKS = 'docks'
CHANGELOG = os.path.join(DOCKS, 'changelog.txt')
#: The player's readme is plain text of its own, not README.md, which is for developers and would be
#: read aloud with every # and | in it.
SIDE_FILES = ((os.path.join(DOCKS, 'readme.txt'), os.path.join(DOCKS, 'readme.txt')),
              (CHANGELOG, CHANGELOG),
              (os.path.join(DOCKS, 'todo list.txt'), os.path.join(DOCKS, 'todo list.txt')),
              ('VERSION', 'VERSION'),
              ('LICENSE', 'license.txt'))


def say(text: str = '') -> None:
    print(text, flush=True)


def build_version() -> str:
    """What this build calls itself: the one line in VERSION, or '' when there is no such file."""
    try:
        with open(os.path.join(HERE, 'VERSION'), encoding='utf-8') as fh:
            return fh.read().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ''


# --- the changelog -----------------------------------------------------------------------------------
# docks\changelog.txt collects what has changed under one heading, "unrelease:", at the top.
# releaser.py files those lines under the version being released before it calls this to build; the
# compiler only reads the changelog, and takes an empty unrelease: heading out of the copy it ships.  The
# parsing lives here, where both use it.

#: The heading the changelog collects unreleased changes under: the whole line, colon and all.
UNRELEASE = 'unrelease:'
#: A heading is one word ending in a colon - "unrelease:", "26.09.20:".  The entries are sentences, so a
#: line with a space in it, colons and all, is never taken for one.
_HEADING = re.compile(r'^[^\s:]+:$')


def changelog_heading(version: str) -> str:
    """'26.09.21-1' -> '26.09.21-1:'.  The heading is VERSION exactly as written, build number and all."""
    return version + ':'


def _parse_changelog(text: str) -> list:
    """[[heading, [lines]], ...] in the order of the file.  Blank lines only separate one version from
    the next, so they are not kept; anything above the first heading is a block with no heading."""
    blocks = []
    for line in text.replace('\r\n', '\n').split('\n'):
        if _HEADING.match(line.strip()):
            blocks.append([line.strip(), []])
        elif line.strip():
            if not blocks:
                blocks.append([None, []])
            blocks[-1][1].append(line)
    return blocks


def _render_changelog(blocks: list) -> str:
    """A heading, its lines, then one blank line before the next heading, all the way down - so where
    one version's changes end is something you hear, not something you have to work out."""
    return '\n\n'.join('\n'.join(([heading] if heading else []) + lines) for heading, lines in blocks) + '\n'


def unreleased_lines(text: str) -> list:
    """The lines under unrelease:, the changes no release has carried yet."""
    return next((lines for heading, lines in _parse_changelog(text) if heading == UNRELEASE), [])


def without_unrelease(text: str) -> str:
    """The changelog a player reads: the same, less the empty unrelease: heading, so it opens on the
    newest version.  A heading that still has lines under it is left alone rather than lose them."""
    return _render_changelog([b for b in _parse_changelog(text) if not (b[0] == UNRELEASE and not b[1])])


def strip_shipped_changelog(dest_root: str) -> None:
    """Take the empty unrelease: heading out of the copy in the build's docks\\ - the copy only.  A build
    made straight after the releaser has filed the changelog opens on the new version."""
    path = os.path.join(dest_root, CHANGELOG)
    if os.path.isfile(path):
        text = open(path, encoding='utf-8').read()
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(without_unrelease(text))


def release_warnings(changelog: str) -> list:
    """What would make this a bad thing to publish, judged on the changelog the build actually carries."""
    found = []
    if not build_version():
        found.append('there is no VERSION file, so the release has no version to be tagged with, and '
                     'the zip has none in its name')
    try:
        with open(changelog, encoding='utf-8') as fh:
            first = fh.readline().strip()
        if first == UNRELEASE:
            found.append('the changelog in this build still opens with "%s", because only releaser.py '
                         'files the changelog; release with it to put those lines under the version'
                         % UNRELEASE)
    except OSError:
        found.append('there is no changelog.txt, so the release notes would be empty')
    return found


def problems_now() -> list[str]:
    """Everything that would stop the build, in plain words."""
    found = []
    if system_key() is None:
        found.append('this builds on Windows, Linux or macOS, and this is %s' % sys.platform)
    if sys.maxsize <= 2 ** 32:
        found.append('use 64-bit Python: the vendored libraries are 64-bit')
    if importlib.util.find_spec('PyInstaller') is None:
        found.append('PyInstaller is not installed in this Python: pip install pyinstaller')
    absent = [pip for mod, pip in PLAY_PACKAGES if importlib.util.find_spec(mod) is None]
    if absent:
        found.append("the game's own packages have to be installed here too, to be bundled: "
                     'pip install ' + ' '.join(absent))
    for src, _ in BINARIES:
        if not os.path.isfile(os.path.join(HERE, src.replace('/', os.sep))):
            found.append('%s is missing - it ships with the repository' % src)
    return found


def prism_native_modules() -> list[str]:
    """Prism's compiled Python module in its prism\\_native folder, which --collect-all leaves behind: a .pyd
    on Windows, a .so on Linux, whatever this Python names its compiled modules."""
    spec = importlib.util.find_spec('prism')
    if spec is None or not spec.submodule_search_locations:
        return []
    folder = os.path.join(list(spec.submodule_search_locations)[0], '_native')
    if not os.path.isdir(folder):
        return []
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    return sorted(os.path.join(folder, name) for name in os.listdir(folder) if name.endswith(suffixes))


#: Where --embed gathers the game's top-folder files - the plists and the map layers - so PyInstaller can
#: take them as one folder.  Adding them one by one would run past Windows' limit on a command line.
EMBED_STAGE = os.path.join(HERE, 'build', 'embed', 'game')
#: Where every build gathers the third-party licenses, which go inside the executable as licenses\
#: (tsatria03, 2026-09-25); only the port's own license.txt stays beside it.
LICENSES_STAGE = os.path.join(HERE, 'build', 'embed', 'licenses')
APP_DOCS_STAGE = os.path.join(HERE, 'build', 'embed', 'app-docs')


def app_bundle(args) -> bool:
    return system_key() == 'darwin' and not args.console


def embedded_data(src: str) -> list[tuple[str, str]]:
    """What --embed puts inside the executable, as PyInstaller's (source, folder inside) pairs: the staged
    top-folder files as game\\, and the sounds as game\\sounds\\used and game\\sounds\\unused, whole.
    paths.py finds them all in the folder the executable unpacks itself to, as it would find them beside a
    folder build.  An original, flat bundle has neither sounds folder; its WAVs are in the top folder, and
    so in the stage."""
    from sixthsense.paths import SOUND_FOLDERS
    data = [(EMBED_STAGE, 'game')]
    for folder in SOUND_FOLDERS:
        sounds = os.path.join(src, folder)
        if os.path.isdir(sounds):
            data.append((sounds, 'game/' + folder.replace(os.sep, '/')))
    return data


def stage_embedded(src: str) -> list[str]:
    """Copy the top-folder files --embed carries into EMBED_STAGE, fresh, and return their names."""
    if os.path.isdir(EMBED_STAGE):
        shutil.rmtree(EMBED_STAGE)
    os.makedirs(EMBED_STAGE)
    names = game_files(src)
    for name in names:
        shutil.copy2(os.path.join(src, name), os.path.join(EMBED_STAGE, name))
    return names


def command(args, data=()) -> list[str]:
    """The PyInstaller command line.  ``data`` is what --embed adds inside the executable."""
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--noupx', '--name', NAME]
    if system_key() == 'darwin':
        cmd += ['--target-arch', platform.machine()]
    for src, dest in BINARIES:
        cmd += ['--add-binary', src + os.pathsep + dest]
    # Prism is imported only once NVDA is found not to be running, so it is named outright rather than left
    # for the analysis to find.  It loads its compiled half from a folder of its own, prism\_native:
    # --collect-all brings the DLL there but not the Python module beside it, because the folder is not a
    # package, so that is added by name - and it needs cffi's own compiled module, which nothing names either
    cmd += ['--collect-all', 'prism', '--hidden-import', '_cffi_backend']
    for src in prism_native_modules():
        cmd += ['--add-binary', src + os.pathsep + 'prism/_native']
    if not args.console:
        # no console window beside the game's own.  A failure is said aloud in one line;
        # --console shows the whole traceback
        cmd += ['--windowed']
    if app_bundle(args):
        cmd += ['--osx-bundle-identifier', 'org.sixthsense.port',
                '--add-data', APP_DOCS_STAGE + os.pathsep + '.']
    # An onedir .app is one copyable item in Finder without unpacking at launch.
    if (args.onefile or args.embed) and not app_bundle(args):
        # one file lands in dist\SixthSense-Windows too, so every build is one folder to zip and nothing
        # else in dist\ - an older zip, say - is swept into it
        cmd += ['--onefile', '--distpath', output_dir(args)]
    for src, inside in data:
        cmd += ['--add-data', src + os.pathsep + inside]
    # the third-party licenses go inside, whichever kind of build (stage_licenses fills the folder)
    cmd += ['--add-data', LICENSES_STAGE + os.pathsep + 'licenses']
    if args.clean:
        cmd += ['--clean']
    return cmd + [ENTRY]


def output_dir(args=None) -> str:
    """Where the executable lands, and so where everything beside it goes: dist\\SixthSense-Windows,
    whichever kind of build."""
    return os.path.join(HERE, 'dist', FOLDER)


def pyinstaller_dir() -> str:
    """Where a folder build's PyInstaller puts it, named after the executable: dist\\SixthSense.  It is
    moved to output_dir() once built, since PyInstaller names that folder and the executable alike."""
    return os.path.join(HERE, 'dist', NAME)


def clear_output(dest_root: str) -> None:
    """Empty dist\\SixthSense-Windows before a build, and dist\\SixthSense, where a folder build first
    lands and where builds went before 2026-09-25.  A one-file build only writes its executable, and would
    leave an older build's files around it."""
    folders = [dest_root, pyinstaller_dir()]
    if system_key() == 'darwin':
        folders.append(pyinstaller_dir() + '.app')
    for folder in folders:
        if os.path.isdir(folder):
            shutil.rmtree(folder)


def move_folder_build(dest_root: str) -> None:
    """A folder build is made in dist\\SixthSense; move it to dist\\SixthSense-Windows."""
    built = pyinstaller_dir()
    if os.path.normcase(built) != os.path.normcase(dest_root) and os.path.isdir(built):
        os.replace(built, dest_root)


def move_app_build(dest_root: str) -> str:
    """Move PyInstaller's finished app without changing its contents or signature."""
    os.makedirs(dest_root, exist_ok=True)
    target = os.path.join(dest_root, NAME + '.app')
    os.replace(pyinstaller_dir() + '.app', target)
    return target


def game_files(src: str) -> list[str]:
    """The names in the bundle's top folder that the game reads - GAME_FILES, matched without regard to
    case, as Windows matches file names."""
    return sorted(name for name in os.listdir(src)
                  if os.path.isfile(os.path.join(src, name))
                  and any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in GAME_FILES))


def sound_files(src: str) -> list[str]:
    """Every file under the bundle's sounds\\used and sounds\\unused folders, as a path inside the bundle,
    so each one keeps its folder.  paths.py looks in unused for a name used does not have, so both go.  An
    original, flat bundle has neither folder, and its WAVs come in with game_files() instead."""
    from sixthsense.paths import SOUND_FOLDERS
    found = []
    for folder in SOUND_FOLDERS:
        for dirpath, dirs, files in os.walk(os.path.join(src, folder)):
            dirs.sort()
            found += [os.path.relpath(os.path.join(dirpath, name), src) for name in sorted(files)]
    return found


#: What data_summary() counts as a sound: the WAVs, and the one blooper clip in sounds\\unused.
SOUND_EXTENSIONS = ('.wav', '.ogg')


def data_summary(names: list[str]) -> str:
    """What a list of the game's files holds, in words: '507 files - 362 sounds, and 145 plists and map
    layers'."""
    sounds = sum(1 for name in names if name.lower().endswith(SOUND_EXTENSIONS))
    return '%d files - %d sounds, and %d plists and map layers' % (len(names), sounds, len(names) - sounds)


def copy_game(dest_root: str) -> bool:
    from sixthsense import paths
    try:
        src = paths.game()                  # --game, SIXTHSENSE_GAME, then game\ - as the game looks
    except SystemExit as missing:           # paths.game() ends the program when there is no bundle
        say("  the game's data was not found, so nothing was copied.  %s" % missing)
        say('  the build will need --game PATH, or a game folder put beside the executable.')
        return False
    dest = os.path.join(dest_root, 'game')
    say("copying the game's data from %s into %s ..." % (src, dest))
    started = time.perf_counter()
    names = game_files(src) + sound_files(src)
    for name in names:
        target = os.path.join(dest, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(src, name), target)
    say('  %s, in %.0f seconds.' % (data_summary(names), time.perf_counter() - started))
    return True


def copy_side_files(dest_root: str) -> None:
    """The text the player reads, next to the game rather than inside it: docks\\ as a folder, and
    VERSION and the license at the top."""
    for name, shipped_as in SIDE_FILES:
        src = os.path.join(HERE, name)
        if not os.path.isfile(src):
            say('  %s is not here, so it was not copied.' % name)
            continue
        target = os.path.join(dest_root, shipped_as)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        say('%s is in the build%s.'
            % (shipped_as, '' if shipped_as == name else ', from %s' % name))


def license_files() -> list[tuple[str, str]]:
    """Every third-party license a release carries: (where it goes under licenses\\, where it comes from).

    The two vendored DLLs' licenses sit beside them in vendor\\.  Prism's come out of its installed
    package's dist-info - its own license, its NOTICE, and the LICENSES folder that NOTICE points to, for
    the libraries Prism itself is built from - and pygame's LGPL out of pygame's installed package, so a
    build always carries the licenses of exactly what it bundled.  A file with no extension gets .txt, so
    Windows opens it rather than asking what to open it with."""
    found = []
    for folder, sources in VENDOR_LICENSES:
        for src in sources:
            found.append((os.path.join(folder, os.path.basename(src)),
                          os.path.join(HERE, src.replace('/', os.sep))))
    try:
        dist = importlib.metadata.distribution('prismatoid')
        for entry in dist.files or ():
            parts = entry.parts
            if len(parts) > 2 and parts[0].endswith('.dist-info') and parts[1] == 'licenses':
                rel = os.path.join('prism', *parts[2:])
                if not os.path.splitext(rel)[1]:
                    rel += '.txt'
                found.append((rel, str(dist.locate_file(entry))))
    except importlib.metadata.PackageNotFoundError:
        found.append((os.path.join('prism', 'LICENSE.txt'), ''))      # reported as missing
    spec = importlib.util.find_spec('pygame')
    folder = list(spec.submodule_search_locations)[0] if spec and spec.submodule_search_locations else ''
    found.append((os.path.join('pygame', 'LGPL.txt'),
                  os.path.join(folder, 'docs', 'generated', 'LGPL.txt') if folder else ''))
    return found


def licensed_names() -> str:
    """Whose licenses this system's build carries, in words."""
    vendored = [{'openal-soft': 'OpenAL Soft', 'nvda-controller-client': 'the NVDA controller client'}
                .get(folder, folder) for folder, _files in VENDOR_LICENSES]
    return ', '.join(vendored + ['Prism']) + ' and pygame'


def stage_licenses(dest: str = None) -> int:
    """The third-party licenses, gathered fresh into LICENSES_STAGE for PyInstaller to put inside the
    executable as licenses\\ (since 2026-09-25; before, they sat beside it).  Returns how many."""
    dest = dest or LICENSES_STAGE
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    copied = 0
    for rel, src in license_files():
        if not src or not os.path.isfile(src):
            say('  the license %s was not found, so it was not copied.' % rel)
            continue
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    say('%d license files - %s - go inside the executable, as licenses%s.'
        % (copied, licensed_names(), os.sep))
    return copied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='compiler.py', description='build SixthSense with PyInstaller')
    parser.add_argument('--embed', action='store_true',
                        help="one executable with the sounds and the game's data inside it; the text a "
                             'player reads stays beside it')
    parser.add_argument('--onefile', action='store_true',
                        help="one executable, with the game's data still beside it")
    parser.add_argument('--no-game', action='store_true',
                        help="leave the game's data out")
    parser.add_argument('--console', action='store_true',
                        help='keep a console window, where a failed start-up prints its traceback')
    parser.add_argument('--clean', action='store_true', help="throw away PyInstaller's cache first")
    parser.add_argument('--dry-run', action='store_true', help='print what would be done, build nothing')
    args = parser.parse_args(argv)
    os.chdir(HERE)                                      # the paths above are relative to the project

    found = problems_now()
    if found:
        say('this would stop the build:' if args.dry_run else 'the build cannot start:')
        for problem in found:
            say('  ' + problem)
        if not args.dry_run:
            return 2
        say()

    dest_root = output_dir(args)
    bundle = app_bundle(args)
    if bundle and (args.onefile or args.embed):
        say('macOS app bundles use onedir; --console enables the single-executable options.')
    src = None
    if not args.no_game:
        from sixthsense import paths
        try:
            src = paths.game()          # --game, SIXTHSENSE_GAME, then game\ - as the game looks
        except SystemExit:              # paths.game() ends the program when there is no bundle
            src = None
    if args.embed and src is None:
        say("--embed puts the game's data inside the executable, and the game's data was not found.")
        if not args.dry_run:
            return 2

    data_inside = args.embed or bundle
    data = embedded_data(src) if data_inside and src else []
    cmd = command(args, data)
    say('running: python ' + ' '.join(cmd[1:]))
    if args.dry_run:
        if args.no_game:
            say("the game's data would be left out.")
        elif src is None:
            say("the game's data was not found, so none would be copied.")
        elif data_inside:
            say("the game's data would go inside the executable, from %s: %s, and nothing else from the "
                'app bundle' % (src, data_summary(game_files(src) + sound_files(src))))
        else:
            say("the game's data would then be copied from %s into %s: %s, and nothing else from the "
                'app bundle'
                % (src, os.path.join(dest_root, 'game'), data_summary(game_files(src) + sound_files(src))))
        for name, shipped_as in SIDE_FILES:
            say('%s would be copied into the build%s%s'
                % (name, '' if shipped_as == name else ', as %s' % shipped_as,
                   '' if os.path.isfile(os.path.join(HERE, name)) else ' - but it is not here'))
        licenses = license_files()
        absent = [rel for rel, lic in licenses if not lic or not os.path.isfile(lic)]
        say('%d license files - %s - would go inside the executable, as licenses%s'
            % (len(licenses) - len(absent), licensed_names(), os.sep))
        for rel in absent:
            say('  but the license %s is not here' % rel)
        for warning in release_warnings(os.path.join(HERE, CHANGELOG)):
            say('before releasing: ' + warning)
        return 0

    if data_inside and src:
        names = stage_embedded(src)
        say("the game's data goes inside the executable: %s."
            % data_summary(names + sound_files(src)))
    stage_licenses()
    if bundle:
        if os.path.isdir(APP_DOCS_STAGE):
            shutil.rmtree(APP_DOCS_STAGE)
        os.makedirs(APP_DOCS_STAGE)
        copy_side_files(APP_DOCS_STAGE)
        strip_shipped_changelog(APP_DOCS_STAGE)
    clear_output(dest_root)
    started = time.perf_counter()
    if subprocess.run(cmd).returncode != 0:
        say("PyInstaller failed - its own output above says why.")
        return 1
    say('built in %.0f seconds.' % (time.perf_counter() - started))
    if bundle:
        try:
            app_path = move_app_build(dest_root)
        except OSError as error:
            say('the app could not be finalized: %s' % error)
            return 1
        say('the game is %s; copy this app on its own.' % app_path)
        return 0
    if not (args.onefile or args.embed):
        move_folder_build(dest_root)

    if src is not None and not args.embed:
        copy_game(dest_root)
    copy_side_files(dest_root)
    strip_shipped_changelog(dest_root)

    for warning in release_warnings(os.path.join(dest_root, CHANGELOG)):
        say('before releasing: ' + warning)

    exe = os.path.join(dest_root, SYSTEM['exe'])
    say()
    say('the game is %s' % exe)
    say("the folder around it is what releaser.py zips, and the game's own files in it are Bitbee's.")
    return 0


# --- the menu ----------------------------------------------------------------------------------------
# Double-click compiler.py, or run it with nothing after it, and it asks rather than expects you to know
# the flags.  Each choice is exactly one of the command lines below, so the two can never disagree; the
# flags still work as they always have for anyone typing them.

MENU = (
    ("Folder build: the game in a folder, with its data beside the executable", []),
    ("Single exe: the sounds and the game's data inside one executable", ['--embed']),
    ("Clean build: empty PyInstaller's cache first, for when a build behaves oddly", ['--clean']),
    ("Build with a console window, to see why the game will not start", ['--console']),
    ("One-file build: a single executable, with the game's data still beside it", ['--onefile']),
    ("Build without the game's data", ['--no-game']),
    ('Show what a build would do, without building anything', ['--dry-run']),
)
if system_key() == 'darwin':
    MENU = (
        ('App build: a self-contained SixthSense.app to copy and open in Finder', []),
        ('Clean app build: empty PyInstaller caches first', ['--clean']),
        ('Console folder build for debugging', ['--console']),
        ('Console single executable with game data inside', ['--console', '--embed']),
        ("App build without the game's data", ['--no-game']),
        ('Show what an app build would do without building', ['--dry-run']),
    )


def menu() -> list | None:
    """Ask which build.  Returns the flags for it, or None to quit."""
    version = build_version()
    say('SixthSense compiler.  VERSION is %s.'
        % (version or 'missing - releaser.py sets it as it releases'))
    say()
    for number, (text, _flags) in enumerate(MENU, 1):
        say('  %d. %s' % (number, text))
    say('  0. Quit')
    say()
    while True:
        try:
            choice = input('Type a number and press Enter: ').strip()
        except EOFError:
            return None
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            text, flags = MENU[int(choice) - 1]
            say('%s.' % text.split(':')[0])
            say()
            return list(flags)
        say('There is no choice "%s". Type a number from 0 to %d.' % (choice, len(MENU)))


def run(argv=None) -> int:
    """Flags on the command line build straight away, as they always have.  No flags with a keyboard at
    the other end - a double-click in Explorer, or py compiler.py typed on its own - opens the menu, and
    the window waits at the end so what happened can be heard before it closes.  With no keyboard at
    all, no flags is still the release build it always was."""
    argv = sys.argv[1:] if argv is None else argv
    if argv or not sys.stdin.isatty():
        return main(argv)
    chosen = menu()
    if chosen is None:
        return 0
    try:
        return main(chosen)
    finally:
        say()
        try:
            input('Finished. Press Enter to close this window.')
        except EOFError:
            pass


if __name__ == '__main__':
    sys.exit(run())

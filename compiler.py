"""Build SixthSense into an executable with PyInstaller.

It builds the game into dist\\SixthSense, and nothing else: it never zips and never changes the
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

Every build lands in dist\\SixthSense, with the text a player reads beside the executable - the readme,
the changelog and the todo list from docks\\, VERSION and the license - and the third-party licenses in
licenses\\.
Those are never put inside it.  That folder is what releaser.py zips into dist\\SixthSense-Win-<VERSION>.zip.

The port and the vendored DLLs always go inside the build.  In the folder build the game's own files do
not: the plists and the three map layers are copied next to the executable, into game\\, and the sounds
into game\\sounds\\used with their folders, which is where sixthsense/paths.py looks for them when frozen.
With --embed the same files go inside the executable instead, and paths.py finds them in the folder it
unpacks itself to; that costs a few seconds at every launch, since it unpacks about 126 MB.  Nothing else
in the original app bundle is copied, and neither is game\\sounds\\unused: the game never opens any of it.

There is no --test yet.  A test build would start the game and read its log; SixthSense does not write a
log, or a crash.txt, so there is nothing for a test run to read.  A windowed build that fails says
why aloud, in one line; build with --console to see the whole traceback.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = 'SixthSense'
ENTRY = 'SixthSense.py'

#: what the game cannot run without: the module, and what pip calls it.  pygame, not pygame-ce - the two
#: cannot be installed side by side, and the port is written against pygame.  prismatoid is Prism, which
#: platform/speech.py speaks through for every screen reader but NVDA, and for the SAPI voice.  The game
#: starts without it, but then only an NVDA player hears the key-bindings screen, so no build leaves it out.
PLAY_PACKAGES = (('pygame', 'pygame'), ('prism', 'prismatoid'))
BINARIES = (('vendor/openal/soft_oal.dll', 'vendor/openal'),    # the audio engine itself
            ('vendor/nvda/nvdaControllerClient64.dll', 'vendor/nvda'))
#: The licenses of the two DLLs in vendor\, which sit beside them: the folder each goes to under licenses\
#: in a build, and the files.  Prism's and pygame's are not kept here - they come out of the installed
#: packages when the build runs (license_files()), so they always match what was bundled.
VENDOR_LICENSES = (('openal-soft', ('vendor/openal/license.txt', 'vendor/openal/license-pffft.txt')),
                   ('nvda-controller-client', ('vendor/nvda/license.txt',)))
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
#: player reads live in docks\ in the repository, and land at the top of the build, beside the executable.
DOCKS = 'docks'
CHANGELOG = os.path.join(DOCKS, 'changelog.txt')
#: The player's readme is plain text of its own, not README.md, which is for developers and would be
#: read aloud with every # and | in it.
SIDE_FILES = ((os.path.join(DOCKS, 'readme.txt'), 'readme.txt'),
              (CHANGELOG, 'changelog.txt'),
              (os.path.join(DOCKS, 'todo list.txt'), 'todo list.txt'),
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
    """Take the empty unrelease: heading out of the copy beside the executable - the copy only.  A build
    made straight after the releaser has filed the changelog opens on the new version."""
    path = os.path.join(dest_root, 'changelog.txt')
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
    if sys.platform != 'win32':
        found.append('this builds a Windows executable, so it has to run on Windows')
    if sys.maxsize <= 2 ** 32:
        found.append('use 64-bit Python: the vendored OpenAL Soft and NVDA DLLs are 64-bit')
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
    """Prism's compiled Python module in its prism\\_native folder, which --collect-all leaves behind."""
    spec = importlib.util.find_spec('prism')
    if spec is None or not spec.submodule_search_locations:
        return []
    folder = os.path.join(list(spec.submodule_search_locations)[0], '_native')
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, name) for name in os.listdir(folder) if name.endswith('.pyd'))


#: Where --embed gathers the game's top-folder files - the plists and the map layers - so PyInstaller can
#: take them as one folder.  Adding them one by one would run past Windows' limit on a command line.
EMBED_STAGE = os.path.join(HERE, 'build', 'embed', 'game')


def embedded_data(src: str) -> list[tuple[str, str]]:
    """What --embed puts inside the executable, as PyInstaller's (source, folder inside) pairs: the staged
    top-folder files as game\\, and the sounds as game\\sounds\\used, whole.  paths.py finds both in the
    folder the executable unpacks itself to, as it would find them beside a folder build.  An original,
    flat bundle has no sounds\\used folder; its WAVs are in the top folder, and so in the stage."""
    from sixthsense.paths import SOUNDS_USED
    data = [(EMBED_STAGE, 'game')]
    sounds = os.path.join(src, SOUNDS_USED)
    if os.path.isdir(sounds):
        data.append((sounds, 'game/' + SOUNDS_USED.replace(os.sep, '/')))
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
    if args.onefile or args.embed:
        # one file lands in dist\SixthSense too, so every build is one folder to zip and nothing else in
        # dist\ - an older zip, say - is swept into it
        cmd += ['--onefile', '--distpath', output_dir(args)]
    for src, inside in data:
        cmd += ['--add-data', src + os.pathsep + inside]
    if args.clean:
        cmd += ['--clean']
    return cmd + [ENTRY]


def output_dir(args=None) -> str:
    """Where the executable lands, and so where everything beside it goes: dist\\SixthSense, whichever
    kind of build."""
    return os.path.join(HERE, 'dist', NAME)


def clear_output(dest_root: str) -> None:
    """Empty dist\\SixthSense before a build.  A folder build's PyInstaller does this itself, but a
    one-file build only writes its executable, and would leave an older build's files around it."""
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)


def game_files(src: str) -> list[str]:
    """The names in the bundle's top folder that the game reads - GAME_FILES, matched without regard to
    case, as Windows matches file names."""
    return sorted(name for name in os.listdir(src)
                  if os.path.isfile(os.path.join(src, name))
                  and any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in GAME_FILES))


def sound_files(src: str) -> list[str]:
    """Every file under the bundle's sounds\\used folder, as a path inside the bundle, so each one keeps
    its folder.  sounds\\unused stays out: nothing in the game opens it.  An original, flat bundle has no
    such folder, and its WAVs come in with game_files() instead."""
    from sixthsense.paths import SOUNDS_USED
    found = []
    for dirpath, dirs, files in os.walk(os.path.join(src, SOUNDS_USED)):
        dirs.sort()
        found += [os.path.relpath(os.path.join(dirpath, name), src) for name in sorted(files)]
    return found


def data_summary(names: list[str]) -> str:
    """What a list of the game's files holds, in words: '454 files - 309 sounds, and 145 plists and map
    layers'."""
    sounds = sum(1 for name in names if name.lower().endswith('.wav'))
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
    """The text the player reads, next to the game rather than inside it."""
    for name, shipped_as in SIDE_FILES:
        src = os.path.join(HERE, name)
        if not os.path.isfile(src):
            say('  %s is not here, so it was not copied.' % name)
            continue
        shutil.copy2(src, os.path.join(dest_root, shipped_as))
        say('%s is beside the executable%s.'
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


def copy_licenses(dest_root: str) -> None:
    """The third-party licenses, into licenses\\ beside the executable."""
    dest = os.path.join(dest_root, 'licenses')
    copied = 0
    for rel, src in license_files():
        if not src or not os.path.isfile(src):
            say('  the license %s was not found, so it was not copied.' % rel)
            continue
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        copied += 1
    say('%d license files - OpenAL Soft, the NVDA controller client, Prism and pygame - are in %s.'
        % (copied, dest))


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

    data = embedded_data(src) if args.embed and src else []
    cmd = command(args, data)
    say('running: python ' + ' '.join(cmd[1:]))
    if args.dry_run:
        if args.no_game:
            say("the game's data would be left out.")
        elif src is None:
            say("the game's data was not found, so none would be copied.")
        elif args.embed:
            say("the game's data would go inside the executable, from %s: %s, and nothing else from the "
                'app bundle' % (src, data_summary(game_files(src) + sound_files(src))))
        else:
            say("the game's data would then be copied from %s into %s: %s, and nothing else from the "
                'app bundle'
                % (src, os.path.join(dest_root, 'game'), data_summary(game_files(src) + sound_files(src))))
        for name, shipped_as in SIDE_FILES:
            say('%s would be copied beside the executable%s%s'
                % (name, '' if shipped_as == name else ', as %s' % shipped_as,
                   '' if os.path.isfile(os.path.join(HERE, name)) else ' - but it is not here'))
        licenses = license_files()
        absent = [rel for rel, lic in licenses if not lic or not os.path.isfile(lic)]
        say('%d license files - OpenAL Soft, the NVDA controller client, Prism and pygame - would go into '
            'licenses%s beside the executable' % (len(licenses) - len(absent), os.sep))
        for rel in absent:
            say('  but the license %s is not here' % rel)
        for warning in release_warnings(os.path.join(HERE, CHANGELOG)):
            say('before releasing: ' + warning)
        return 0

    if args.embed:
        names = stage_embedded(src)
        say("the game's data goes inside the executable: %s."
            % data_summary(names + sound_files(src)))
    clear_output(dest_root)
    started = time.perf_counter()
    if subprocess.run(cmd).returncode != 0:
        say("PyInstaller failed - its own output above says why.")
        return 1
    say('built in %.0f seconds.' % (time.perf_counter() - started))

    if src is not None and not args.embed:
        copy_game(dest_root)
    copy_side_files(dest_root)
    copy_licenses(dest_root)
    strip_shipped_changelog(dest_root)

    for warning in release_warnings(os.path.join(dest_root, 'changelog.txt')):
        say('before releasing: ' + warning)

    exe = os.path.join(dest_root, NAME + '.exe')
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

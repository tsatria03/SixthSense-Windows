"""Build SixthSense into an executable with PyInstaller.

Double-click this file, or run py compiler.py with nothing after it, and it offers a numbered menu of
builds, then waits for Enter at the end so you can hear how it went.  Its first choice is the release
build.  Every other choice is one of these flags, which still work typed out:

    py compiler.py --no-package   the folder alone, without the release zip
    py compiler.py --clean        empty PyInstaller's cache first
    py compiler.py --console      keep a console window, to see why the game will not start
    py compiler.py --onefile      a single executable instead (unpacks itself at every launch)
    py compiler.py --no-game      leave the game's data out
    py compiler.py --dry-run      say what a build would do, build nothing

A build makes one folder, dist\\SixthSense, with the game's data copied in and the third-party licenses in
licenses\\ beside the executable, and ends by zipping it into dist\\SixthSense-Win-<VERSION>.zip, which is
what a release's asset is.

The release build - no flags at all - also files the changelog first: the lines under "unrelease:" go
under this version's heading in the repository's changelog.txt, and the copy beside the executable opens
on that version.  It ends by saying what it changed, for you to commit.  Run with no flags and no
keyboard (from a script), it is the release build straight away, without the menu.

The port and the vendored DLLs go inside the build; the game's own files do not - the plists and the
three map layers are copied next to the executable, into game\\, and the sounds into game\\sounds\\used
with their folders, which is where sixthsense/paths.py looks for them when frozen.  Nothing else in the
original app bundle is copied, and neither is game\\sounds\\unused: the game never opens any of it.

There is no --test yet.  A test build would start the game and read its log; SixthSense does not write a
log, or a crash.txt, so there is nothing for a test run to read.  Until it does, a windowed build
that fails to start says nothing - build with --console to hear why.
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
import zipfile

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
#: called here, and what it is called there.  LICENSE has no extension, which is the convention on GitHub
#: but means Windows asks what to open it with, so it ships as a .txt.
SIDE_FILES = (('changelog.txt', 'changelog.txt'),
              ('VERSION', 'VERSION'),
              ('LICENSE', 'license.txt'))
# A release could also carry readme.html beside the executable, built from README.md by a Markdown
# converter, since a screen reader reads every # and | of a .md file aloud.  SixthSense's README is a
# two-line stub and there is no converter here yet; add both once there is a real README.


def say(text: str = '') -> None:
    print(text, flush=True)


def build_version() -> str:
    """What this build calls itself: the one line in VERSION, or '' when there is no such file."""
    try:
        with open(os.path.join(HERE, 'VERSION'), encoding='utf-8') as fh:
            return fh.read().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ''


#: How often packaging says how far it has got: after each quarter of the files.
PACK_STEPS = 4


def package(dest_root: str) -> str:
    """Zip the built folder into the archive a release is made of.

    A zip rather than a rar because Windows opens a zip by itself, with nothing installed - and an
    updater, should SixthSense ever get one, can read a zip with Python's own zipfile.  Everything
    sits under one folder inside the archive, so extracting it gives a player a folder rather than a heap
    of files in their Downloads.

    Packaging takes a while, and a zip can only be opened once its last few bytes are written, so it
    says that it has started, how far it has got, and when it is done.  It is written under a .part name
    and renamed only once it is whole: close the window halfway and no zip is left behind that looks
    finished but will not open.
    """
    version = build_version()
    name = '%s-Win-%s' % (NAME, version) if version else '%s-Win' % NAME
    archive = os.path.join(HERE, 'dist', name + '.zip')
    partial = archive + '.part'
    for old in (archive, partial):
        if os.path.isfile(old):
            os.remove(old)
    files = []
    for dirpath, dirs, names in os.walk(dest_root):
        dirs.sort()
        files += [os.path.join(dirpath, filename) for filename in sorted(names)]
    say()
    say('packaging the release: zipping %d files into %s.' % (len(files), os.path.basename(archive)))
    say('this can take a minute - leave this window open until it says the zip is done.')
    started = time.perf_counter()
    # a line after each quarter, so a long silence never looks like the end
    marks = {len(files) * step // PACK_STEPS for step in range(1, PACK_STEPS)}
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for count, full in enumerate(files, 1):
            inside = os.path.join(NAME, os.path.relpath(full, dest_root))
            zf.write(full, inside.replace(os.sep, '/'))
            if count in marks:
                say('  %d of %d files packed ...' % (count, len(files)))
    os.replace(partial, archive)
    say('the zip is done: %d files, %.0f MB, in %.0f seconds.'
        % (len(files), os.path.getsize(archive) / (1 << 20), time.perf_counter() - started))
    say('upload this as the release asset, and tag the release %s.' % (version or 'with its version'))
    return archive


# --- the changelog -----------------------------------------------------------------------------------
# changelog.txt collects what has changed under one heading, "unrelease:", at the top.  A plain build -
# py compiler.py with no flags at all - files those lines under the version being built, in the
# repository's changelog, and ships a copy that opens on that version instead.  Any flag leaves the
# changelog exactly as it is: a build with a flag is a build for trying something, not a release.

#: The heading the changelog collects unreleased changes under: the whole line, colon and all.
UNRELEASE = 'unrelease:'
#: A heading is one word ending in a colon - "unrelease:", "26.09.20:".  The entries are sentences, so a
#: line with a space in it, colons and all, is never taken for one.
_HEADING = re.compile(r'^[^\s:]+:$')


def first_version() -> str:
    """What VERSION starts at when a plain build finds there is none: today's first release, '26.09.21-1'
    on the 21st of September 2026 - the same shape as the VERSION the repository already has."""
    return time.strftime('%y.%m.%d') + '-1'


def changelog_heading(version: str) -> str:
    """'26.09.21-1' -> '26.09.21-1:'.  The heading is VERSION exactly as written, build number and all.
    Nothing here works a version out: build again without changing VERSION and the new lines join the
    same entry; change the number in VERSION and the next release build starts a new one."""
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


def plan_changelog(text: str, version: str):
    """What a plain build does to the repository's changelog: (text, changed, what it did).

    The lines under unrelease: move to this version's entry - a new one just below unrelease:, or the
    bottom of the one already there when this is a second build of the same day - and unrelease: stays
    at the top, empty, for whatever changes next.  With nothing under it the text comes back as it was.
    If the unrelease: line has been deleted, it is put back."""
    blocks = _parse_changelog(text)
    notes = []
    at = next((i for i, (heading, _lines) in enumerate(blocks) if heading == UNRELEASE), None)
    if at is None:
        blocks.insert(0, [UNRELEASE, []])
        at = 0
        notes.append('there was no "%s" line, so one was put back at the top' % UNRELEASE)
    moving, heading = blocks[at][1], changelog_heading(version)
    if moving:
        blocks[at][1] = []
        entry = next((block for block in blocks if block[0] == heading), None)
        if entry is not None:
            entry[1].extend(moving)
            notes.append('%d line(s) from "%s" went to the bottom of %s' % (len(moving), UNRELEASE, heading))
        else:
            blocks.insert(at + 1, [heading, moving])
            notes.append('%d line(s) from "%s" became the new entry %s' % (len(moving), UNRELEASE, heading))
    else:
        notes.append('nothing is under "%s", so no entry was added' % UNRELEASE)
    changed = bool(moving) or len(notes) > 1
    return (_render_changelog(blocks) if changed else text), changed, notes


def without_unrelease(text: str) -> str:
    """The changelog a player reads: the same, less the empty unrelease: heading, so it opens on the
    newest version.  A heading that still has lines under it is left alone rather than lose them."""
    return _render_changelog([b for b in _parse_changelog(text) if not (b[0] == UNRELEASE and not b[1])])


def prepare_release_files() -> list:
    """A plain build's work on the repository, done before anything is copied: VERSION started if there
    is none, and the changelog's unreleased lines filed under this version.  Returns the files it
    changed, so the build can say at the end that they want committing."""
    changed = []
    if not build_version():
        start_at = first_version()
        with open(os.path.join(HERE, 'VERSION'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(start_at + '\n')
        say('VERSION did not exist, so it has been started at %s.' % start_at)
        changed.append('VERSION')
    path = os.path.join(HERE, 'changelog.txt')
    text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''
    new, did, notes = plan_changelog(text, build_version())
    for note in notes:
        say('changelog: %s' % note)                 # no full stop: most notes end on a heading's colon
    if did:
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(new)
        changed.append('changelog.txt')
    return changed


def strip_shipped_changelog(dest_root: str) -> None:
    """Take the empty unrelease: heading out of the copy beside the executable - the copy only."""
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
            found.append('the changelog in this build still opens with "%s", because only the release '
                         'build files the changelog; choose it, number 1, from the menu to put those lines '
                         'under the version' % UNRELEASE)
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


def command(args) -> list[str]:
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
        # no console window beside the game's own.  SixthSense does not write crash.txt yet, so a windowed
        # build that fails to start says nothing: --console is how to hear why
        cmd += ['--windowed']
    if args.onefile:
        cmd += ['--onefile']
    if args.clean:
        cmd += ['--clean']
    return cmd + [ENTRY]


def output_dir(args) -> str:
    """Where the executable lands, and so where the game's data goes beside it."""
    return os.path.join(HERE, 'dist') if args.onefile else os.path.join(HERE, 'dist', NAME)


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
    """What a list of the game's files holds, in words: '474 files - 329 sounds, and 145 plists and map
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
    parser.add_argument('--onefile', action='store_true',
                        help='one executable instead of one folder (unpacks itself at every launch)')
    parser.add_argument('--no-game', action='store_true',
                        help="do not copy the game's data next to the executable")
    parser.add_argument('--console', action='store_true',
                        help='keep a console window, where a failed start-up prints its traceback')
    parser.add_argument('--clean', action='store_true', help="throw away PyInstaller's cache first")
    parser.add_argument('--no-package', action='store_true',
                        help='do not zip the folder afterwards; a build makes the release archive by default')
    parser.add_argument('--dry-run', action='store_true', help='print what would be done, build nothing')
    args = parser.parse_args(argv)
    os.chdir(HERE)                                      # the paths above are relative to the project
    # a plain build is a release: only then is the changelog filed under the version
    flagged = any((args.onefile, args.no_game, args.console, args.clean, args.no_package))
    plain = not flagged and not args.dry_run

    found = problems_now()
    if found:
        say('this would stop the build:' if args.dry_run else 'the build cannot start:')
        for problem in found:
            say('  ' + problem)
        if not args.dry_run:
            return 2
        say()

    cmd = command(args)
    say('running: python ' + ' '.join(cmd[1:]))
    if args.dry_run:
        if args.no_game:
            say("the game's data would not be copied.")
        else:
            from sixthsense import paths
            try:
                src = paths.game()
                say("the game's data would then be copied from %s into %s: %s, and nothing else from the "
                    'app bundle'
                    % (src, os.path.join(output_dir(args), 'game'),
                       data_summary(game_files(src) + sound_files(src))))
            except SystemExit:
                say("the game's data was not found, so none would be copied.")
        for name, shipped_as in SIDE_FILES:
            say('%s would be copied beside the executable%s%s'
                % (name, '' if shipped_as == name else ', as %s' % shipped_as,
                   '' if os.path.isfile(os.path.join(HERE, name)) else ' - but it is not here'))
        licenses = license_files()
        absent = [rel for rel, src in licenses if not src or not os.path.isfile(src)]
        say('%d license files - OpenAL Soft, the NVDA controller client, Prism and pygame - would go into '
            'licenses%s beside the executable' % (len(licenses) - len(absent), os.sep))
        for rel in absent:
            say('  but the license %s is not here' % rel)
        if flagged:
            say('the changelog would be copied as it is, because a build with a flag leaves it alone.')
        else:                                           # what the same command without --dry-run would do
            version = build_version() or first_version()
            if not build_version():
                say('VERSION does not exist, so it would be started at %s.' % version)
            path = os.path.join(HERE, 'changelog.txt')
            text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''
            _new, did, notes = plan_changelog(text, version)
            say('without --dry-run, the changelog in the repository would be %s:'
                % ('changed' if did else 'left alone'))
            for note in notes:
                say('  %s' % note)
            say("and the build's copy would open on %s, without the %s line."
                % (changelog_heading(version), UNRELEASE))
        zip_version = build_version() or (first_version() if not flagged else '<no VERSION file>')
        if args.no_package:
            say('it would not be zipped, because of --no-package.')
        else:
            say('it would then be packed into dist%s%s-Win-%s.zip' % (os.sep, NAME, zip_version))
        if flagged:
            for warning in release_warnings(os.path.join(HERE, 'changelog.txt')):
                say('before releasing: ' + warning)
        return 0

    started = time.perf_counter()
    if subprocess.run(cmd).returncode != 0:
        say("PyInstaller failed - its own output above says why.")
        return 1
    say('built in %.0f seconds.' % (time.perf_counter() - started))

    dest_root = output_dir(args)
    if not args.no_game:
        copy_game(dest_root)
    # only once PyInstaller has succeeded: a failed build must not leave the repository changed
    changed = prepare_release_files() if plain else []
    copy_side_files(dest_root)
    copy_licenses(dest_root)
    if plain:
        strip_shipped_changelog(dest_root)

    if not args.no_package:
        for warning in release_warnings(os.path.join(dest_root, 'changelog.txt')):
            say('before releasing: ' + warning)
        package(dest_root)

    exe = os.path.join(dest_root, NAME + '.exe')
    say()
    say('the game is %s' % exe)
    say("the folder around it is what you hand over, and the game's own files in it are Bitbee's.")
    if changed:
        say()
        say('%s changed in the repository: commit %s before you tag the release.'
            % (' and '.join(changed), 'them' if len(changed) > 1 else 'it'))
    return 0


# --- the menu ----------------------------------------------------------------------------------------
# Double-click compiler.py, or run it with nothing after it, and it asks rather than expects you to know
# the flags.  Each choice is exactly one of the command lines below, so the two can never disagree; the
# flags still work as they always have for anyone typing them.

MENU = (
    ('Release build: file the changelog under the version, build, and zip', []),
    ('Build without the zip', ['--no-package']),
    ("Clean build: empty PyInstaller's cache first, for when a build behaves oddly", ['--clean']),
    ("Build with a console window, to see why the game will not start", ['--console']),
    ('One-file build: a single executable instead of a folder', ['--onefile']),
    ("Build without the game's data", ['--no-game']),
    ('Show what a release build would do, without building anything', ['--dry-run']),
)


def menu() -> list | None:
    """Ask which build.  Returns the flags for it, or None to quit."""
    version = build_version()
    say('SixthSense compiler.  VERSION is %s.'
        % (version or 'missing - a release build will start it at %s' % first_version()))
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

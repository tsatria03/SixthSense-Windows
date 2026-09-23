"""Release SixthSense: set the version, file the changelog, build, commit, tag and upload.

Double-click this file, or run py releaser.py, and it offers a numbered menu: the whole release, or any one
step of it.  Every step says what it is about to do and asks Y or N first, and it waits for Enter at the
end so you can hear how it went.  compiler.py does the building; this does everything around it,
the zip included.

The steps, in the order a full release takes them:

    1. check      everything is committed and pushed, the GitHub CLI is here and signed in, and the
                  changelog has changes waiting under "unrelease:" - no more than 100 of them
    2. prepare    VERSION becomes today's date and that day's release number, 26.09.23-1 for the first
                  release on the 23rd of September 2026, -2 for the second, counted from the tags; and the
                  lines under "unrelease:" are filed under that version in changelog.txt
    3. build      compiler.py builds it into dist\\SixthSense: the folder build, or the single executable
                  with the sounds and the game's data inside.  If the build fails, VERSION and the
                  changelog go back to how they were
    4. zip        dist\\SixthSense becomes dist\\SixthSense-Win-<version>.zip - only a build made for this
                  version, so an older build can never go out under the new name
    5. commit     VERSION and changelog.txt are committed as "Release <version>" and pushed
    6. tag        the commit is tagged V<version>, and the tag is pushed
    7. upload     the zip goes up to GitHub as the release "SixthSense V<version>", with that version's
                  changelog lines as its notes

A step you answer N to is skipped, and the ones after it still ask; each checks for itself that what it
needs is there.  Nothing here ever moves or deletes a tag or a release that already exists.
"""
from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import compiler                                                      # noqa: E402
from compiler import (NAME, UNRELEASE, _parse_changelog, _render_changelog,   # noqa: E402
                      changelog_heading, unreleased_lines)

#: What a release's title and tag are made of: "SixthSense V26.09.23-1", tag "V26.09.23-1".
TITLE_PREFIX = NAME + ' V'
TAG_PREFIX = 'V'

#: A release carries at most this many changelog entries.  Fewer is fine; more is not.
MAX_ENTRIES = 100

#: Where the GitHub CLI is looked for when it is not on the PATH.
GH_FALLBACK = r'C:\Program Files\GitHub CLI\gh.exe'
#: The dev's shared tools file, which may name gh.
TOOLS_INI = os.path.join(os.path.expanduser('~'), '.game_tools', 'tools.ini')

VERSION_FILE = os.path.join(HERE, 'VERSION')
CHANGELOG = os.path.join(HERE, 'changelog.txt')


def say(text: str = '') -> None:
    print(text, flush=True)


def ask(question: str) -> bool:
    """A Y or N question.  Anything but Y is no, and so is no keyboard at all."""
    try:
        return input('%s (Y/N): ' % question).strip().upper() == 'Y'
    except EOFError:
        return False


# --- the version ------------------------------------------------------------------------------------

def today_stamp(now=None) -> str:
    """'26.09.23' on the 23rd of September 2026: two-digit year, month and day."""
    return time.strftime('%y.%m.%d', time.localtime(now))


def next_version(tags, stamp: str) -> str:
    """Today's version: the stamp and the number of today's release, one past the highest release
    number already tagged for that day, or 1.  Tags for other days, and tags of any other shape, are
    ignored."""
    pattern = re.compile(r'^%s%s-(\d+)$' % (re.escape(TAG_PREFIX), re.escape(stamp)))
    numbers = [int(m.group(1)) for m in (pattern.match(t.strip()) for t in tags) if m]
    return '%s-%d' % (stamp, max(numbers, default=0) + 1)


def tag_for(version: str) -> str:
    return TAG_PREFIX + version


def title_for(version: str) -> str:
    return TITLE_PREFIX + version


def read_version() -> str:
    return compiler.build_version()


# --- the changelog ----------------------------------------------------------------------------------

def plan_changelog(text: str, version: str):
    """The changelog with its unreleased lines filed under ``version``: (text, changed, what it did).

    The lines under unrelease: move to this version's entry - a new one just below unrelease:, or the
    bottom of one already there - and unrelease: stays at the top, empty, for whatever changes next.
    With nothing under it the text comes back as it was.  If the unrelease: line has been deleted, it is
    put back."""
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


def release_notes(text: str, version: str) -> str:
    """The lines filed under ``version``, one per line: what the release page on GitHub says."""
    heading = changelog_heading(version)
    lines = next((lines for h, lines in _parse_changelog(text) if h == heading), [])
    return '\n'.join(line.strip() for line in lines)


def read_changelog() -> str:
    if not os.path.isfile(CHANGELOG):
        return ''
    with open(CHANGELOG, encoding='utf-8') as fh:
        return fh.read()


def write_text(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


# --- the zip ----------------------------------------------------------------------------------------

#: What the compiler builds, and so what gets zipped.
BUILD_DIR = os.path.join(HERE, 'dist', NAME)

#: How often packaging says how far it has got: after each quarter of the files.
PACK_STEPS = 4


def zip_path(version: str) -> str:
    """Where package() writes the zip for ``version``."""
    return os.path.join(HERE, 'dist', '%s-Win-%s.zip' % (NAME, version))


def built_version(build_dir: str = None) -> str:
    """The version the build in dist\\SixthSense carries, from the VERSION beside its executable, or ''
    when there is no build."""
    path = os.path.join(build_dir or BUILD_DIR, 'VERSION')
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read().strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ''


def package(build_dir: str, version: str) -> str:
    """Zip the built folder into the archive a release is made of.

    A zip rather than a rar or a 7z because Windows opens a zip by itself, with nothing installed.
    Everything sits under one folder inside the archive, so extracting it gives a player a folder rather
    than a heap of files in their Downloads.

    Packaging takes a while, and a zip can only be opened once its last few bytes are written, so it
    says that it has started, how far it has got, and when it is done.  It is written under a .part name
    and renamed only once it is whole: close the window halfway and no zip is left behind that looks
    finished but will not open.
    """
    archive = zip_path(version)
    partial = archive + '.part'
    for old in (archive, partial):
        if os.path.isfile(old):
            os.remove(old)
    files = []
    for dirpath, dirs, names in os.walk(build_dir):
        dirs.sort()
        files += [os.path.join(dirpath, filename) for filename in sorted(names)]
    say('zipping %d files into %s.' % (len(files), os.path.basename(archive)))
    say('this can take a minute - leave this window open until it says the zip is done.')
    started = time.perf_counter()
    # a line after each quarter, so a long silence never looks like the end
    marks = {len(files) * step // PACK_STEPS for step in range(1, PACK_STEPS)}
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for count, full in enumerate(files, 1):
            inside = os.path.join(NAME, os.path.relpath(full, build_dir))
            zf.write(full, inside.replace(os.sep, '/'))
            if count in marks:
                say('  %d of %d files packed ...' % (count, len(files)))
    os.replace(partial, archive)
    say('the zip is done: %d files, %.0f MB, in %.0f seconds.'
        % (len(files), os.path.getsize(archive) / (1 << 20), time.perf_counter() - started))
    return archive


def find_zip(version: str):
    """The zip built for ``version``, or None when there is none."""
    path = zip_path(version)
    return path if os.path.isfile(path) else None


# --- running things ---------------------------------------------------------------------------------

def git(*args, capture=True):
    """Run git in the repository.  Returns (ok, output)."""
    proc = subprocess.run(['git'] + list(args), cwd=HERE, capture_output=capture, text=True)
    out = (proc.stdout or '').strip() if capture else ''
    if capture and proc.returncode != 0 and proc.stderr:
        out = (out + '\n' + proc.stderr.strip()).strip()
    return proc.returncode == 0, out


def gh_path():
    """The GitHub CLI: on the PATH, named in the shared tools.ini, or where its installer puts it."""
    found = shutil.which('gh')
    if found:
        return found
    ini = configparser.ConfigParser()
    try:
        ini.read(TOOLS_INI)
        named = ini.get('tools', 'gh', fallback='')
    except configparser.Error:
        named = ''
    for candidate in (named, GH_FALLBACK):
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def gh(*args, capture=True):
    """Run the GitHub CLI in the repository.  Returns (ok, output)."""
    exe = gh_path()
    if exe is None:
        return False, 'the GitHub CLI was not found'
    proc = subprocess.run([exe] + list(args), cwd=HERE, capture_output=capture, text=True)
    out = ((proc.stdout or '') + (proc.stderr or '')).strip() if capture else ''
    return proc.returncode == 0, out


def all_tags() -> list:
    """Every tag, here and on GitHub, so a release made from another machine still counts."""
    tags = set()
    ok, out = git('tag', '--list')
    if ok:
        tags.update(t.strip() for t in out.splitlines() if t.strip())
    ok, out = git('ls-remote', '--tags', 'origin')
    if ok:
        for line in out.splitlines():
            ref = line.split('\t')[-1].strip()
            if ref.startswith('refs/tags/'):
                tags.add(ref[len('refs/tags/'):].replace('^{}', ''))
    return sorted(tags)


# --- the steps --------------------------------------------------------------------------------------
# Each returns True when it did its work, or found it already done, and False when it could not.

def step_check() -> bool:
    """Everything a release needs before it starts."""
    say('checking the repository ...')
    fine = True
    ok, out = git('status', '--porcelain')
    if not ok:
        say('  git could not be run here: %s' % out)
        return False
    if out:
        say('  there are changes that are not committed. Commit them first:')
        for line in out.splitlines():
            say('    ' + line)
        fine = False
    git('fetch', 'origin')
    ok, out = git('rev-list', '--left-right', '--count', 'HEAD...@{upstream}')
    if ok:
        ahead, behind = (int(n) for n in out.split())
        if ahead:
            say('  %d commit(s) are not pushed yet. Push them first.' % ahead)
            fine = False
        if behind:
            say('  GitHub has %d commit(s) this copy does not. Pull them first.' % behind)
            fine = False
    else:
        say('  could not compare this branch with GitHub: %s' % out)
        fine = False
    if gh_path() is None:
        say('  the GitHub CLI, gh, was not found. Install it from cli.github.com.')
        fine = False
    else:
        ok, out = gh('auth', 'status')
        if not ok:
            say('  the GitHub CLI is not signed in. Run gh auth login.')
            fine = False
    waiting = unreleased_lines(read_changelog())
    if not waiting:
        say('  nothing is under "%s" in changelog.txt, so there is nothing to release.' % UNRELEASE)
        fine = False
    elif len(waiting) > MAX_ENTRIES:
        say('  %d changes are under "%s", and a release carries no more than %d.'
            % (len(waiting), UNRELEASE, MAX_ENTRIES))
        fine = False
    else:
        say('  %d change(s) are waiting to be released.' % len(waiting))
    say('  everything is ready.' if fine else '  the release cannot go ahead until those are fixed.')
    return fine


def step_prepare():
    """Set VERSION to today's release and file the changelog under it.  Returns the version, and what the
    two files held before, so a failed build can put them back; or None when nothing was done."""
    version = next_version(all_tags(), today_stamp())
    text = read_changelog()
    waiting = unreleased_lines(text)
    if not waiting:
        say('nothing is under "%s", so there is nothing to file.' % UNRELEASE)
        return None
    say('this release will be %s, tagged %s, with %d change(s).'
        % (title_for(version), tag_for(version), len(waiting)))
    if not ask('Set VERSION to %s and file the changelog under it?' % version):
        say('skipped.')
        return None
    old_version = open(VERSION_FILE, encoding='utf-8').read() if os.path.isfile(VERSION_FILE) else None
    new, _changed, notes = plan_changelog(text, version)
    write_text(VERSION_FILE, version + '\n')
    write_text(CHANGELOG, new)
    say('VERSION is now %s.' % version)
    for note in notes:
        say('changelog: %s' % note)
    return version, old_version, text


def restore(saved) -> None:
    """Put VERSION and the changelog back as step_prepare found them."""
    _version, old_version, old_changelog = saved
    if old_version is None:
        if os.path.isfile(VERSION_FILE):
            os.remove(VERSION_FILE)
    else:
        write_text(VERSION_FILE, old_version)
    write_text(CHANGELOG, old_changelog)
    say('VERSION and changelog.txt are back as they were.')


def choose_build():
    """Which build: the folder, or the single executable.  None to skip."""
    say('which build should the release carry?')
    say('  1. the game in a folder, with its data beside the executable')
    say("  2. a single executable, with the sounds and the game's data inside it")
    say('  0. skip the build')
    while True:
        try:
            choice = input('Type a number and press Enter: ').strip()
        except EOFError:
            return None
        if choice == '0':
            return None
        if choice == '1':
            return []
        if choice == '2':
            return ['--embed']
        say('There is no choice "%s". Type 0, 1 or 2.' % choice)


def step_build(saved=None):
    """compiler.py, building dist\\SixthSense.  After step_prepare, a failed build undoes it.  True when
    it built, False when it failed, None when skipped."""
    flags = choose_build()
    if flags is None:
        say('skipped the build.')
        return None
    say()
    try:
        code = compiler.main(flags)
    except Exception as error:                          # a crash in the build counts as a failure
        say('the build stopped with an error: %r' % error)
        code = 1
    os.chdir(HERE)
    if code != 0:
        say('the build failed.')
        if saved is not None:
            restore(saved)
        return False
    return True


def step_package(version: str) -> bool:
    """Zip dist\\SixthSense into the release's archive.  Refuses a build made for another version, so an
    old build can never go out under a new name."""
    if not os.path.isdir(BUILD_DIR):
        say('there is no build in %s. Build it first.' % BUILD_DIR)
        return False
    carries = built_version()
    if carries != version:
        say('the build in %s is for %s, not %s. Build it again first.'
            % (BUILD_DIR, carries or 'no version', version))
        return False
    if not ask('Zip the build into %s?' % os.path.basename(zip_path(version))):
        say('skipped the zip.')
        return None
    try:
        package(BUILD_DIR, version)
    except OSError as error:
        say('the zip could not be written: %s' % error)
        return False
    return True


def step_commit(version: str) -> bool:
    """Commit VERSION and the changelog as the release, and push."""
    ok, out = git('status', '--porcelain', '--', 'VERSION', 'changelog.txt')
    if not out:
        say('VERSION and changelog.txt have nothing to commit.')
        return True
    if not ask('Commit VERSION and changelog.txt as "Release %s", and push?' % version):
        say('skipped.')
        return False
    ok, out = git('add', '--', 'VERSION', 'changelog.txt')
    if ok:
        ok, out = git('commit', '-m', 'Release %s' % version, '--', 'VERSION', 'changelog.txt')
    if not ok:
        say('the commit failed: %s' % out)
        return False
    say('committed.')
    ok, out = git('push', 'origin', 'HEAD')
    if not ok:
        say('the push failed: %s' % out)
        return False
    say('pushed.')
    return True


def step_tag(version: str) -> bool:
    """Tag the current commit V<version> and push the tag.  An existing tag is never moved."""
    tag = tag_for(version)
    if tag in all_tags():
        say('the tag %s already exists, so it is left where it is.' % tag)
        return True
    ok, head = git('log', '-1', '--format=%h %s')
    if not ask('Tag %s as %s, and push the tag?' % (head, tag)):
        say('skipped.')
        return False
    ok, out = git('tag', tag)
    if not ok:
        say('the tag could not be made: %s' % out)
        return False
    ok, out = git('push', 'origin', tag)
    if not ok:
        say('the tag could not be pushed: %s' % out)
        return False
    say('tagged %s and pushed it.' % tag)
    return True


def step_upload(version: str) -> bool:
    """The GitHub release, with the zip and that version's changelog lines."""
    tag, title = tag_for(version), title_for(version)
    archive = find_zip(version)
    if archive is None:
        say('there is no zip for %s at %s. Build and zip it first.' % (version, zip_path(version)))
        return False
    if tag not in all_tags():
        say('the tag %s does not exist yet. Tag the release first.' % tag)
        return False
    ok, _out = gh('release', 'view', tag)
    if ok:
        say('GitHub already has a release for %s, so it is left as it is.' % tag)
        return True
    notes = release_notes(read_changelog(), version)
    if not notes:
        say('the changelog has nothing under %s, so the release notes would be empty.'
            % changelog_heading(version))
    say('the release will be "%s", tag %s, with %s (%.0f MB).'
        % (title, tag, os.path.basename(archive), os.path.getsize(archive) / (1 << 20)))
    if not ask('Upload it to GitHub?'):
        say('skipped.')
        return False
    handle, notes_file = tempfile.mkstemp(suffix='.txt', prefix='release-notes-')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            fh.write(notes + '\n')
        say('uploading - this can take a few minutes for a zip this size. Leave this window open.')
        ok, out = gh('release', 'create', tag, archive, '--title', title, '--notes-file', notes_file,
                     '--verify-tag', capture=False)
    finally:
        os.remove(notes_file)
    if not ok:
        say('the upload failed. What gh said is above.')
        return False
    say('the release %s is on GitHub.' % title)
    return True


def full_release() -> None:
    """Every step, in order.  A step answered N is skipped; one that fails stops the release."""
    if not step_check():
        return
    say()
    saved = step_prepare()
    version = saved[0] if saved else read_version()
    if not version:
        say('there is no version to release.')
        return
    say()
    if step_build(saved) is False:
        return
    say()
    if step_package(version) is False:
        return
    say()
    if not step_commit(version):
        return
    say()
    if not step_tag(version):
        return
    say()
    step_upload(version)


# --- the menu ---------------------------------------------------------------------------------------

MENU = (
    ('Full release: every step below, in order', full_release),
    ('Check that everything is ready', step_check),
    ("Set the version and file the changelog", lambda: step_prepare()),
    ('Build', lambda: step_build()),
    ('Zip the build', lambda: step_package(read_version())),
    ('Commit and push the version and changelog', lambda: step_commit(read_version())),
    ('Tag the release', lambda: step_tag(read_version())),
    ('Upload the release to GitHub', lambda: step_upload(read_version())),
)


def menu() -> None:
    while True:
        say()
        say('SixthSense releaser.  VERSION is %s.' % (read_version() or 'missing'))
        say()
        for number, (text, _action) in enumerate(MENU, 1):
            say('  %d. %s' % (number, text))
        say('  0. Quit')
        say()
        try:
            choice = input('Type a number and press Enter: ').strip()
        except EOFError:
            return
        if choice == '0':
            return
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            text, action = MENU[int(choice) - 1]
            say('%s.' % text.split(':')[0])
            say()
            action()
            continue
        say('There is no choice "%s". Type a number from 0 to %d.' % (choice, len(MENU)))


def run() -> int:
    os.chdir(HERE)
    try:
        menu()
    finally:
        say()
        try:
            input('Finished. Press Enter to close this window.')
        except EOFError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(run())

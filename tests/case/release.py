"""releaser.py and compiler.py, where they can be checked without building, running git or reaching GitHub:
the version numbering, filing the changelog and putting it back, the release's names and notes, zipping a
build (a small stand-in one), and what the compiler puts inside the executable and beside it.

Nothing here builds, commits, tags or uploads, and the repository's own VERSION and changelog.txt are never
touched: every file a test writes is in a temporary folder.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import _scratch_save                                             # noqa: E402,F401  never the real save

import compiler                                                      # noqa: E402
import releaser                                                      # noqa: E402

CHANGELOG = ('unrelease:\n'
             'The newest change.\n'
             'An older change.\n'
             '\n'
             '26.09.01-1:\n'
             'Something released long ago.\n')


# --- the version ------------------------------------------------------------------------------------

def test_the_first_release_of_a_day_is_number_one():
    assert releaser.next_version([], '26.09.23') == '26.09.23-1'
    assert releaser.next_version(['V26.09.22-4'], '26.09.23') == '26.09.23-1'


def test_a_later_release_the_same_day_counts_up_from_the_tags():
    tags = ['V26.09.23-1', 'V26.09.23-2', 'V26.09.22-7', 'not-a-release', '26.09.23-9', 'V26.09.23-x']
    assert releaser.next_version(tags, '26.09.23') == '26.09.23-3'
    # a gap does not get filled: one past the highest
    assert releaser.next_version(['V26.09.23-1', 'V26.09.23-5'], '26.09.23') == '26.09.23-6'


def test_the_date_is_two_digit_year_month_and_day():
    moment = time.mktime((2026, 9, 3, 12, 0, 0, 0, 0, -1))
    assert releaser.today_stamp(moment) == '26.09.03'


def test_the_tag_and_the_title():
    assert releaser.tag_for('26.09.21-3') == 'V26.09.21-3'
    assert releaser.title_for('26.09.21-3') == 'SixthSense V26.09.21-3'


# --- the changelog ----------------------------------------------------------------------------------

def test_filing_moves_the_unreleased_lines_under_the_version():
    new, changed, _notes = releaser.plan_changelog(CHANGELOG, '26.09.23-1')
    assert changed
    blocks = compiler._parse_changelog(new)
    assert blocks[0] == ['unrelease:', []]
    assert blocks[1] == ['26.09.23-1:', ['The newest change.', 'An older change.']]
    assert blocks[2] == ['26.09.01-1:', ['Something released long ago.']]


def test_filing_nothing_leaves_the_changelog_as_it_was():
    text = 'unrelease:\n\n26.09.01-1:\nSomething released long ago.\n'
    new, changed, _notes = releaser.plan_changelog(text, '26.09.23-1')
    assert not changed and new == text


def test_a_missing_unrelease_line_is_put_back():
    new, changed, _notes = releaser.plan_changelog('26.09.01-1:\nOld.\n', '26.09.23-1')
    assert changed and new.startswith('unrelease:\n')


def test_the_release_notes_are_that_versions_lines():
    new, _changed, _notes = releaser.plan_changelog(CHANGELOG, '26.09.23-1')
    assert releaser.release_notes(new, '26.09.23-1') == 'The newest change.\nAn older change.'
    assert releaser.release_notes(new, '26.09.30-1') == ''


def test_the_unreleased_lines_are_counted():
    assert compiler.unreleased_lines(CHANGELOG) == ['The newest change.', 'An older change.']
    assert compiler.unreleased_lines('unrelease:\n\n26.09.01-1:\nOld.\n') == []
    assert releaser.MAX_ENTRIES == 100


def test_the_shipped_changelog_opens_on_the_version():
    new, _changed, _notes = releaser.plan_changelog(CHANGELOG, '26.09.23-1')
    assert compiler.without_unrelease(new).startswith('26.09.23-1:\n')
    # unreleased lines are never dropped from a copy
    assert compiler.without_unrelease(CHANGELOG).startswith('unrelease:\n')


def _with_temp_files(test):
    """Run ``test`` with the releaser's VERSION and changelog pointed at a temporary folder, the tags and
    the Y/N answer faked, so nothing real is read or written."""
    saved = (releaser.VERSION_FILE, releaser.CHANGELOG, releaser.all_tags, releaser.ask,
             releaser.today_stamp)
    with tempfile.TemporaryDirectory() as folder:
        releaser.VERSION_FILE = os.path.join(folder, 'VERSION')
        releaser.CHANGELOG = os.path.join(folder, 'changelog.txt')
        releaser.all_tags = lambda: ['V26.09.23-1']
        releaser.ask = lambda question: True
        releaser.today_stamp = lambda now=None: '26.09.23'
        try:
            test(folder)
        finally:
            (releaser.VERSION_FILE, releaser.CHANGELOG, releaser.all_tags, releaser.ask,
             releaser.today_stamp) = saved


#: Five entries: the fewest a release may carry.
FIVE = ('unrelease:\n'
        'The newest change.\n'
        'Another change.\n'
        'A third change.\n'
        'A fourth change.\n'
        'An older change.\n'
        '\n'
        '26.09.01-1:\n'
        'Something released long ago.\n')


def test_preparing_sets_the_version_and_files_the_changelog_and_a_failed_build_puts_them_back():
    def test(folder):
        releaser.write_text(releaser.VERSION_FILE, '26.09.21-1\n')
        releaser.write_text(releaser.CHANGELOG, FIVE)
        saved = releaser.step_prepare()
        assert saved is not None and saved[0] == '26.09.23-2'
        assert open(releaser.VERSION_FILE, encoding='utf-8').read() == '26.09.23-2\n'
        filed = open(releaser.CHANGELOG, encoding='utf-8').read()
        assert '26.09.23-2:\nThe newest change.' in filed
        releaser.restore(saved)
        assert open(releaser.VERSION_FILE, encoding='utf-8').read() == '26.09.21-1\n'
        assert open(releaser.CHANGELOG, encoding='utf-8').read() == FIVE
    _with_temp_files(test)


def _checked(status, changelog, answer=False):
    """step_check with git, gh, the changelog and the Y/N answer faked: what it said, and
    its answer.  Each question asked is added to what it said, marked with "?? "."""
    said = []
    saved = (releaser.git, releaser.gh_path, releaser.gh, releaser.read_changelog, releaser.say,
             releaser.ask)
    replies = {'status': (True, status), 'fetch': (True, ''), 'rev-list': (True, '0\t0')}
    releaser.git = lambda *a: replies[a[0]]
    releaser.gh_path = lambda: 'gh'
    releaser.gh = lambda *a: (True, '')
    releaser.read_changelog = lambda: changelog
    releaser.say = lambda text='': said.append(text)
    releaser.ask = lambda question: said.append('?? ' + question) or answer
    try:
        return said, releaser.step_check()
    finally:
        (releaser.git, releaser.gh_path, releaser.gh, releaser.read_changelog,
         releaser.say, releaser.ask) = saved


def test_the_check_names_its_problems_not_the_waiting_changes():
    """The verdict came straight after "11 change(s) are waiting to be released" and said
    "the release cannot go ahead until those are fixed", as if the changes were the
    problem.  It now names each problem again, and the count says it is fine."""
    said, ready = _checked(' M releaser.py', FIVE)
    assert ready is False
    assert '  5 change(s) are waiting to be released, which is fine.' in said, said
    at = said.index('  the release cannot go ahead until this is fixed:')
    assert said[at + 1] == '    1. there are changes that are not committed. Commit them first:', said
    assert not any('those are fixed' in line for line in said)
    said, ready = _checked('', FIVE)
    assert ready is True and said[-1] == '  everything is ready.', said


FOUR = FIVE.replace('A fourth change.\n', '')


def test_fewer_than_five_entries_do_not_make_a_release():
    """tsatria03, 2026-09-24: a version needs at least five entries.  Four are refused
    when the question to release anyway is answered N, and nothing is filed or changed."""
    assert releaser.MIN_ENTRIES == 5

    def test(folder):
        releaser.ask = lambda question: False
        releaser.write_text(releaser.VERSION_FILE, '26.09.21-1\n')
        releaser.write_text(releaser.CHANGELOG, FOUR)
        assert releaser.step_prepare() is None
        assert open(releaser.VERSION_FILE, encoding='utf-8').read() == '26.09.21-1\n'
        assert open(releaser.CHANGELOG, encoding='utf-8').read() == FOUR
    _with_temp_files(test)
    said, ready = _checked('', FOUR, answer=False)
    assert ready is False
    assert '?? Release anyway with 4 change(s)?' in said, said
    at = said.index('  the release cannot go ahead until this is fixed:')
    assert said[at + 1] == ('    1. only 4 change(s) are under "unrelease:", and a release '
                            'needs at least 5.'), said
    # said once before the question, and named once more in the verdict, not twice before it
    assert said.count('  only 4 change(s) are under "unrelease:", and a release needs at least 5.') == 1


def test_fewer_than_five_can_be_released_anyway():
    """tsatria03, 2026-09-24: the force override.  Answering Y to releasing anyway lets
    the check pass and the prepare step file the four; a full release asks only once."""
    said, ready = _checked('', FOUR, answer=True)
    assert ready is True, said
    assert '  releasing anyway with 4 change(s).' in said, said
    assert said[-1] == '  everything is ready.', said

    def test(folder):
        releaser.write_text(releaser.VERSION_FILE, '26.09.21-1\n')
        releaser.write_text(releaser.CHANGELOG, FOUR)
        saved = releaser.step_prepare()
        assert saved is not None and saved[0] == '26.09.23-2'
        assert '26.09.23-2:\nThe newest change.' in open(releaser.CHANGELOG, encoding='utf-8').read()
        # forced, as a full release calls it after the check: no second question
        releaser.write_text(releaser.CHANGELOG, FOUR)
        asked = []
        releaser.ask = lambda question: asked.append(question) or True
        assert releaser.step_prepare(forced=True) is not None
        assert not any('anyway' in q for q in asked), asked
    _with_temp_files(test)


def test_other_problems_are_not_hidden_behind_the_question():
    """With another problem in the way, the check does not ask to release anyway, since
    the release could not go ahead either way; the shortfall is named with the rest."""
    said, ready = _checked(' M releaser.py', FOUR, answer=True)
    assert ready is False
    assert not any(line.startswith('?? ') for line in said), said
    assert '    2. only 4 change(s) are under "unrelease:", and a release needs at least 5.' in said, said


def test_nothing_waiting_is_never_released_anyway():
    said, ready = _checked('', 'unrelease:\n\n26.09.01-1:\nOld.\n', answer=True)
    assert ready is False
    assert not any(line.startswith('?? ') for line in said), said


def test_preparing_with_nothing_waiting_does_nothing():
    def test(folder):
        text = 'unrelease:\n\n26.09.01-1:\nOld.\n'
        releaser.write_text(releaser.VERSION_FILE, '26.09.21-1\n')
        releaser.write_text(releaser.CHANGELOG, text)
        assert releaser.step_prepare() is None
        assert open(releaser.VERSION_FILE, encoding='utf-8').read() == '26.09.21-1\n'
        assert open(releaser.CHANGELOG, encoding='utf-8').read() == text
    _with_temp_files(test)


# --- the zip ----------------------------------------------------------------------------------------

def test_the_zip_is_named_for_the_version():
    assert releaser.zip_path('26.09.23-1') == os.path.join(
        ROOT, 'dist', 'SixthSense-Win-26.09.23-1.zip')
    assert releaser.find_zip('00.00.00-0') is None


def _fake_build(folder, version):
    build = os.path.join(folder, 'SixthSense')
    os.makedirs(os.path.join(build, 'game'))
    for name, body in (('SixthSense.exe', 'exe'), ('VERSION', version + '\n'),
                       (os.path.join('docks', 'todo list.txt'), 'todo'),
                       (os.path.join('game', 'SoundList.plist'), 'x')):
        os.makedirs(os.path.dirname(os.path.join(build, name)), exist_ok=True)
        with open(os.path.join(build, name), 'w', encoding='utf-8') as fh:
            fh.write(body)
    return build


def test_the_releaser_zips_the_build_under_one_folder():
    import zipfile
    saved = releaser.zip_path
    with tempfile.TemporaryDirectory() as folder:
        build = _fake_build(folder, '26.09.23-1')
        releaser.zip_path = lambda version: os.path.join(folder, 'SixthSense-Win-%s.zip' % version)
        try:
            archive = releaser.package(build, '26.09.23-1')
            with zipfile.ZipFile(archive) as zf:
                names = sorted(zf.namelist())
            leftover = os.path.exists(archive + '.part')
        finally:
            releaser.zip_path = saved
    # the zip extracts to a SixthSense-Windows folder (tsatria03, 2026-09-25)
    assert names == ['SixthSense-Windows/SixthSense.exe', 'SixthSense-Windows/VERSION',
                     'SixthSense-Windows/docks/todo list.txt',
                     'SixthSense-Windows/game/SoundList.plist']
    assert not leftover


def test_the_releaser_will_not_zip_a_build_made_for_another_version():
    saved = (releaser.BUILD_DIR, releaser.ask, releaser.package)
    zipped = []
    with tempfile.TemporaryDirectory() as folder:
        releaser.BUILD_DIR = _fake_build(folder, '26.09.21-1')
        releaser.ask = lambda question: True
        releaser.package = lambda build, version: zipped.append(version)
        try:
            assert releaser.built_version() == '26.09.21-1'
            assert releaser.step_package('26.09.23-1') is False
            assert zipped == []
            assert releaser.step_package('26.09.21-1') is True
            assert zipped == ['26.09.21-1']
        finally:
            releaser.BUILD_DIR, releaser.ask, releaser.package = saved


def test_answering_no_skips_the_zip():
    saved = (releaser.BUILD_DIR, releaser.ask, releaser.package)
    zipped = []
    with tempfile.TemporaryDirectory() as folder:
        releaser.BUILD_DIR = _fake_build(folder, '26.09.23-1')
        releaser.ask = lambda question: False
        releaser.package = lambda build, version: zipped.append(version)
        try:
            assert releaser.step_package('26.09.23-1') is None
        finally:
            releaser.BUILD_DIR, releaser.ask, releaser.package = saved
    assert zipped == []


# --- the compiler -----------------------------------------------------------------------------------

class _Args:
    def __init__(self, **flags):
        for name in ('embed', 'onefile', 'no_game', 'console', 'clean', 'dry_run'):
            setattr(self, name, flags.get(name, False))


def test_the_compiler_no_longer_files_the_changelog_or_zips():
    for name in ('plan_changelog', 'prepare_release_files', 'first_version', 'package', 'PACK_STEPS'):
        assert not hasattr(compiler, name), name
    assert not any('--no-package' in flags for _text, flags in compiler.MENU)


def test_the_player_documents_ship_in_a_docks_folder():
    """The build lays docks\\ out as the repository does; VERSION and the license stay at the top."""
    with tempfile.TemporaryDirectory() as build:
        compiler.copy_side_files(build)
        compiler.strip_shipped_changelog(build)
        top = sorted(os.listdir(build))
        docks = sorted(os.listdir(os.path.join(build, 'docks')))
        shipped = open(os.path.join(build, 'docks', 'changelog.txt'), encoding='utf-8').read()
    assert top == ['VERSION', 'docks', 'license.txt'], top
    assert docks == ['changelog.txt', 'readme.txt', 'todo list.txt'], docks
    # an empty unrelease: heading is taken out of the copy in docks\, not left in it
    assert shipped == compiler.without_unrelease(shipped)


def test_the_player_documents_are_read_from_docks():
    for name in ('readme.txt', 'changelog.txt', 'todo list.txt'):
        assert os.path.isfile(os.path.join(ROOT, 'docks', name)), name
    assert releaser.CHANGELOG == os.path.join(ROOT, 'docks', 'changelog.txt')
    assert releaser.CHANGELOG_GIT == 'docks/changelog.txt'


def test_the_players_readme_has_no_markdown():
    """A screen reader reads every # * | and ` aloud, so the readme a player opens has none."""
    with open(os.path.join(ROOT, 'docks', 'readme.txt'), encoding='utf-8') as fh:
        text = fh.read()
    assert text.strip()
    for mark in ('#', '*', '|', '`'):
        assert mark not in text, mark


def test_a_folder_build_puts_nothing_of_the_games_inside():
    """Nothing of the game's own goes inside a folder build; only the third-party licenses
    do (tsatria03, 2026-09-25)."""
    cmd = compiler.command(_Args())
    assert '--onefile' not in cmd
    added = [cmd[i + 1] for i, part in enumerate(cmd) if part == '--add-data']
    assert added == [compiler.LICENSES_STAGE + os.pathsep + 'licenses'], added
    assert cmd[-1] == compiler.ENTRY


def test_the_third_party_licenses_go_inside_and_license_txt_stays_beside():
    """tsatria03, 2026-09-25: the licenses of OpenAL Soft, the NVDA client, Prism and pygame
    go inside the executable; the port's own license.txt stays beside it, and nothing is
    copied into a licenses folder beside it any more."""
    for flags in ({}, {'embed': True}, {'onefile': True}):
        cmd = compiler.command(_Args(**flags))
        added = [cmd[i + 1] for i, part in enumerate(cmd) if part == '--add-data']
        assert compiler.LICENSES_STAGE + os.pathsep + 'licenses' in added, (flags, added)
    assert not hasattr(compiler, 'copy_licenses')
    assert ('LICENSE', 'license.txt') in compiler.SIDE_FILES
    with tempfile.TemporaryDirectory() as folder:
        stage = os.path.join(folder, 'licenses')
        copied = compiler.stage_licenses(stage)
        found = [os.path.relpath(os.path.join(d, f), stage).replace(os.sep, '/')
                 for d, _s, fs in os.walk(stage) for f in fs]
    assert copied == len(found) and copied > 0, found
    assert 'openal-soft/license.txt' in found and 'nvda-controller-client/license.txt' in found


def test_embedding_puts_the_sounds_and_the_data_inside_one_executable():
    with tempfile.TemporaryDirectory() as bundle:
        os.makedirs(os.path.join(bundle, 'sounds', 'used', 'sfx'))
        os.makedirs(os.path.join(bundle, 'sounds', 'unused', 'sfx'))
        data = compiler.embedded_data(bundle)
        cmd = compiler.command(_Args(embed=True), data)
    assert '--onefile' in cmd
    assert cmd[cmd.index('--distpath') + 1] == os.path.join(ROOT, 'dist', 'SixthSense-Windows')
    assert cmd[cmd.index('--name') + 1] == 'SixthSense'
    added = [cmd[i + 1] for i, part in enumerate(cmd) if part == '--add-data']
    assert compiler.EMBED_STAGE + os.pathsep + 'game' in added
    assert os.path.join(bundle, 'sounds', 'used') + os.pathsep + 'game/sounds/used' in added
    assert os.path.join(bundle, 'sounds', 'unused') + os.pathsep + 'game/sounds/unused' in added
    # the text a player reads is never among what goes inside; only the third-party
    # licenses are (since 2026-09-25), never the port's own license.txt
    assert not any('changelog' in a or 'todo' in a or 'license.txt' in a.lower() for a in added)
    assert compiler.LICENSES_STAGE + os.pathsep + 'licenses' in added


def test_a_flat_bundle_embeds_its_top_folder_alone():
    with tempfile.TemporaryDirectory() as bundle:
        assert compiler.embedded_data(bundle) == [(compiler.EMBED_STAGE, 'game')]


def test_every_build_lands_in_one_folder():
    """tsatria03, 2026-09-25: the folder is SixthSense-Windows, and the executable inside it
    is still SixthSense.exe."""
    assert compiler.output_dir(_Args()) == compiler.output_dir(_Args(embed=True)) \
        == os.path.join(ROOT, 'dist', 'SixthSense-Windows') == releaser.BUILD_DIR


def test_a_folder_build_is_moved_to_the_windows_folder():
    """PyInstaller names a folder build after the executable, dist\\SixthSense; the compiler
    moves it to dist\\SixthSense-Windows, and clears both before the next build."""
    saved = compiler.HERE
    with tempfile.TemporaryDirectory() as here:
        compiler.HERE = here
        try:
            built = compiler.pyinstaller_dir()
            dest = compiler.output_dir()
            assert built == os.path.join(here, 'dist', 'SixthSense')
            os.makedirs(os.path.join(built, '_internal'))
            open(os.path.join(built, 'SixthSense.exe'), 'w').close()
            compiler.move_folder_build(dest)
            assert not os.path.exists(built)
            assert os.path.isfile(os.path.join(dest, 'SixthSense.exe'))
            assert os.path.isdir(os.path.join(dest, '_internal'))
            os.makedirs(built)
            compiler.clear_output(dest)
            assert not os.path.exists(built) and not os.path.exists(dest)
        finally:
            compiler.HERE = saved


def test_the_stage_holds_only_what_the_game_reads():
    with tempfile.TemporaryDirectory() as bundle:
        for name in ('SoundList.plist', 'type1.plist', 'g_CH1_E', 'a_CH1_E.txt', 's_CH1_E.txt',
                     'sixsense', 'Icon.png', 'stage1ground', 'PkgInfo'):
            open(os.path.join(bundle, name), 'w').close()
        saved = compiler.EMBED_STAGE
        compiler.EMBED_STAGE = os.path.join(bundle, 'stage')
        try:
            names = compiler.stage_embedded(bundle)
            staged = sorted(os.listdir(compiler.EMBED_STAGE))
        finally:
            compiler.EMBED_STAGE = saved
    assert names == staged == sorted(['SoundList.plist', 'type1.plist', 'g_CH1_E', 'a_CH1_E.txt',
                                      's_CH1_E.txt'])


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    bad = 0
    for fn in fns:
        try:
            fn()
            print('ok    %s' % fn.__name__)
        except AssertionError as e:
            bad += 1
            print('FAIL  %s: %s' % (fn.__name__, e))
        except Exception as e:
            bad += 1
            print('ERROR %s: %r' % (fn.__name__, e))
    print('%d/%d passed' % (len(fns) - bad, len(fns)))
    sys.exit(1 if bad else 0)

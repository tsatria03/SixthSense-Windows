# Building and releasing SixthSense

This is how to build the game and how to make a release. Two scripts in the repository's root do the work. `compiler.py` builds the game. `releaser.py` makes a release, and it runs the compiler itself when it gets to the build.

## What you need

- 64-bit Python 3.12 or newer on Windows. Stay 64-bit, because the OpenAL and NVDA libraries in `vendor/` are 64-bit.
- The game's packages, installed with `pip install -r requirements.txt`.
- PyInstaller, installed with `pip install pyinstaller`. The compiler stops and says so if it is missing.
- For a release, GitHub's command-line tool, `gh`, logged in with `gh auth login`. The account needs write access to `tsatria03/SixthSense-Windows`. The releaser looks for `gh` on the PATH, then in `%USERPROFILE%\.game_tools\tools.ini`, then at `C:\Program Files\GitHub CLI\gh.exe`.

Players need none of this. A build carries its own Python.

## Building

Double-click `compiler.py`, or run `py compiler.py` with nothing after it. It offers a numbered menu. Type a number and press Enter. At the end it waits for Enter, so you can hear how it went.

The menu:
1. Folder build. The game in a folder, with its data beside the executable. This is the usual build.
2. Single exe. The sounds and the game's data go inside one executable. It starts a few seconds slower, because it unpacks itself at every launch.
3. Clean build. Empties PyInstaller's cache first. Use it when a build behaves oddly.
4. Build with a console window. Use it to see why the game will not start.
5. One-file build. A single executable, with the game's data still beside it.
6. Build without the game's data.
7. Show what a build would do, without building anything.

Each choice is also a flag, which still works typed out:
- `py compiler.py` makes the folder build.
- `py compiler.py --embed` makes the single exe.
- `py compiler.py --clean`, `--console`, `--onefile`, `--no-game` and `--dry-run` match the other choices.

Every build lands in `dist\SixthSense-Windows`, around `SixthSense.exe`. The readme, the changelog and the todo list go beside it in a `docks` folder. `VERSION` and `license.txt` go at the top. The compiler never zips anything and never changes the repository.

## Releasing

Double-click `releaser.py`, or run `py releaser.py`. It asks Y or N before every step. Choose 1 to go through all of them in order, or pick one step on its own.

The menu:
1. Full release. Every step below, in order.
2. Check that everything is ready. The tree must be committed and pushed. `gh` must be found. The changelog must have entries waiting.
3. Set the version and file the changelog. The version is today's date and that day's release number, such as `26.09.27-1`. A second release on the same day is `-2`. It is written to `VERSION`, and the lines under `unrelease:` in `docks/changelog.txt` move under a new heading with that version.
4. Build. Runs the compiler, and asks which build the release carries. Type 1 for the folder build, 2 for the single exe, or 0 to skip.
5. Zip the build. Makes `dist\SixthSense-Win-<version>.zip`. It refuses if the build's `VERSION` is not the release's.
6. Commit and push the version and changelog, as "Release <version>".
7. Tag the release as `V<version>`, such as `V26.09.27-1`, and push the tag. It refuses to overwrite a tag that already exists.
8. Upload the release to GitHub. It is titled "SixthSense V<version>". The zip is attached, and that version's changelog lines are the notes.

## How many changelog entries

A release aims for 50 to 100 lines under `unrelease:`. More than 100 is always refused. With fewer than 5, the releaser asks "Release anyway with N change(s)?", and Y goes on. Headings are never counted, only the lines under them. After a release, `unrelease:` starts again from nothing.

## If a release stops partway

- A failed build puts `VERSION` and the changelog back by itself.
- If you stop after step 3 but before step 6, `VERSION` and the changelog stay changed on disk, and the check then refuses to go on. Put them back with `git restore VERSION "docks/changelog.txt"`, then run the releaser again.
- A tag or a release that already exists is never overwritten. The releaser looks for tags on your machine and on GitHub, so a release made from another machine counts too. To redo one, delete the release and its tag on GitHub, and the tag on your machine with `git tag -d V<version>`.

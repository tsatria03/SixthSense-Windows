# Bloopers

Funny moments from making the port, kept for fun: the headshot that followed the zombie around, and whatever comes next. Nothing in here is part of the game, and the build script leaves this folder out of releases.

## Adding a clip

- Keep it short, preferably under two minutes.
- Name it by date and what happens, for example `2026-09-22 headshot follows the zombie.mp3`.
- Use a compressed format, such as MP3, Ogg or M4A for sound, or MP4 for video. Every file committed to git stays in its history for good, even after it is deleted, so small files keep the repository small.
- Add a line to the list below saying what the clip is and what caused it, if it is known.

## Clips

- `game/sounds/unused/bloopers/stop_standing_by_the_zombie!.ogg`, 39 seconds, 2026-09-22. The girl is calling for help while she stands right next to the zombie, and "headshot!" rings out from where she is. For a while the headshot announcement was converted to mono so it would pan, which put it at the zombie's position instead of in the centre, where the original always has it. It is centred again.

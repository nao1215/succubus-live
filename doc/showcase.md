# README showcase

Run from the repository root on Linux with Go (the toolchain requested by
`go.mod`), Python 3 with PyYAML, ffmpeg, Xvfb and xauth installed:

```sh
python3 tools/showcase.py
```

The script uses `go tool gozen run --dev --script --shots` with the Gozen version
pinned in `go.mod`. It writes `doc/img/showcase.gif`: 960×540, 6 fps, an infinite
loop of eight three-second scenes (24 seconds). ffmpeg generates a shared palette
and applies ordered Bayer dithering. Raw PNGs, input scripts, traces, isolated
saves and three review PNGs per scene remain in `.cache/showcase/run-*/`.
The review PNGs are decoded from the final GIF. Inspect them before publishing.

Order: channel listing, Nox, Ella, Mora, Vespa, Pim, Lise, Lise × Gyal.
Gyal is a guest with no solo channel, so her existing collaboration is included
to cover all seven characters. The listing scrolls to expose its channel cards;
each following scene uses the game's fullscreen stream view.

Each capture has fresh settings: English, fullscreen stream view and captions
off. The listing still displays English captions (its captions do not use the
watch view's CC setting); the language selector still labels Japanese in Japanese.
No Japanese dialogue subtitles are intended in the output.

Only temporary copies of `data/streams.yaml` are staged: the solo scenes contain
their one channel, the listing contains all channels, and the Gyal scene unlocks
the existing Lise/Gyal episode and selects it with probability one. Solo channels
use their first existing episode. Game assets and dialogue are read through
symlinks; the tracked game and the player's saves are never edited. The seed is
7, but the engine also uses wall-clock time for stream scheduling and audience
counts, so reruns need not be byte-identical.

## Reference

The [Debimate Games page](https://debimate.jp/games/) inspected on 2026-11-01
serves a muted looping MP4, rather than a GIF. The downloaded video is 960×540,
49.33 seconds, 1,058,596 bytes. It starts with the ordinary stream/listing view
(including scrolling), then shows fullscreen Nox, Ella, Mora, Vespa, Pim and
Lise. Measured cut points are 7.08, 14.13, 21.21, 28.21, 35.29 and
42.25 seconds (each section lasts approximately 7 seconds). Its Japanese subtitles make it unsuitable
for the English README. The local Debimate repository documents its recording
in `scripts/game-demos/README.md` and keeps the video at
`content/games/media/succubus-live.mp4`. This showcase shortens each scene to
three seconds and adds the guest collaboration to keep the GIF compact.

## Publishing order

Commit this GIF and its reproduction instructions on `docs/showcase-gif`.
In Gozen, create `docs/succubus-live-showcase` from `origin/main` in a separate
worktree and replace the Made with Gozen image URL's `stream.jpg` with
`showcase.gif`. Suggested English alt text:
`Succubus Live: channel listing and fullscreen streams featuring all seven characters`.
The URL points to Succubus Live's `main`, so publish the GIF there before merging
the Gozen README change. Preparing these commits does not require pushing them.

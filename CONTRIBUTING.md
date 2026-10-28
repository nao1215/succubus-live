## Contributing to Succubus Live

Thank you for helping make Succubus Live better. Bug reports, ideas for topics and reactions, fixes to the scripts and the translation, and reviews are all welcome.

### 1. Start with clear communication

- Bug report: use the issue template. For a wrong or odd line, say which streamer said it and what she said.
- A new stream, topic or reaction: open an issue first so we can agree on it before you write it.
- A fix to a line or the translation: open a pull request with the line before and after.

### 2. What you need

For `make check`:

- Python 3 with PyYAML
- Node.js: `tools/kwtest.py` runs the reactions' patterns as JavaScript regular expressions, the way the game reads them
- git
- gozen, the version in `go.mod`: Go 1.24 or later runs it as `go tool gozen` (Go fetches the newer toolchain `go.mod` asks for). With a prebuilt `gozen` command of the same version, run `make check GOZEN=gozen`.

To render the voices (`make voices`, `make voices-en`):

- [uv](https://docs.astral.sh/uv/), git and ffmpeg. `tools/voices.py` sets up the speech models in `~/.cache/succubus-live-voice/` the first time.
- For English, espeak-ng too (`apt install espeak-ng`, `brew install espeak-ng`): Kokoro reads the words its dictionary lacks with it, and without it those words are silent.

To export (`make web`, `make desktop`): curl, tar, unzip, zip and sha256sum (or `shasum` on macOS), besides gozen. `tools/runtime.sh` downloads the player runtime of the gozen version in `go.mod`, read from the file (Go is not needed for that); `gozen export` takes only a runtime of its own version, so a `gozen` command of another version needs that version passed: `GOZEN_VERSION=vX.Y.Z make web GOZEN=gozen`.

### 3. Change the game

The scripts in `src/` are the source. `tools/import_stream.py` writes `game/` from them and `assets/`, with `game/LICENSE` and `game/NOTICE.txt` copied from `LICENSE` and `NOTICE.md`; `tools/voices.py` writes `game/assets/voice/`; `game/game.yaml`, the fonts and the logo are put there by hand.

1. Edit the YAML in `src/`. [src/WRITERS.md](./src/WRITERS.md) is the style guide and [src/README.md](./src/README.md) describes every file.
2. `make check` checks the scripts, writes `game/` and runs `gozen check` on it.
3. `make voices` (Japanese) and `make voices-en` (English) render the voices of the lines that are new or changed, the streams' lines and the reactions' lines both; the voices of lines that are gone are removed. A line with a name filled in at play time (`{from}`) is recorded once without the name ("Thanks, {from}." is read as "Thanks.", "{from} keeps it" as "You keep it") and filed under the line before it is filled; the subtitle still shows the name. A line with the player's own words (`{text}`, `{days}`) has no recording: its subtitle is shown and the streamer says her `fallback` line from `src/voice/<id>.yaml`. A line without a recording is never read by the browser's speech synthesis (`missing_voice: captions`). `gozen check` does not fail on a missing voice, so check the list of lines without a voice that `tools/voices.py` prints.
4. `make run` plays the game in a window; `make web` exports the browser version into `dist/web`:

```shell
make web
cd dist/web && python3 -m http.server 8000   # open http://localhost:8000
```

Commit `src/`, `game/` and `game/assets/voice/` together, so the voices always match the lines.

### 4. What the scripts must keep

- No sexual content in a stream where children appear (`family: true`), and none about real people or minors. The streamers decline sexual or romantic requests from viewers who identify themselves as minors; a reaction must keep that.
- Facts about real games, music, software and events need a source in `src/sources/`.
- The English translation has the same beats as the Japanese one; `tools/build.py` checks it.

### 5. Release

1. In `CHANGELOG.md`, move the entries of `## [Unreleased]` into a new section named after the tag without its `v`: `## [X.Y.Z] - YYYY-MM-DD`, or `## [1.2.0-rc.1] - YYYY-MM-DD` for the tag `v1.2.0-rc.1`. The release notes are that section; a tag without one stops the release.
2. Push a tag `vX.Y.Z` on `main`. A tag `vX.Y.Z-rc.N`, such as `v1.2.0-rc.1`, makes a prerelease; a tag of any other form stops the release.
3. The `Release` workflow runs the checks of `make verify` on the tag, exports the desktop zips, signs `checksums.txt` with cosign and publishes them.

GitHub Pages follows `main`, after the same checks.

# Changelog

All notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.3] - 2026-11-19

### Changed

- Gozen v0.26.0 (from v0.15.0): the player gains a text size setting, can be added to a phone's home screen from the browser, asks to turn a phone held the other way, and keeps the autosave when the page is hidden. Go 1.26.11, which gozen v0.26.0 requires, is the minimum to build the game.
- CI scans the Go modules in go.mod with osv-scanner and the commits with gitleaks on every pull request and push to main.
- CI scans the repository with Trivy on every pull request (Trivy covers dependency vulnerabilities, committed secrets and misconfigurations, and also runs daily). Workflow actions are recorded in `.github/workflows/actions.lock`, which CI verifies against the pinned commits.

## [0.1.2] - 2026-10-28

### Fixed
- The streamers' lines that hold a name (answers to your choices, replies to comments and tips) are voiced. They were read by the browser's speech synthesis; they are now recorded once without the name, and the subtitle still shows it.
- A comment of your own read out on stream plays the streamer's short reply instead of the browser's speech synthesis, and the browser never reads a line aloud with speech synthesis.
- The first line of a stream no longer falls back to speech synthesis on a slow connection: it waits longer for its voice, and the lobby starts loading the opening lines.

### Changed
- Gozen v0.15.0.

## [0.1.1] - 2026-10-28

### Added
- A link to the game shows a card with its picture and description.

### Fixed
- The first visit opens in the language of your device, so English speakers choose their name in English; the language buttons work on the name screen too.
- The streamer's next line after reading out your tip message is no longer silent.

### Security
- Run CodeQL on the Python tools and the workflows for every pull request, push to main and once a week.
- Attach SLSA provenance (`multiple.intoto.jsonl`) to each release and verify it with slsa-verifier.

## [0.1.0] - 2026-10-28

### Added
- Six streamers, always live: Lise (games), Mora (single life), Pim (family life), Ella (music), Nox (programming) and Vespa (pop culture), with 51 streams of 10 to 15 minutes in Japanese and English.
- Four collabs that open after you have watched both streamers for 30 minutes, one of them with Gyaru from Rabbit Run as a guest.
- Comments, answers to the streamers' questions and tips; the streamers may read your comment out and answer it, and they remember you.
- Pre-rendered voices for every line of the streams, in Japanese (Irodori-TTS) and English (Kokoro-82M).
- The browser version on GitHub Pages and desktop zips for Windows, macOS and Linux.

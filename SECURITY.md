# Security policy

## Supported versions
Only the latest release and the browser version on GitHub Pages get fixes, including security fixes.

## Reporting a vulnerability
Report security issues privately, not through public issues or pull requests.

- Email: n.chika156@gmail.com
- Or use the "Report a vulnerability" button on the repository's Security tab.

Succubus Live is a game made of YAML, pictures and sounds, played by the [gozen](https://github.com/nao1215/gozen) player. The game has no server, no account and no analytics: the browser version fetches only its own files from GitHub Pages, and the game uploads nothing it keeps to a server of its own. It keeps the name you chose, your gold, what the streamers remember about you, and the last 200 comments the streamers had no reaction for (with the time, the channel and the language), in the browser's local storage or in a folder on your computer; [What the game keeps](#what-the-game-keeps) below says where and how to erase them.

One thing is outside the game's hands: in the browser version, a line with no recording (one with your name or your comment in it, for one) is read by the browser's speech synthesis, which may use an online voice service of the browser or the operating system: your name and comments may then be sent to that service. The speaker button on the stream turns the voices off.

Reports about the save data, what the comment field accepts, or the browser page are especially useful. A problem in the player itself is best reported to [gozen](https://github.com/nao1215/gozen/security/policy). Please include:

- the version (the release tag, or "browser" and the date)
- OS or phone, and the browser
- what you did and what happened

## What the game keeps

The game keeps these on your device. It has no server of its own and uploads none of them; the one thing that may send text out is the browser's speech synthesis, which can receive your name and comments when it reads a line aloud (see above).

- the name you chose, your gold, and what the streamers remember about you
- the last 200 comments the streamers had no reaction for, with the time, the channel and the language (`stream_unanswered.json`)
- the settings: the language and the full-screen stream view

In the browser they are in the site's local storage, under keys that start with `gozen/succubus-live/`. To erase them, remove the site data of `nao1215.github.io` in the browser's settings (it also removes the data of the other pages on that site) or remove those keys. A private window usually throws them away when it is closed; how long they last depends on the browser.

On the desktop they are, by default, in the folder `gozen/succubus-live/` of your user configuration folder: `$XDG_CONFIG_HOME` (`~/.config/` when it is not set) on Linux, `%AppData%` on Windows, `~/Library/Application Support/` on macOS. A player started with `--save-dir DIR` keeps them in `DIR` instead. To erase them, remove that folder.

## What to expect
Succubus Live is maintained by one developer in spare time, so there is no guaranteed response time. I will acknowledge the report, confirm the issue, and fix it in a new release.

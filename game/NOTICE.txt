# Third-party notices

Succubus Live is released under the [MIT License](./LICENSE). The following parts are covered by their own licenses. `tools/import_stream.py` copies [LICENSE](./LICENSE) and this file into `game/LICENSE` and `game/NOTICE.txt` (`make check` fails when they differ). `gozen export` puts the game in `game/` of every export, so they are `game/LICENSE` and `game/NOTICE.txt` in each desktop zip; in the browser version the player may read them compressed (`game/LICENSE.gz`; `game/files.json` maps each name to the file served), and `make web` also puts them uncompressed at the top of the site as `LICENSE` and `NOTICE.txt`.

## Fonts

| File | Font | License |
| ---- | ---- | ------- |
| `game/assets/fonts/mplus-1p-regular.ttf` (the same path in the desktop zips) | M+ 1p Regular by M+ FONTS PROJECT | [M+ FONTS License](./game/assets/fonts/LICENSE.txt), beside the font in the desktop zips; `make web` also puts it uncompressed at the top of the site as `LICENSE-mplus.txt` (free to use, copy and distribute, with or without modification) |
| `tools/banner/LilitaOne-Regular.ttf` (the banner only) | Lilita One by Juan Montoreano | [SIL Open Font License 1.1](./tools/banner/OFL-LilitaOne.txt) |

## The gozen player

The browser version and the desktop zips run on the [gozen](https://github.com/nao1215/gozen) player (MIT License). `gozen export` puts the license texts of the player, the Go runtime and the Go modules linked into it in `runtime-licenses/` of every zip and of the browser version: `runtime-licenses/LICENSE`, `runtime-licenses/GO-LICENSE` and `runtime-licenses/THIRD_PARTY_LICENSES/`.

## Voices

The audio files in `game/assets/voice/` were generated with the speech models below and are released under the MIT License with the rest of the game. No model weights or model code are included in this repository or in the exports; the models' own licenses and conditions of use (on their model cards) apply to the models, not as a license of these files. `tools/voices.py` downloads the models when it renders the voices.

| Part | Role | License or terms |
| ---- | ---- | ---------------- |
| [Irodori-TTS](https://github.com/Aratako/Irodori-TTS) (code) by Aratako | Japanese speech synthesis | MIT |
| [Irodori-TTS v4.1-Small-MF](https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small-MF) (weights) | Japanese speech model | MIT, with the conditions of use on [its model card](https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small-MF#license--ethical-restrictions) |
| [Semantic-DACVAE-Japanese-32dim](https://huggingface.co/Aratako/Semantic-DACVAE-Japanese-32dim) | Audio codec of Irodori-TTS | MIT |
| [modernbert-ja-310m](https://huggingface.co/sbintuitions/modernbert-ja-310m) by SB Intuitions | Reads the text and the voice descriptions inside Irodori-TTS | MIT |
| [SilentCipher](https://github.com/sony/silentcipher) by Sony Research (the package Irodori-TTS's `uv.lock` pins, from [SesameAILabs/silentcipher](https://github.com/SesameAILabs/silentcipher), and the model [sony/silentcipher](https://huggingface.co/sony/silentcipher)) | Inaudible watermark Irodori-TTS puts in the audio it generates | MIT |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad | English speech synthesis and its built-in voices | Apache License 2.0 ([model card](https://huggingface.co/hexgrad/Kokoro-82M)) |

What `tools/voices.py` fixes, and what it does not:

- Fixed: the Irodori-TTS code (a git commit), the Python packages of Irodori-TTS (its `uv.lock`, installed with `uv sync --frozen`), and the versions of the Python packages for Kokoro (`kokoro`, `misaki` and the others it installs with `==`).
- Not fixed: the revisions of the model weights and voice files downloaded from Hugging Face (the Irodori-TTS weights, its codec and text model, and Kokoro-82M with its voices). `revision` in `tools/voice/voices.yaml` is empty, so they come from the latest revision at the time of the download, and the same line rendered again after a model update may sound different. The voices in this repository are the ones rendered; render a streamer's lines again all together, not one by one, if a model changes.

We did not prepare recordings of real people as references for voice imitation in this game. The Japanese voices were designed from text descriptions alone, with no reference recording: `tools/voice/<id>.flac` is what Irodori-TTS read of `ref_text` given only `caption`, with `design_seed` as the seed and no reference audio (all three are in `tools/voice/voices.yaml`; `python3 tools/voices.py --design <id> --out <file>` makes it again; for `lise` and `mora` it gives the committed file sample for sample). Every line is then rendered with that sample as its reference audio, so that every line keeps the same voice.

SilentCipher was installed (it is a dependency in Irodori-TTS's `uv.lock`, so `uv sync --frozen` installs it) and its model loaded when the Japanese voices were rendered, so Irodori-TTS put its watermark (the payload "IRDTS") in each of them, the samples in `tools/voice/` included. The Ogg Vorbis encoding of `game/assets/voice/` weakens it: in a check of one file, SilentCipher still found a watermark, but read only part of the payload. The English voices (Kokoro-82M) have no watermark. The English voices are Kokoro's built-in voices, as Kokoro ships them.

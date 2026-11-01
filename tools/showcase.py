#!/usr/bin/env python3
"""Capture the README showcase with the go.mod-pinned Gozen (Linux/Xvfb)."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENES = ["lobby", "nox", "ella", "mora", "vespa", "pim", "lise", "lise-gyal"]
FPS, SECONDS = 6, 3


def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def main():
    for command in ("go", "xvfb-run", "ffmpeg"):
        if not shutil.which(command):
            raise SystemExit(f"Required command: {command}")
    # Keep raw frames, traces and review PNGs outside the tracked game data.
    base = ROOT / ".cache" / "showcase"
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    frames = work / "frames"
    frames.mkdir()
    source = ROOT / "game"
    original = yaml.safe_load((source / "data/streams.yaml").read_text())
    for scene in SCENES:
        print(f"Capturing {scene}", flush=True)
        folder = work / scene
        game = folder / "game"
        game.mkdir(parents=True)
        for item in source.iterdir():
            if item.name != "data":
                (game / item.name).symlink_to(item, target_is_directory=item.is_dir())
        (game / "data").mkdir()
        for item in (source / "data").iterdir():
            if item.name != "streams.yaml":
                (game / "data" / item.name).symlink_to(item)
        streams = copy.deepcopy(original)
        # Stage only the existing shows being filmed; never edit the real game.
        streams["duos"] = []
        streams["live"]["duo_chance"] = 0
        if scene != "lobby":
            ids = scene.split("-")
            streams["channels"] = [c for c in streams["channels"] if c["id"] in ids]
            if scene == "lise-gyal":
                duo = copy.deepcopy(next(d for d in original["duos"] if d["with"] == "gyal"))
                duo["unlock"] = 0
                streams["duos"] = [duo]
                streams["live"]["duo_chance"] = 1
        for channel in streams["channels"]:
            if channel.get("episodes"):
                channel["episodes"] = channel["episodes"][:1]
        (game / "data/streams.yaml").write_text(yaml.safe_dump(streams, allow_unicode=True))
        saves = folder / "saves"
        saves.mkdir()
        (saves / "config.json").write_text(json.dumps({
            "language": "en", "stream_full": True, "stream_captions_off": True,
        }))
        commands = ["gap 1", "wait 60", "type Guest", "press ok", "wait 120"]
        # Scroll the lobby to show the channel cards; other scenes open the only show.
        commands += ["press down" if scene == "lobby" else "press ok", "wait 120"]
        offset = SCENES.index(scene) * FPS * SECONDS
        for i in range(FPS * SECONDS):
            commands += [f"shot frame{offset + i:04d}", "wait 7"]
        commands += ["quit"]
        script = folder / "input.txt"
        script.write_text("\n".join(commands) + "\n")
        run("xvfb-run", "-a", "go", "tool", "gozen", "run", game,
            "--dev", "--mute", "--seed", "7", "--window", "0.5",
            "--script", script, "--shots", frames, "--save-dir", saves,
            "--trace", folder / "trace.jsonl")
    output = ROOT / "doc/img/showcase.gif"
    # A shared 256-color palette and ordered dithering limit temporal noise/size.
    run("ffmpeg", "-v", "error", "-y", "-framerate", FPS,
        "-i", frames / "frame%04d.png", "-filter_complex",
        "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
        "-loop", "0", output)
    review = work / "review"
    review.mkdir()
    # Decode the finished GIF, not the source PNGs: three frames per scene.
    for index, scene in enumerate(SCENES):
        for second in (0.5, 1.5, 2.5):
            run("ffmpeg", "-v", "error", "-y", "-i", output,
                "-ss", index * SECONDS + second, "-frames:v", "1",
                review / f"{index:02d}-{scene}-{second}.png")
    print(f"GIF: {output} ({output.stat().st_size:,} bytes, 24 seconds)")
    print(f"Review PNGs and capture scripts: {work}")


if __name__ == "__main__":
    main()

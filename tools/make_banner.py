#!/usr/bin/env python3
"""README の上部と OGP に使う横長の絵（1280x640）を作る（rabbitrun の tools/make_banner.py と同じ作り）。

背景は夜の配信サイトらしい紫からピンクの縦のグラデーションに、薄いハートを散らしたもの。
中央にハートに羽のロゴ（game/assets/logo.png）と題名「SUCCUBUS LIVE」（Lilita One、白い縁と影）を置き、
左右に6人の立ち絵（原画の assets/<id>/base.png）を3人ずつ並べる。

  python3 tools/make_banner.py               # doc/img/banner.png を作る
  python3 tools/make_banner.py --out x.png   # 別の場所に出す
書体は Lilita One（SIL OFL 1.1、tools/banner/OFL-LilitaOne.txt）。
"""
import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "tools/banner/LilitaOne-Regular.ttf"
W, H = 1280, 640
# 文字ごとの色（配信者の色に寄せたピンク・紫・赤・水色）
PALETTE = [(0xff, 0x5f, 0xa2), (0xc0, 0x6c, 0xff), (0xff, 0x8a, 0x5c), (0x5c, 0xc8, 0xff), (0xff, 0xc8, 0x3c), (0x7c, 0xe0, 0x9c)]
WORDS = [("SUCCUBUS", 112), ("LIVE", 168)]
SHADOW = (0x50, 0x18, 0x50, 0x90)
# (id, 中心の x, 高さ)。手前の人ほど後に描く
CHARS = [("nox", 95, 760), ("mora", 235, 800), ("lise", 360, 840),
         ("vespa", 1185, 760), ("ella", 1045, 800), ("pim", 920, 840)]


def background():
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(58 + 90 * t), int(20 + 18 * t), int(88 + 20 * t), 255))
    hearts = Image.new("RGBA", (W, H))
    hd = ImageDraw.Draw(hearts)
    rng = random.Random(4)
    for _ in range(70):
        cx, cy, k = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.6, 2.2)
        pts = [(cx + k * 16 * math.sin(t) ** 3, cy - k * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
               for t in (i / 40 * 2 * math.pi for i in range(41))]
        hd.polygon(pts, fill=(255, 150, 210, rng.randint(25, 60)))
    return Image.alpha_composite(bg, hearts.filter(ImageFilter.GaussianBlur(1.5)))


def title():
    """ロゴの印と題名を透明な画像に描く（文字ごとに色を変え、太い白縁と柔らかい影）。"""
    canvas = Image.new("RGBA", (W, 520))
    mark = Image.open(ROOT / "game/assets/logo.png").convert("RGBA").resize((150, 150), Image.LANCZOS)
    canvas.alpha_composite(mark, ((W - 150) // 2, 0))
    y, ci = 150, 0
    for word, size in WORDS:
        font = ImageFont.truetype(str(FONT), size)
        spacing = size * 0.04
        widths = [font.getlength(ch) for ch in word]
        x0 = W / 2 - (sum(widths) + spacing * (len(word) - 1)) / 2
        shadow = Image.new("RGBA", canvas.size)
        sd = ImageDraw.Draw(shadow)
        x = x0
        for ch, w in zip(word, widths):
            sd.text((x + size * 0.05, y + size * 0.07), ch, font=font, fill=SHADOW, stroke_width=int(size / 11), stroke_fill=SHADOW)
            x += w + spacing
        canvas = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size / 40)), canvas)
        d = ImageDraw.Draw(canvas)
        x = x0
        for ch, w in zip(word, widths):
            d.text((x, y), ch, font=font, fill=PALETTE[ci % len(PALETTE)] + (255,), stroke_width=int(size / 11), stroke_fill="white")
            x += w + spacing
            ci += 1
        y += size * 0.98
    return canvas.crop(canvas.getbbox())


def figure(pid, height):
    """立ち絵を人物の範囲で切り出し、高さ height に縮める。"""
    im = Image.open(ROOT / f"assets/{pid}/base.png").convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox())
    return im.resize((round(im.width * height / im.height), height), Image.LANCZOS)


def soft_shadow(im, blur=10, alpha=110):
    a = im.getchannel("A").point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", im.size, (30, 0, 40, 0))
    sh.putalpha(a)
    pad = blur * 3
    out = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2))
    out.paste(sh, (pad, pad))
    return out.filter(ImageFilter.GaussianBlur(blur)), pad


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=ROOT / "doc/img/banner.png")
    args = p.parse_args()
    bg = background()
    for pid, cx, h in CHARS:
        f = figure(pid, h)
        x, y = round(cx - f.width / 2), 8  # 頭の上を揃え、足元は画面の下で切る
        sh, pad = soft_shadow(f)
        bg.alpha_composite(sh, (x - pad + 10, y - pad + 8))
        bg.alpha_composite(f, (x, y))
    t = title()
    bg.alpha_composite(t, ((W - t.width) // 2, (H - t.height) // 2))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(args.out, optimize=True)
    print(args.out)


if __name__ == "__main__":
    main()

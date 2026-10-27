#!/usr/bin/env python3
"""台詞を前もって音声ファイルにする（日本語は Irodori-TTS v4.1-Small-MF、英語は Kokoro-82M。CPU で動く）。

  python3 tools/voices.py                 足りない音声を作り、消えた台詞の音声を消す（全員。二人配信の回も）
  python3 tools/voices.py --only lise     一人だけ（消すのもその人の分だけ）
  python3 tools/voices.py --dry-run       作る数・消す数と、差し込みで飛ばした数を数えるだけ
  python3 tools/voices.py --jobs 4 --threads 8   4 本並べて作る（1 本あたり 8 スレッド）
  python3 tools/voices.py --lang en       英語（game/lang/en.yaml の訳）の音声を作る（反応の本の行も。外すなら --no-book）
  python3 tools/voices.py --device gpu --jobs 1 --reverse   GPU（PyTorch の ROCm 版）で、残りを後ろから作る
      CPU の実行と同時に流してよい。作る直前にファイルがあれば飛ばすので、前と後ろから進めれば二重に作らない。
      GPU の環境に要る変数（ROCm の HSA_OVERRIDE_GFX_VERSION など）は、自分の環境に合わせて環境変数で渡す。
      書き込みは一時ファイル経由なので、途中で止めても作りかけは残らない。
  python3 tools/voices.py --design lise --out /tmp/lise.flac   声の見本を voices.yaml の caption・ref_text・design_seed から
      参照音声なしで作り直す（tools/voice/<id>.flac の作り方。見本を変えると声が変わるので、置き換えたら全部作り直す）

作り終わりに、作るはずなのに音声の無い行を数え、あれば終了コード 1 で終わる（名前などの差し込みがあって作らない行は別に数える）。

置き場と名前（gozen 側の再生と同じ決まり）：
  game/assets/voice/<話す配信者の channel id>/<hash>.ogg   Ogg Vorbis、モノラル、-q:a 2（日本語 44.1kHz で約 58kbps、英語 24kHz で約 35kbps）
      gozen は .ogg を Vorbis としてしか読まない（sound.DecodeEffect）。Opus で書いた古いファイルは「無い」と数えて作り直す。
  hash = 台詞の文字列（YAML を読んだ後の値。{from} などの差し込みを済ませる前の、ファイルに書いたままの行）を
         UTF-8 で SHA-1 し、16 進の先頭 16 文字（小文字）。正規化はしない（空白・記号もそのまま）。
  言語で置き場を分けない。英語の行は game/lang/en.yaml で訳した後の文字列（表示する英語）が鍵（gozen の db.Tr の後）。
  消す判定は言語に依らず「日本語の台詞 ∪ 英語の台詞（lang/en.yaml で引けるもの。反応の本の行も含む）」に無い hash。
  なので --lang ja で走らせても英語の音声は消えず、--lang en でも日本語の音声は消えない。

英語（--lang en）：
  上の対象の行のうち、game/lang/en.yaml の text に訳のある行を、その英語で作る（訳の無い行は作らない。数を出す）。
  gozen は本の行を表示する言語に訳してから言うので、英語の反応の本の行も既定で作る（作らないなら --no-book）。
  crowd.tip_lines（ほかの視聴者の投げ銭の文）は、ゲストを除く各配信者の声で日英とも作る（引用符を付ける前の文が鍵）。
  game/data/streams.yaml の `voices: voice` が、game/assets/ の下の置き場を指す（tools/import_stream.py が書く）。

対象の行（game/ の下を読む）：
  streams/<id>/NNN.yaml の say、ask の q と r（答えの行）。拍に who があればその人の声、無ければその回の配信者。
  data/streams.yaml の channels の greet / first / streak / stayed / bridges（回と回のつなぎ）と、duos（二人配信）の回の行。
  二人配信の回は say が主（host）の行、<channel id>: の拍がその人の行（主の id で書いた行も主）、ask は who（無ければ主）の声。
  ゲスト（guest: true のチャンネル）も声の置き場は assets/voice/<ゲストの id>/。voices.yaml に声の無い人の行は作らず、数を出す。
  assets/react.yaml の people の say・asks・dodge の行。
  {…} の差し込みを含む行は作らない（名前などが変わるので。gozen はファイルが無ければ字幕だけ）。
  chat（視聴者のコメント）、ask の選択肢 c、lobby（一覧の紹介文）は読まない。

声：tools/voice/voices.yaml（話者ごとの声の説明・参照音声・速さ）。参照音声 tools/voice/<id>.flac は
  このモデルに声の説明（caption）だけを渡し、参照音声なしで ref_text を読ませた合成の声（--design で作り直せる）で、
  実在の人の声ではない。作り直すと声が変わるので消さないこと。

初回は Irodori-TTS（コミット固定）を SUCCUBUS_VOICE_CACHE（既定 ~/.cache/succubus-live-voice/）に取ってきて uv で CPU 版の環境を作り、
その環境の Python でこのスクリプトを開き直す（uv と git と ffmpeg が要る）。GPU は --device gpu のときだけ使う。
英語は別の環境（<キャッシュ>/venv-kokoro、kokoro・misaki を版固定）を作って開き直す。
  辞書に無い語の読みに OS の espeak-ng（apt install espeak-ng、brew install espeak-ng）を使う。
  場所は環境変数 ESPEAK_NG_LIBRARY・ESPEAK_NG_DATA、無ければ voices.yaml の en.espeak、それも無ければ OS から探す。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # リポジトリのルート
GAME = ROOT / 'game'  # 台詞を読む gozen のゲーム（data/・streams/・lang/・assets/react.yaml）
VOICE_DIR = ROOT / 'tools' / 'voice'  # 声の設定（voices.yaml）と見本（<id>.flac）
OUT_DIR = GAME / 'assets' / 'voice'  # 作った音声の置き場
IRODORI_REPO = 'https://github.com/Aratako/Irodori-TTS.git'
IRODORI_COMMIT = '59be938c99d48b5653ca5aa3fdd0cddaa56940e5'  # 2026-10-25（v4.1）
CACHE = Path(os.environ.get('SUCCUBUS_VOICE_CACHE', Path.home() / '.cache' / 'succubus-live-voice'))
SLOT = re.compile(r'\{[^{}]*\}')  # {from} {days} {text} {mem.x} などの差し込み
VORBIS_Q = '2'  # libvorbis の品質。0〜3 を測って、日英約1万行・平均8秒で 600MB に収まる中で一番良い値
SAMPLE_RATE = 44100  # gozen の sound.SampleRate。これより低いモデルの出力（Kokoro の 24kHz）はそのまま（gozen が変換する）


def is_vorbis(path):
    """Ogg Vorbis か（先頭のページの識別ヘッダで見る。Opus なら OpusHead）。"""
    try:
        with open(path, 'rb') as f:
            return b'\x01vorbis' in f.read(64)
    except OSError:
        return False


def encode(wav, out, rate):
    """wav を Ogg Vorbis にして out に書く（一時ファイル経由。作りかけは残らない）。"""
    tmp = Path(out).with_suffix('.ogg.part')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), '-ac', '1', '-ar', str(min(int(rate), SAMPLE_RATE)),
                    '-c:a', 'libvorbis', '-q:a', VORBIS_Q, '-f', 'ogg', str(tmp)], check=True)
    tmp.replace(out)
LANG_EN = GAME / 'lang' / 'en.yaml'
# 英語の読み上げの環境（版を固定する。torch は CPU 版）
KOKORO_PKGS = ['kokoro==0.9.4', 'misaki[en]==0.9.4', 'soundfile==0.14.0', 'torch==2.14.1',
               'en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/'
               'en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl']
TORCH_CPU_INDEX = 'https://download.pytorch.org/whl/cpu'


def line_hash(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------- 台詞を集める

def load(p):
    import yaml
    return yaml.safe_load(Path(p).read_text(encoding='utf-8'))


class Lines:
    def __init__(self, known):
        self.known = set(known)       # 声のある channel id
        self.by = {}                  # channel id -> {hash: text}
        self.slotted = 0              # 差し込みがあって作らない行
        self.unknown = {}             # 声の無い話者 -> 行数
        self.book = {}                # channel id -> {hash: text}（反応の本の行。by にも入っている）
        self.in_book = False          # 今 add している行が反応の本の行か

    def add(self, who, text):
        if not isinstance(text, str) or not text.strip():
            return
        if SLOT.search(text):
            self.slotted += 1
            return
        if who not in self.known:
            self.unknown[who] = self.unknown.get(who, 0) + 1
            return
        h = line_hash(text)
        if self.in_book and h not in self.by.get(who, {}):  # 台本にもある行は台本の行として数える
            self.book.setdefault(who, {})[h] = text
        self.by.setdefault(who, {})[h] = text

    def adds(self, who, v):
        """文字列、文字列の並び（続けて言う行）、{text: …} のどれでも。"""
        if isinstance(v, str):
            self.add(who, v)
        elif isinstance(v, list):
            for x in v:
                self.adds(who, x)
        elif isinstance(v, dict):
            self.adds(v.get('who', who), v.get('text'))


def ask_lines(lines, who, a):
    who = a.get('who', who)
    lines.adds(who, a.get('q'))
    for o in a.get('options') or []:
        lines.adds(o.get('who', who), o.get('r'))


NOT_SPEAKERS = ('say', 'chat', 'ask', 'who')  # 拍の鍵のうち、話す人の id でないもの


def beats(lines, who, items):
    """回の parts（拍の並びの並び）を歩く。二人配信の <channel id>: 行（gozen の Beat の Speaker）はその人の声。"""
    for b in items or []:
        if isinstance(b, list):
            beats(lines, who, b)
            continue
        if not isinstance(b, dict):
            continue
        w = b.get('who', who)
        if 'say' in b:
            lines.adds(w, b['say'])
        if isinstance(b.get('ask'), dict):
            ask_lines(lines, w, b['ask'])
        for k, v in b.items():
            if k not in NOT_SPEAKERS and isinstance(v, (str, dict)):
                lines.adds(k, v if isinstance(v, str) else v.get('text'))


def episode(lines, who, rel):
    doc = load(GAME / rel)
    beats(lines, who, doc.get('parts'))


def collect(duos=False):
    data = load(GAME / 'data/streams.yaml')
    chans = data.get('channels') or []
    actor_of = {c['id']: c.get('actor', c['id']) for c in chans}
    chan_of_actor = {a: c for c, a in actor_of.items()}
    voices = load(VOICE_DIR / 'voices.yaml')['speakers']
    lines = Lines(voices)

    def ch(who):  # 台本の who は actor のことも channel id のこともある
        return chan_of_actor.get(who, who)

    for c in chans:
        cid = c['id']
        for rel in c.get('episodes') or []:
            episode(lines, cid, rel)
        for k in ('greet', 'first', 'streak', 'stayed', 'bridges'):
            lines.adds(cid, c.get(k))
        if not c.get('guest'):  # ほかの視聴者の投げ銭の文（crowd.tip_lines）は、ホストが自分の声で読む（引用符を付ける前の文が鍵）
            lines.adds(cid, (data.get('crowd') or {}).get('tip_lines'))
    for d in (data.get('duos') or []) if duos else []:  # 二人配信は --duos のときだけ（台本の確定待ち）
        # 二人配信：回の配信者（host、無ければ cast の先頭）が既定の声。相方の行は拍の who で相方の声になる
        host = d.get('host') or (d.get('cast') or d.get('with') or [None])[0]
        for rel in d.get('episodes') or []:
            sub = Lines(voices)
            episode(sub, host, rel)
            for who, m in sub.by.items():
                for h, t in m.items():
                    lines.by.setdefault(ch(who), {})[h] = t
            lines.slotted += sub.slotted
            for k, n in sub.unknown.items():
                lines.unknown[k] = lines.unknown.get(k, 0) + n
    lines.in_book = True
    book = load(GAME / 'assets/react.yaml')
    for p in book.get('people') or []:
        pid = ch(p['id'])
        for r in p.get('rules') or []:
            lines.adds(r.get('who', pid), r.get('say'))
            for a in r.get('asks') or []:
                if isinstance(a, dict):
                    ask_lines(lines, pid, a)
                else:
                    lines.adds(pid, a)
        for a in p.get('asks') or []:
            if isinstance(a, dict):
                ask_lines(lines, pid, a)
            else:
                lines.adds(pid, a)
        dodge = p.get('dodge') or {}
        lines.adds(pid, list(dodge.values()) if isinstance(dodge, dict) else dodge)
    lines.in_book = False
    return lines


def english(lines):
    """日本語の台詞を lang/en.yaml の text で英語に。(英語の行 channel id -> {hash: text}, 訳の無い行の数 channel id -> n,
    反応の本の英語の行 channel id -> {hash: text})。差し込みのある英語（訳で {…} が入った行）は作らない。"""
    table = (load(LANG_EN) or {}).get('text') or {} if LANG_EN.exists() else {}
    by, book, lacking = {}, {}, {}
    for cid, m in lines.by.items():
        for h, ja in m.items():
            en = table.get(ja)
            if not isinstance(en, str) or not en.strip() or en == ja or SLOT.search(en):
                lacking[cid] = lacking.get(cid, 0) + 1
                continue
            dst = book if h in lines.book.get(cid, {}) else by
            dst.setdefault(cid, {})[line_hash(en)] = en
    return by, lacking, book


# ---------------------------------------------------------------- 読み上げの環境

def bootstrap(argv, device):
    """Irodori-TTS の環境が無ければ作り、その Python で開き直す（CPU 版と ROCm 版は別の環境）。"""
    try:
        import irodori_tts  # noqa: F401
        return
    except ImportError:
        pass
    src = CACHE / 'Irodori-TTS'
    venv = CACHE / ('venv' if device == 'cpu' else 'venv-rocm')
    py = venv / 'bin' / 'python'
    if not src.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', IRODORI_REPO, str(src)], check=True)
    head = subprocess.run(['git', '-C', str(src), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    if head != IRODORI_COMMIT:
        subprocess.run(['git', '-C', str(src), 'fetch', 'origin'], check=True)
        subprocess.run(['git', '-C', str(src), 'checkout', '--detach', IRODORI_COMMIT], check=True)
    if not py.exists() or head != IRODORI_COMMIT:
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(venv))
        subprocess.run(['uv', 'sync', '--frozen', '--extra', 'cpu' if device == 'cpu' else 'rocm', '--project', str(src)],
                       check=True, env=env)
    # GPU の環境に要る変数（HSA_OVERRIDE_GFX_VERSION など）は、呼ぶ人が環境変数で渡す（ここでは足さない）
    env = dict(os.environ, PYTHONPATH=str(src))
    os.execve(str(py), [str(py), str(Path(__file__).resolve()), *argv], env)


def bootstrap_en(argv):
    """Kokoro-82M の環境が無ければ作り、その Python で開き直す（日本語の Irodori の環境とは別）。"""
    try:
        import kokoro  # noqa: F401
        import misaki  # noqa: F401
        return
    except ImportError:
        pass
    venv = CACHE / 'venv-kokoro'
    py = venv / 'bin' / 'python'
    if not py.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['uv', 'venv', '--python', '3.12', str(venv)], check=True)
    subprocess.run(['uv', 'pip', 'install', '--python', str(py), '--extra-index-url', TORCH_CPU_INDEX,
                    '--index-strategy', 'unsafe-best-match', *KOKORO_PKGS], check=True)
    os.execve(str(py), [str(py), str(Path(__file__).resolve()), *argv], dict(os.environ))


def reading(text, table):
    """表示の文字列を、読み上げに渡す文字列に（tools/voice/voices.yaml の readings）。ハッシュは表示の文字列のまま。"""
    for a, b in table:
        text = text.replace(a, b)
    return text


ONE_READING = re.compile(r'\[([^\[\]]+)\]\(/([^/]+)/\)')


def reading_en(text, table):
    """英語の readings：語の単位で、大文字小文字を区別せずに置き換える（Nox が Noxious の中で変わらないように）。
    読みは misaki の [語](/IPA/)。置き換えた後の [ ] の中は置き換えない（Kinoko no Yama の後に Kinoko を書いてよい）。
    「Harumi's」のような所有の 's は、読みが一語のとき /…z/（s・ʃ などの後は ɪz、無声音の後は s）を足して一語にする。"""
    def sub(b):
        def f(m):
            one = ONE_READING.fullmatch(b)
            if m.group(2) and one:
                ipa = one.group(2)
                end = 'ɪz' if ipa[-1] in 'szʃʒʧʤ' else 's' if ipa[-1] in 'ptkfθ' else 'z'
                return f'[{m.group(1)}{m.group(2)}](/{ipa}{end}/)'
            return (ONE_READING.sub(lambda o: f'[{m.group(1)}](/{o.group(2)}/)', b) if one else b) + (m.group(2) or '')
        return f
    for a, b in table:
        text = re.sub(r'(?<![\w\[])(' + re.escape(a) + r")('s)?(?![\w\]])", sub(b), text, flags=re.I)
    text = text.replace('/)-[', '/) [')  # Karaage-kun のように読みが続くときの - は読まない（misaki の辞書に無い記号）
    return re.sub(r'\s{2,}', ' ', text).strip()


def espeak_paths(conf):
    """OS の espeak-ng のライブラリとデータの場所。環境変数 ESPEAK_NG_LIBRARY・ESPEAK_NG_DATA、voices.yaml の en.espeak、
    OS から探した場所の順に、在るものを使う。見つからなければ ('', '')。"""
    import ctypes
    import ctypes.util
    import glob
    es = conf.get('espeak') or {}
    libs = [os.environ.get('ESPEAK_NG_LIBRARY'), es.get('library'), ctypes.util.find_library('espeak-ng'),
            *glob.glob('/usr/lib/*/libespeak-ng.so.1'), '/usr/lib/libespeak-ng.so.1',
            '/opt/homebrew/lib/libespeak-ng.dylib', '/usr/local/lib/libespeak-ng.dylib']
    datas = [os.environ.get('ESPEAK_NG_DATA'), es.get('data'), *glob.glob('/usr/lib/*/espeak-ng-data'),
             '/usr/share/espeak-ng-data', '/opt/homebrew/share/espeak-ng-data', '/usr/local/share/espeak-ng-data']
    def loadable(x):
        try:
            ctypes.CDLL(x)
            return True
        except OSError:
            return False
    lib = next((x for x in libs if x and loadable(x)), '')
    data = next((x for x in datas if x and Path(x).is_dir()), '')
    return (lib, data) if lib and data else ('', '')


def worker_en(args):
    """英語の作り手：Kokoro-82M（米国英語 a と英国英語 b のパイプラインで一つのモデルを共有）。"""
    jobs, threads, conf = args
    import torch
    import soundfile as sf
    import misaki.espeak
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    # misaki の辞書に無い語（Metallica、daycare など）は espeak-ng で読む。espeakng_loader の同梱の espeak-ng-data は
    # 作った時の場所を指していて読めないので、OS の espeak-ng（apt の espeak-ng）を使う。無ければ辞書に無い語は無音になる。
    lib, data = espeak_paths(conf)
    if lib and data:
        EspeakWrapper.set_library(lib)
        EspeakWrapper.set_data_path(data)
    else:
        print('注意: espeak-ng が見つからない（ESPEAK_NG_LIBRARY・ESPEAK_NG_DATA で場所を渡せる）。辞書に無い語は読まれない', flush=True)

        def no_fallback(**_):
            raise RuntimeError('espeak-ng is not available')
        misaki.espeak.EspeakFallback = no_fallback
    from kokoro import KPipeline
    torch.set_num_threads(threads)
    repo = conf['model']
    pa = KPipeline(lang_code='a', repo_id=repo)
    pb = KPipeline(lang_code='b', repo_id=repo, model=pa.model)
    done = []
    for cid, h, text, out in jobs:
        if is_vorbis(out):
            continue
        sp = conf['speakers'][cid]
        pipe = pb if sp['voice'].startswith('b') else pa
        t0 = time.time()
        parts = [r.audio for r in pipe(reading_en(text, conf['readings']), voice=sp['voice'], speed=float(sp.get('speed', 1.0)))
                 if r.audio is not None]
        if not parts:
            print(json.dumps({'id': cid, 'hash': h, 'skip': 'no audio', 'text': text}, ensure_ascii=False), flush=True)
            continue
        audio = torch.cat(parts).numpy()
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / 'a.wav'
            sf.write(str(wav), audio, 24000)
            encode(wav, out, 24000)
        dur = len(audio) / 24000
        done.append((time.time() - t0, dur))
        print(json.dumps({'id': cid, 'hash': h, 'sec': round(time.time() - t0, 2), 'dur': round(dur, 2), 'text': text},
                         ensure_ascii=False), flush=True)
    return done


def worker(args):
    """一本の作り手：モデルを読み、受け取った行を順に作る。"""
    jobs, threads, conf = args
    import torch
    from huggingface_hub import hf_hub_download
    from irodori_tts.inference_runtime import InferenceRuntime, RuntimeKey, SamplingRequest, save_wav
    torch.set_num_threads(threads)
    path = hf_hub_download(conf['model'], 'model.safetensors', revision=conf.get('revision'))
    rt = InferenceRuntime.from_key(RuntimeKey(checkpoint=path, model_device=conf['device'], codec_device=conf['device']))
    done = []
    for cid, h, text, out in jobs:
        if is_vorbis(out):  # ほかの実行（CPU と GPU を同時に流したとき）が先に作った
            continue
        sp = conf['speakers'][cid]
        t0 = time.time()
        r = rt.synthesize(SamplingRequest(
            text=reading(text, conf['readings']), caption=sp['caption'], ref_wav=str(VOICE_DIR / sp['ref']),
            seed=int(h[:8], 16), duration_scale=float(sp.get('duration_scale', 1.0))), log_fn=None)
        with tempfile.TemporaryDirectory() as td:
            wav = save_wav(Path(td) / 'a.wav', r.audio, r.sample_rate)
            encode(wav, out, r.sample_rate)
        dur = r.audio.shape[-1] / r.sample_rate
        done.append((time.time() - t0, dur))
        print(json.dumps({'id': cid, 'hash': h, 'sec': round(time.time() - t0, 2), 'dur': round(dur, 2), 'text': text},
                         ensure_ascii=False), flush=True)
    return done


def design(cid, out, device):
    """声の見本を作る：voices.yaml の caption だけで（参照音声なし）、ref_text を design_seed で読ませ、out に書く（flac か wav）。"""
    import torch
    from huggingface_hub import hf_hub_download
    from irodori_tts.inference_runtime import InferenceRuntime, RuntimeKey, SamplingRequest, save_wav
    conf = load(VOICE_DIR / 'voices.yaml')
    sp = conf['speakers'][cid]
    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    dev = 'cpu' if device == 'cpu' else 'cuda'
    path = hf_hub_download(conf['model'], 'model.safetensors', revision=conf.get('revision'))
    rt = InferenceRuntime.from_key(RuntimeKey(checkpoint=path, model_device=dev, codec_device=dev))
    r = rt.synthesize(SamplingRequest(text=sp['ref_text'], caption=sp['caption'], no_ref=True, seed=int(sp['design_seed'])),
                      log_fn=None)
    with tempfile.TemporaryDirectory() as td:
        wav = save_wav(Path(td) / 'a.wav', r.audio, r.sample_rate)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav), str(out)], check=True)
    print(out)


def missing(ids, want_of, intended):
    """作るはずなのに音声の無い行を出し、その数を返す。intended は差し込み・読みが空で作らない行の数（失敗にしない）。"""
    lack = []
    for cid in ids:
        for h, text in sorted(want_of(cid).items()):
            if not is_vorbis(OUT_DIR / cid / f'{h}.ogg'):
                lack.append((cid, h, text))
    print(f'音声の無い行：差し込みなどで作らない行 {intended}（意図どおり）、作るはずなのに無い行 {len(lack)}')
    for cid, h, text in lack[:50]:
        print(f'  無い: {cid}/{h}.ogg {text[:40]}')
    if len(lack) > 50:
        print(f'  …ほか {len(lack) - 50} 行')
    return len(lack)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--only', action='append', help='この channel id だけ（何度でも）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--jobs', type=int, default=4, help='並べる本数（既定 4）')
    ap.add_argument('--threads', type=int, default=0, help='1 本あたりのスレッド（既定 (CPU 数 - 8) / jobs）')
    ap.add_argument('--device', choices=['cpu', 'gpu'], default='cpu', help='gpu は AMD ROCm（既定 cpu）')
    ap.add_argument('--reverse', action='store_true', help='後ろから作る（CPU と GPU を同時に流すとき、片方に付ける）')
    ap.add_argument('--limit', type=int, default=0, help='作る数の上限（試し用）')
    ap.add_argument('--duos', action='store_true', default=True, help='二人配信の回の行も作る（既定）')
    ap.add_argument('--no-duos', dest='duos', action='store_false', help='二人配信の回の行を作らない（台本を書いている途中のとき）')
    ap.add_argument('--duos-only', action='store_true', help='二人配信の回の行だけ作る（一人配信の台本を直している人の、二人配信の分だけ先に作るとき）')
    ap.add_argument('--lang', choices=['ja', 'en'], default='ja', help='作る言語（既定 ja）。消す判定は両方の和')
    ap.add_argument('--no-book', dest='book', action='store_false', help='--lang en で反応の本の行を作らない（既定は作る。gozen は本の行を訳してから言う）')
    ap.add_argument('--design', metavar='ID', help='声の見本を voices.yaml の caption から作り直す（--out に書く）')
    ap.add_argument('--out', type=Path, help='--design の書き先（.flac か .wav）')
    a = ap.parse_args()
    if a.design:
        if not a.out:
            ap.error('--design には --out が要る')
        bootstrap(sys.argv[1:], a.device)
        design(a.design, a.out, a.device)
        return
    if a.duos_only:
        a.duos = True

    lines = collect(duos=a.duos)
    en_by, en_lacking, en_book = english(lines)
    # 消す判定は二人配信の行も含めた全部で（--duos なしで流しても、作った二人配信の音声を消さない）
    every = lines if a.duos else collect(duos=True)
    if a.duos_only:
        base = collect(duos=False)
        b_by, _, b_book = english(base)
        base_en = {c: {**b_by.get(c, {}), **b_book.get(c, {})} for c in set(b_by) | set(b_book)}  # 一人配信の行と反応の本の英語
    ev_by, _, ev_book = english(every) if not a.duos else (en_by, None, en_book)
    full = load(VOICE_DIR / 'voices.yaml')
    if a.lang == 'en':
        conf = dict(full['en'])
        conf['readings'] = [tuple(x) for x in conf.get('readings') or []]
        say = lambda t: reading_en(t, conf['readings'])  # noqa: E731
    else:
        conf = full
        conf['readings'] = [tuple(x) for x in conf.get('readings') or []]
        say = lambda t: reading(t, conf['readings'])  # noqa: E731
    if a.only:  # 声のある話者の id だけ（パスや打ち間違いで game/assets/voice/ の外や別の置き場を消さない）
        known = set(full['speakers'])
        bad = [x for x in a.only if x not in known]
        if bad:
            ap.error(f'--only に知らない id: {bad}（tools/voice/voices.yaml の speakers: {sorted(known)}）')
    ids = a.only or sorted(set(lines.by) | set(en_by) | set(en_book))
    todo, stale, wants = [], [], {}
    for cid in ids:
        ja_want = lines.by.get(cid, {})
        en_want = {**en_by.get(cid, {}), **en_book.get(cid, {})}
        # 消す判定は言語に依らず日英の和（片方の言語で走らせても、もう片方の音声を消さない）
        keep = set(ja_want) | set(en_want) | set(every.by.get(cid, {})) | set(ev_by.get(cid, {})) | set(ev_book.get(cid, {}))
        if a.lang == 'en':
            want = dict(en_by.get(cid, {}))
            if a.book:
                want.update(en_book.get(cid, {}))
        else:
            want = ja_want
        if a.duos_only:  # 二人配信にだけある行
            solo = base.by.get(cid, {}) if a.lang == 'ja' else {**base_en.get(cid, {})}
            want = {h: t for h, t in want.items() if h not in solo}
        wants[cid] = {h: t for h, t in want.items() if say(t).strip()}  # 読みを置き換えると空になる行（「ｗｗｗ」だけ等）は作らない
        d = OUT_DIR / cid
        files = {p.stem: p for p in d.glob('*.ogg')} if d.exists() else {}
        have = {h for h, p in files.items() if is_vorbis(p)}  # Opus の古いファイルは無いのと同じ（作り直す）
        stale += [d / f'{h}.ogg' for h in sorted(set(files) - keep)]
        todo += [(cid, h, want[h], str(d / f'{h}.ogg')) for h in sorted(set(want) - have)]
        if a.lang == 'en':
            n_ja = len(set(ja_want) - set(lines.book.get(cid, {})))
            print(f'{cid}: 台詞 {n_ja}（反応の本を除く）、訳あり {len(en_by.get(cid, {}))}、本の英語 {len(en_book.get(cid, {}))}'
                  f'{"（作る）" if a.book else "（作らない）"}、ある {len(have & set(want))}、作る {len(set(want) - have)}、'
                  f'消す {len(have - keep)}（残す＝日本語 {len(ja_want)} ∪ 英語 {len(en_want)} の {len(keep)}）')
        else:
            print(f'{cid}: 台詞 {len(want)}、ある {len(have & set(want))}、作る {len(set(want) - have)}、'
                  f'消す {len(have - keep)}（英語の音声 {len(have & set(en_want) - set(ja_want))} は残す）')
    print(f'差し込みがあって作らない行: {lines.slotted}')
    if a.lang == 'en':
        print(f'英語の訳が無くて作らない行（反応の本を含む）: {sum(en_lacking.get(c, 0) for c in ids)}')
    if lines.unknown:
        print(f'声の決まっていない話者（作らない）: {lines.unknown}')
    # 読みを置き換えると空になる行（「ｗｗｗ」だけ等）は作らない
    todo = [t for t in todo if say(t[2]).strip()]
    if a.reverse:
        todo.reverse()
    if a.limit:
        todo = todo[:a.limit]
    conf['device'] = 'cpu' if a.device == 'cpu' else 'cuda'
    if a.dry_run:
        return
    out_root = OUT_DIR.resolve()
    for p in stale:
        if p.resolve().parent.parent != out_root:  # 念のため：置き場の <id>/ の直下のものだけ消す
            sys.exit(f'{p} は {OUT_DIR} の下ではないので消さない')
        p.unlink()
    for p in OUT_DIR.glob('*/*.ogg.part'):  # 止めた実行の作りかけ（同時に流している実行のものは消さない）
        if time.time() - p.stat().st_mtime > 3600:
            p.unlink()
    if not todo:
        sys.exit(1 if missing(ids, wants.get, lines.slotted) else 0)
    if a.lang == 'en':
        bootstrap_en(sys.argv[1:])
        a.device = 'cpu'  # Kokoro は CPU で十分速い
    else:
        bootstrap(sys.argv[1:], a.device)
    for cid in {t[0] for t in todo}:
        (OUT_DIR / cid).mkdir(parents=True, exist_ok=True)
    if a.device == 'gpu':  # GPU は 1 本で十分。複数本は VRAM を食うだけ
        a.jobs = 1
    jobs = max(1, min(a.jobs, len(todo)))
    # 既定では 8 コアをほかの仕事に残す（--threads で変える）
    threads = a.threads or (2 if a.device == 'gpu' else max(1, ((os.cpu_count() or 8) - 8) // jobs))
    chunks = [todo[i::jobs] for i in range(jobs)]
    t0 = time.time()
    if jobs == 1:
        res = [(worker_en if a.lang == 'en' else worker)((chunks[0], threads, conf))]
    else:
        import multiprocessing as mp
        with mp.get_context('spawn').Pool(jobs) as pool:
            res = pool.map(worker_en if a.lang == 'en' else worker, [(c, threads, conf) for c in chunks])
    wall = time.time() - t0
    dur = sum(d for r in res for _, d in r)
    n = sum(len(r) for r in res)
    size = sum(Path(t[3]).stat().st_size for t in todo if Path(t[3]).exists())
    print(f'作った {n} 行、音声 {dur / 3600:.2f} 時間、かかった {wall / 3600:.2f} 時間（実時間比 {wall / max(dur, 1e-9):.2f}）、'
          f'{size / 1e6:.1f} MB')
    if a.limit:  # 試しに一部だけ作ったときは、残りがあって当然なので失敗にしない
        return
    sys.exit(1 if missing(ids, wants.get, lines.slotted) else 0)


if __name__ == '__main__':
    main()

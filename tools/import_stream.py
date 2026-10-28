#!/usr/bin/env python3
"""src/ と assets/<id>/ から、gozen のゲーム game/ のデータを作り直す。

  書くのは game/ の下だけ（リポジトリの src/・assets/・data/ には書かない・消さない）。
  game/game.yaml、game/assets/fonts/、game/assets/voice/（tools/voices.py が作る）、game/assets/logo.png、game/assets/og-image.jpg（リンクのカードの絵）は手で置くもので、ここでは消さない。
  ここで書くもの（手で直さない。直すなら src/ を直して流し直す）：
    game/data/cast.yaml             話すだけの人物（6人とゲスト）
    game/data/streams.yaml          配信の決まりとチャンネル（gozen の ADR 0048 の形）。ゲスト（src/cast.yaml の guest: true）は
                                    guest: true のチャンネル（一人配信・カード・部屋・回を持たず、二人配信の with にだけなる）
    game/streams/<id>/NNN.yaml      配信の回
    game/streams/<主>-<相手>/NNN.yaml  二人配信の回（src/duo/<主>-<相手>/。data/streams.yaml の duos に組と回を書く）
    game/assets/react.yaml          反応の本（共通の判定の語彙は全員で共通、各人の決まり）
    game/assets/<id>/puppet.yaml    立ち絵（parts.json の矩形と cast.yaml の rig から）と、その絵。
                                    assets/<id>/ に絵（parts.json・base.png…）がまだ無い人は、
                                    仮の立ち絵 game/assets/<id>/placeholder_base.png（ここで描く人影）と、全部の表情を素の顔にした puppet.yaml
    game/assets/<id>/room.jpg       その人の配信部屋
    game/lang/en.yaml               英語（gozen の言語の表「日本語の原文 → 英語」、ADR 0027）：名前と共通の言葉、
                                    src/en/ の回（二人配信は src/en/duo/）と voice の英訳（組は tools/build.py の en_pairs・voice_pairs で作る）。
                                    同じ日本語に別の英語があれば食い違いとして出し、最初の訳を使う
    game/LICENSE, game/NOTICE.txt   リポジトリの LICENSE と NOTICE.md をそのまま写す（gozen export はゲームの直下の
                                    LICENSE・NOTICE.txt を書き出しに入れる。NOTICE.md は拾わない）

「試作」は、src/ と assets/ とブラウザの下書き（index.html・app.js）のこと（このゲームの前に作った HTML/JS 版）。

使い方:
  python3 tools/import_stream.py [入力のフォルダ]          作り直す（入力の既定はリポジトリのルート：その src/ と assets/<id>/ を読む）
  python3 tools/import_stream.py --compare [入力のフォルダ]  src/ の正規表現と、作った語彙の当たり方を比べる
  python3 tools/import_stream.py --conflicts               作り直し、英訳の食い違いを全部出す
"""
import itertools
import re
import shutil
import struct
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # リポジトリのルート
SRC = ROOT  # 入力の既定（src/ と assets/<id>/ を読む）。引数で別のフォルダを渡せる
GAME = ROOT / 'game'  # 出力。消す・書くのはこの下だけ
IDS = ['lise', 'mora', 'pim', 'ella', 'nox', 'vespa']
FACES = ['smile', 'smug', 'shy', 'surprised', 'annoyed', 'sad', 'angry', 'laugh', 'sleepy', 'thinking', 'flustered']
# 絵がまだ無い表情を台本が使ったときに代わりに出す表情（絵のある全員の絵がそろえば使われない）
STAND_IN = {'sad': 'shy', 'angry': 'annoyed', 'laugh': 'smile', 'sleepy': 'shy', 'thinking': 'smug', 'flustered': 'surprised'}
DRAWN = set(FACES)  # 絵のある全員（仮の立ち絵の人を除く）に絵がある表情。build で決める
# 二人配信の答えの返し（ask の options の r）で、聞いた人（ask.who）でない人が言う行。gozen の r は文字列だけで、
# 話す人を書けない（全部 ask.who が言う）ので、書き出さずに数えて出す。英訳の表にも入れない。build で集める
DROPPED = []  # (回のファイル, 聞いた人, 話す人, 行)
TIPS = [500, 2000, 10000, 50000]
# 試作 app.js の値
TIMING = {'say': 2.0, 'per_char': 0.14, 'chat': 1.6, 'ask': 12}  # 喋る速さ（1文字0.14秒）に合わせた。1.8/0.11 は「字幕早い」
# 全員いつも配信中（2026-10-27「これなら全員オンラインでもいいかな。常に」）。
# duo_chance 0.25：解禁した二人配信が、枠の切り替わり（slot.rest）や開いたときに二人の一人配信に代わって流れる確率。
#   試作 app.js と同じ値のまま（両方が配信中の組が 4 回に 1 回だけ二人になる。一人配信が主で、二人の回は時々の出来事）。
#   今は組ごとに回が 1 本ずつしかないので、上げると同じ回に何度も当たる。回が増えてから見直す。
LIVE = {'share': 1.0, 'min_share': 1.0, 'duo_chance': 0.25}
# 二人配信の解禁：組の各ホストの一人配信を何分見たら流れ始めるか（ゲストの組は主の一人配信だけ）。全部の組で同じ 30 分。
#   gozen の既定と同じ値だが、決めた値として duos の各組に unlock: 30 と書く（既定が変わっても動かないように）。
#   30 分は 1 枠（slot.minutes 60）の半分：一人配信をひと枠の半分ほど見て、その人を知ってから二人の回に出会う。
#   組ごとに変える理由がまだ無いので全部同じ（2026-10-27 の指示）。
DUO_UNLOCK = 30
AWAY = {'per_hour': 1500, 'cap_hours': 24, 'star_bonus': 0.1}
CROWD_RATE = 0.34  # 雑談は 1.2〜4.7 秒おき（平均 2.95 秒）
BOUNCE_ON = '[！!]|[wｗ]{2}|草'
BOUNCE_AMOUNT = 1.0  # 1.3 は「揺れが激しい」（2026-10-27 夜）
LOGO = 'logo.png'  # 上の帯の題名の前の印（assets/ の下。手で置く絵で、ここでは作らない）
VOICES = 'voice'  # 台詞の音声の置き場（assets/ の下）。中身は tools/voices.py が作る：<channel id>/<台詞の SHA-1 の先頭16桁>.ogg
# 一覧の場所。設定の画面は置かない（ゲームではないので。言語は上の帯のボタン、読み上げは配信の画面のボタンで切り替える）
LOBBY = {'name': '配信一覧', 'stream': 'lobby'}


# ---------------------------------------------------------------- YAML を書く

def q(s):
    """文字列ひとつを YAML の値に（要るときだけ引用符）。"""
    return yaml.safe_dump(s, allow_unicode=True, width=1 << 20, default_style=None).removesuffix('\n...\n').rstrip('\n')


def flow(v):
    """短い値を一行の flow 形式に。"""
    if isinstance(v, list):
        return '[' + ', '.join(flow(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k}: {flow(x)}' for k, x in v.items()) + '}'
    if isinstance(v, str):
        s = q(v)
        # flow の中で読み違える素の文字列（, ] ? など）には引用符を付ける
        try:
            if yaml.safe_load(f'[{s}]') == [v]:
                return s
        except yaml.YAMLError:
            pass
        return yaml.safe_dump(v, allow_unicode=True, default_style='"', width=1 << 20).strip()
    return q(v)


def dump(obj):
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=1 << 20, default_flow_style=None)


def write(rel, text):
    p = GAME / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')


def load(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def from_name(x):
    """試作の {name}（呼ばれる人）を、gozen の {from} に。"""
    if isinstance(x, str):
        return x.replace('{name}', '{from}')
    if isinstance(x, list):
        return [from_name(v) for v in x]
    if isinstance(x, dict):
        return {k: from_name(v) for k, v in x.items()}
    return x


# ---------------------------------------------------------------- 回

def answer_line(r, who, where):
    """答えの返しの一行。試作では {話す人: 行} で別の人にも言わせられるが、gozen の r は聞いた人（who）の行だけなので、
    聞いた人の行は文字列にし、別の人の行は書かずに DROPPED に数える（None を返す）。"""
    if isinstance(r, dict):
        (spk, text), = r.items()
        if spk != who:
            DROPPED.append((where, who, spk, from_name(str(text))))
            return None
        r = text
    return q(from_name(str(r)))


def beat_lines(b, host, where):
    """拍ひとつを YAML の行に（先頭は '- '）。host はその回の配信者（二人配信なら主）。
    say と話す人の id（二人配信の <channel id>: 行）、表情、chat、ask はそのまま通す。"""
    (k, v), = b.items()
    if k == 'chat':
        return [f'- chat: {flow([str(x) for x in v])}']
    if k == 'ask':
        who = v.get('who', host)
        out = ['- ask:']
        if 'who' in v:
            out.append(f'    who: {v["who"]}')
        out += [f'    q: {q(v["q"])}', '    options:']
        for o in v['options']:
            rs = [x for x in (answer_line(r, who, where) for r in o['r']) if x is not None]
            out.append(f'    - c: {q(str(o["c"]))}')
            out += ['      r:'] + [f'      - {x}' for x in rs] if rs else ['      r: []']
        out.append(f'    npc: {flow(v["npc"])}')
        return out
    if isinstance(v, dict):
        face = v['face'] if v['face'] in DRAWN else STAND_IN.get(v['face'])
        if face not in DRAWN:
            return [f'- {k}: {q(str(v["text"]))}']
        return [f'- {k}: {flow({"face": face, "text": str(v["text"])})}']
    return [f'- {k}: {q(str(v))}']


def episode(src, host, where):
    """回のファイルひとつ。host はその回の配信者（二人配信なら主）、where は書き出す先（注意の出所）。"""
    doc = load(src)
    out = [f'title: {q(doc["title"])}']
    if doc.get('family'):  # 子どもが出る回。gozen はこの回の間、コメントの刺激に value.family = 1 を入れる
        out.append('family: true')
    if doc.get('lobby'):
        out.append('lobby:')
        out += [f'- {q(x)}' for x in doc['lobby']]
    out.append('parts:')
    for p in doc['parts']:
        out.append(f'# {p["title"]}')  # 見出しは書き手の目印（画面には出ない）
        lines = [ln for b in p['beats'] for ln in beat_lines(b, host, where)]
        out.append('- ' + lines[0])
        out += ['  ' + ln for ln in lines[1:]]
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- 正規表現 → 語彙

class Rx:
    """試作の反応の正規表現（使っている範囲だけ）を、語の並びに開く。

    words: [(語, whole)]  whole は前後が \\b の英字の語
    excepts: 否定の先読み・後読みを語に付けた、打ち消す語
    """

    def __init__(self, pat):
        self.s, self.i = pat, 0

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ''

    def alts(self):
        out = [self.seq()]
        while self.peek() == '|':
            self.i += 1
            out.append(self.seq())
        return out

    def seq(self):
        items = []
        while self.peek() not in ('', '|', ')'):
            items.append(self.atom())
        return items

    def atom(self):
        c = self.s[self.i]
        self.i += 1
        if c == '(':
            kind = 'group'
            for pre, k in (('?<!', 'behind'), ('?!', 'ahead'), ('?:', 'group')):
                if self.s.startswith(pre, self.i):
                    self.i += len(pre)
                    kind = k
                    break
            body = self.alts()
            assert self.s[self.i] == ')', self.s
            self.i += 1
            item = (kind, body)
        elif c == '[':
            j = self.s.index(']', self.i)
            item = ('group', [[('lit', ch)] for ch in self.s[self.i:j]])
            self.i = j + 1
        elif c == '\\':
            e = self.s[self.i]
            self.i += 1
            item = ('edge', None) if e == 'b' else ('lit', e)
        elif c == '.':
            item = ('any', None)
        else:
            item = ('lit', c)
        if self.peek() == '?':
            self.i += 1
            item = ('opt', item)
        return item


def strings(items):
    """lookaround を除いた並びを、取りうる文字列の一覧に開く。"""
    parts = []
    for it in items:
        k, v = it
        if k == 'lit':
            parts.append([v])
        elif k == 'group':
            parts.append([s for alt in v for s in strings(alt)])
        elif k == 'opt':
            inner = strings([v]) if v[0] != 'any' else ['']
            parts.append([''] + [s for s in inner if s])
        elif k == 'any':
            parts.append([''])  # 区切りの一文字（正規化で消える）
        else:
            parts.append([''])
    return [''.join(p) for p in itertools.product(*parts)]


def expand(pat):
    """正規表現ひとつを (words, excepts) に。"""
    words, excepts = [], []
    for alt in Rx(pat).alts():
        bare = [it for it in alt if it[0] not in ('behind', 'ahead')]
        trail = bool(bare) and bare[-1][0] == 'edge'
        behind = [s for k, v in alt if k == 'behind' for a in v for s in strings(a)]
        if alt and alt[0][0] == 'behind' and len(alt) > 1 and alt[1][0] == 'edge':
            # (?<!sus)\bsex：英字で終わる後読みの後の \b は、語としての一致がもう打ち消している
            behind = [s for s in behind if not s[-1:].isalnum()]
        ahead = [s for k, v in alt if k == 'ahead' for a in v for s in strings(a)]
        core = [it for it in alt if it[0] not in ('behind', 'ahead', 'edge')]
        # 前だけ \b（\btoddler）は複数形などを落とさないよう部分一致のまま。後ろに \b があれば語として
        for w in strings(core):
            # C++ や 0.1 は正規化で短くなり、何にでも当たるので語として
            words.append((w, trail or (len(norm(w)) < 3 and w.isascii())))
            for b in behind:
                excepts.append(b + w)
            for a in ahead:
                excepts.append(w + a)
    seen, ws = set(), []
    for w, wh in words:
        key = (w.lower() if wh else norm(w), wh)
        if key not in seen:
            seen.add(key)
            ws.append((w, wh))
    # 正規化で語と同じになる打ち消し（エラ(?!ー) の「エラー」）は、語ごと消してしまうので書かない
    plain = {norm(w) for w, wh in ws}
    ex = sorted({norm(e) for e in excepts} - plain)
    return ws, ex


def norm(s):
    """gozen の react.Normalize と同じ畳み方。"""
    out, last, run = [], '', 0
    for ch in s:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            ch = chr(o - 0xFEE0)
        elif 0xFF61 <= o <= 0xFF9F:
            ch = unicodedata.normalize('NFKC', ch)
        if 'ァ' <= ch <= 'ヶ':
            ch = chr(ord(ch) - ord('ァ') + ord('ぁ'))
        if ch in 'ー〜~・' or ch.isspace() or unicodedata.category(ch)[0] in 'PS':
            continue
        ch = ch.lower()
        run = run + 1 if ch == last else 1
        last = ch
        if run <= 2:
            out.append(ch)
    return ''.join(out)


def lex_entry(words, excepts):
    ws = [{'word': w, 'whole': True} if wh else w for w, wh in words]
    return {'words': ws, 'except': excepts} if excepts else ws


def slug(pat, used, owner):
    """語彙の名前：最初の英字の語から。無ければ持ち主と番号。"""
    m = re.search(r'[A-Za-z][A-Za-z0-9]{2,}(?:[ _-]?[A-Za-z0-9]+)*', pat.replace('\\b', ' '))
    base = re.sub(r'[^a-z0-9]+', '_', m.group().lower()).strip('_') if m else f'{owner}_word'
    name, n = base, 2
    while name in used:
        name = f'{base}_{n}'
        n += 1
    return name


# ---------------------------------------------------------------- 反応の本

def say_value(alts):
    """試作の alts（返しの候補。各候補は台詞の並び）を、本の say に。"""
    return [a[0] if len(a) == 1 else a for a in from_name(alts)]


def shared_tags(src):
    """試作の src/tags.yaml（{組: {名前: 正規表現}}）を {名前: 正規表現} に。"""
    return {k: str(v) for g in load(src / 'src/tags.yaml').values() for k, v in g.items()}


# 未成年と申告した視聴者（minor の反応が remember: {minor: 1} で覚える）か、子どもが出る回（回の family: true が
# コメントの刺激の value.family になる）なら、下ネタ（src/tags.yaml の lewd の組）の反応は性的でない断りにする。
# 各人の voice には書かず、ここで lewd の組の反応すべての前に足す。台詞は voice の safe_refusal（無ければ common.yaml の generic.safe_refusal）
SAFE_WHEN = '(mem.minor == "1" || value.family == 1)'


def lewd_tags(src):
    return set(load(src / 'src/tags.yaml').get('lewd') or {})


# 覚える値（remember）は言語に依らない id にする（2026-10-27）。試作の voice は remember: {kinoko_takenoko: きのこ} と
# 日本語の値で書くが、その値をそのまま覚えると、英語の台詞の {mem.kinoko_takenoko} にも「きのこ」が入る。
# そこで本では、値をその反応の tag の名前（kinoko など。src/tags.yaml の名前）にして覚え、cases の mem の条件も id で比べる。
# 台詞の {mem.鍵} は、その鍵の値ごとの cases に開き、値の言葉を書き込んだ台詞にする（日本語は voice の値、英語は
# src/en/common.yaml の remember_values の id → 英語）。表示は今までと同じ文になり、英語は言語の表で訳せる。
# 前の版の保存（日本語の値で覚えたもの）にも当たるよう、条件は id と日本語の値の両方で比べる。
MEM_IDS = {}  # (鍵, 試作の値) -> id。book の始めに mem_ids で決める


def mem_ids(src):
    """6人の voice の remember の、文字列の値を id（その反応の tag）に。同じ (鍵, 値) が別の tag なら止める。"""
    out = {}
    for pid in IDS:
        for kw in load(src / f'src/voice/{pid}.yaml')['keywords']:
            for k, v in (kw.get('remember') or {}).items():
                if not isinstance(v, str):
                    continue  # minor: 1 などの数はそのまま
                if 'tag' not in kw:
                    raise SystemExit(f'{pid}: 文字列を覚える remember は tag の反応に書く（{k}: {v}）')
                if out.setdefault((k, v), kw['tag']) != kw['tag']:
                    raise SystemExit(f'remember の {k}: {v} が tag {out[(k, v)]} と {kw["tag"]} の両方にある')
    return out


def mem_values(key):
    """鍵の値の一覧 [(試作の値, id)]。"""
    return [(v, i) for (k, v), i in MEM_IDS.items() if k == key]


def mem_cond(key, v):
    i = MEM_IDS.get((key, v))
    if i is None:
        raise SystemExit(f'cases の mem の {key}: {v} を覚える remember が無い')
    return f'(mem.{key} == "{i}" || mem.{key} == "{v}")'


def mem_slots(lines):
    """台詞の並び（の並び）にある {mem.鍵} の鍵。"""
    found = []
    for t in (x for a in lines for x in (a if isinstance(a, list) else [a])):
        found += [k for k in re.findall(r'\{mem\.([A-Za-z0-9_]+)\}', str(t)) if k not in found]
    return found


def fill_mem(x, key, word):
    if isinstance(x, list):
        return [fill_mem(y, key, word) for y in x]
    return str(x).replace('{mem.' + key + '}', word)


def remember_value(kw):
    """試作の remember: {鍵: 値} を、gozen の remember: [{key, set}] に（文字列の値は id に）。"""
    if not kw.get('remember'):
        return {}
    return {'remember': [{'key': k, 'set': MEM_IDS[(k, v)] if isinstance(v, str) else str(v)} for k, v in kw['remember'].items()]}


def case_when(cond):
    """試作の cases の if（hour / visits / days / step / mem）を、gozen の when の式に。"""
    parts = []
    for k, v in cond.items():
        if k == 'hour':  # [始, 終)。始 > 終 なら日をまたぐ（[23, 5] は 23 時〜4 時）
            a, b = v
            parts.append(f'(value.hour >= {a} || value.hour < {b})' if a > b else f'value.hour >= {a} && value.hour < {b}')
        elif k in ('visits', 'days', 'step'):  # [最小, 最大]（最大は null で上限なし）
            a, b = v
            parts.append(f'value.{k} >= {a}' + (f' && value.{k} <= {b}' if b is not None else ''))
        elif k == 'mem':  # {鍵: 値}。値が * なら、何か覚えていれば
            for mk, mv in v.items():
                parts.append(f'mem.{mk} != 0' if mv == '*' else mem_cond(mk, mv) if isinstance(mv, str) else f'mem.{mk} == "{mv}"')
        elif k == 'family':  # 子どもが出る回（回の YAML の family: true。gozen がコメントの value.family に 1 を入れる）
            parts.append('value.family == 1' if v else 'value.family != 1')
        else:
            raise SystemExit(f'cases の if に知らない条件 {k!r}（hour / visits / days / step / mem / family）')
    return ' && '.join(parts)


def book(src):
    tags = shared_tags(src)
    lewd = lewd_tags(src)
    fallback = (load(src / 'src/common.yaml').get('generic') or {}).get('safe_refusal')
    lexicon, by_pattern = {}, {}
    for tag, pat in tags.items():
        lexicon[tag] = lex_entry(*expand(pat))
        by_pattern[pat] = tag
    MEM_IDS.clear()
    MEM_IDS.update(mem_ids(src))
    people = []
    for pid in IDS:
        v = load(src / f'src/voice/{pid}.yaml')
        refusal = [x if isinstance(x, list) else [x] for x in (v.get('safe_refusal') or fallback or [])]
        if not v.get('safe_refusal'):
            print(f'注意: {pid} の voice に safe_refusal がない（common.yaml の generic.safe_refusal を使う）')
        assert refusal, 'safe_refusal が voice にも common.yaml の generic にもない'
        rules = [{'id': f'tip_{a}', 'kind': 'tip', **({'when': f'value.amount >= {a}'} if a != TIPS[0] else {}),
                  'say': say_value([lines]) } for a, lines in reversed(list(zip(TIPS, v['tips'])))]
        for kw in v['keywords']:
            alts = kw['alts'] if 'alts' in kw else [kw['say']]
            if 'tag' in kw:
                tag = kw['tag']
            else:
                pat = kw['match']
                tag = by_pattern.get(pat)
                if tag is None:
                    tag = slug(pat, lexicon, pid)
                    lexicon[tag] = lex_entry(*expand(pat))
                    by_pattern[pat] = tag
            mem = remember_value(kw)
            if tag in lewd:  # 未成年・子どもの回では、cases よりも前に性的でない断り
                rules.append({'id': f'{tag}__safe', 'when': f'tag.{tag} > 0 && {SAFE_WHEN}', 'say': say_value(refusal)})
            # cases：条件つきの返し（時刻・見に来た回数・覚えた値）。既定の返しより前に、上から順に置く
            for n, c in enumerate(kw.get('cases') or [], 1):
                when = f'tag.{tag} > 0 && {case_when(c["if"])}'
                slots = mem_slots(c['alts'])
                if len(slots) > 1:
                    raise SystemExit(f'{pid} {tag}: cases の台詞の {{mem.…}} は一つの鍵だけ（{slots}）')
                if not slots:
                    rules.append({'id': f'{tag}__{n}', 'when': when, 'say': say_value(c['alts']), **mem})
                    continue
                # {mem.鍵} を、覚えた値ごとの決まりに開く（値の言葉を台詞に書き込む）
                for word, i in mem_values(slots[0]):
                    rules.append({'id': f'{tag}__{n}_{i}', 'when': f'{when} && {mem_cond(slots[0], word)}',
                                  'say': say_value(fill_mem(c['alts'], slots[0], word)), **mem})
            rules.append({'id': tag, 'when': f'tag.{tag} > 0', 'say': say_value(alts), **mem})
        people.append({'id': pid, 'rules': rules, 'dodge': {'unknown': from_name(v['echo'])}})
    return {'lexicon': lexicon, 'people': people}


def book_text(bk):
    out = ['# 反応の本。tools/import_stream.py が試作の src/tags.yaml（全員で共通の判定）と src/voice/ から作る。',
           '# 子どもの話・未成年の語彙は、下ネタの決まりより前に置いてある。', 'lexicon:']
    for tag, e in bk['lexicon'].items():
        out.append(f'  {tag}: {flow(e)}')
    out.append('people:')
    for p in bk['people']:
        out.append(f'- id: {p["id"]}')
        out.append('  rules:')
        for r in p['rules']:
            head = f'  - id: {r["id"]}'
            out.append(head)
            for k in ('kind', 'when'):
                if k in r:
                    out.append(f'    {k}: {flow(r[k])}')
            out.append('    say:')
            out += [f'    - {flow(s) if isinstance(s, list) else q(s)}' for s in r['say']]
            if 'remember' in r:
                out.append(f'    remember: {flow(r["remember"])}')
        out.append('  dodge:')
        out.append('    unknown:')
        out += [f'    - {q(s)}' for s in p['dodge']['unknown']]
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- 立ち絵

def base_scale(path):
    """立ち絵の倍率：base.png の幅 / 1024（1024x1536 の絵は 1、2048x3072 は 2）。PNG の頭から読む。"""
    with open(path, 'rb') as fh:
        head = fh.read(24)
    assert head[:8] == b'\x89PNG\r\n\x1a\n', f'{path} が PNG でない'
    w = struct.unpack('>I', head[16:20])[0]
    assert w % 1024 == 0, f'{path} の幅 {w} が 1024 の倍数でない'
    return w // 1024


def puppet(src, pid, rig):
    parts = load(src / f'assets/{pid}/parts.json')
    at = lambda g: [parts[g]['x'], parts[g]['y']]
    f = parts['face']
    # 2048x3072 の絵（2026-10-28 に 1024 から 2 倍にした）では parts.json と rig も 2 倍。丸めは 1024 の座標でしてから倍率を掛け、
    # 1024 のときに作っていた値のちょうど S 倍にする（2 倍の座標で丸めると 1px ずれる）
    S = base_scale(src / f'assets/{pid}/base.png')
    u = lambda v: v / S  # 1024 の座標へ
    spring = lambda k: 170 + 14 * k  # 試作 puppet.js の胸のばね（2026-10-27「揺れすぎ」で固くした値）
    # 胸の楕円は胸そのものに絞る：胸の内側に収め、輪郭（髪・腹との境目）にかけない（2.2r は腕・手・髪、1.35r は髪と腹まで動いた。2026-10-27）
    soft = [{'ellipse': [S * round(u(x) - 0.55 * u(r)), S * round(u(y) - 0.5 * u(r)), S * round(1.1 * u(r)), S * round(1.1 * u(r))], 'follow': 'body', 'axis': 'y',  # 縦だけ（横に揺らすと胸の外側の縁が後ろの髪に対してずれる）
             'stiffness': spring(k), 'damping': 15, 'limit': round(S * round(u(rig['bounce']) * 0.9, 1), 1)}
            for k, (x, y, r) in enumerate(rig['chest'])]
    fx, fy, fw, fh = (int(u(f[k])) for k in ('x', 'y', 'w', 'h'))
    spec = {
        'base': 'base.png',
        'face': 'normal',
        'faces': {'normal': {}, **{n: {'image': f'face_{n}.png', 'at': at('face'), 'eyes': {'off': True}} for n in FACES
                                    if (src / f'assets/{pid}/face_{n}.png').exists()}},
        'eyes': {'closed': {'image': 'eyes_closed.png', 'at': at('eyes')}, 'every': [2.2, 6.7], 'double': 0},
        'mouth': {'frames': ['face', {'image': 'mouth_half.png', 'at': at('mouth')},
                             {'image': 'mouth_open.png', 'at': at('mouth')}], 'speed': 8},  # 1秒に約8回（12 は一覧で速すぎた）
        'head': {'center': [S * (fx + fw // 2), S * (fy + fh // 2 - fw // 10)], 'radius': f['w'], 'neck': rig['neck']},
        'soft_sway': soft,
        'motion': {
            'breath': {'depth': 0, 'period': 4.4},  # 胸以外は動かさない（2026-10-27「胸だけにして」）
            # 頭や体を左右に揺らさない（2026-10-27「頭を左右に動かしたりしないで欲しい」）。呼吸とうなずきだけ
            'sway': {'angle': 0, 'shift': 0, 'period': 7.3},
            'tilt': {'angle': 0},
            'talk': {'nod': 0},
        },
    }
    head = ['# tools/import_stream.py が試作の assets/<id>/parts.json と src/cast.yaml の rig から作る。',
            '# 表情は顔の上半分の差分。表情の間はまばたきしない（試作と同じ）。口の閉じは元の顔の口。',
            '# 胸（soft_sway）は試作の固いばね：揺れは小さく、1〜2回で収まる。']
    body = dump(spec)
    return '\n'.join(head) + '\n' + body


PLACEHOLDER = 'placeholder_base.png'  # 仮の立ち絵の名前（絵が来たら消える。名前で仮と分かるように）
PICTURES = ['base.png', 'eyes_closed.png', 'mouth_half.png', 'mouth_open.png', 'parts.json']  # 立ち絵に要る試作の絵（と表情 face_*.png）


def drawn(src, pid):
    """試作の assets/<id>/ に立ち絵がそろっているか（無ければ仮の立ち絵にする）。"""
    return all((src / f'assets/{pid}/{n}').exists() for n in PICTURES)


def placeholder_picture(rig, color, out):
    """仮の立ち絵：base.png と同じ 1024x1536 の透明な絵に、配信者の色の人影と PLACEHOLDER の字。
    首（rig.neck）の上に頭、下に肩と胴を置くので、rig の frame（top〜bottom）に頭から胸までが映る。"""
    from PIL import Image, ImageDraw, ImageFont
    w, h = 1024, 1536
    rgb = tuple(int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    nx, ny = rig['neck']
    fill, line = rgb + (150,), (255, 255, 255, 220)
    d.ellipse([nx - 95, ny - 230, nx + 95, ny - 20], fill=fill, outline=line, width=6)  # 頭
    d.rectangle([nx - 40, ny - 30, nx + 40, ny + 30], fill=fill)  # 首
    d.polygon([(nx - 230, ny + 70), (nx + 230, ny + 70), (nx + 270, h), (nx - 270, h)], fill=fill, outline=line, width=6)  # 胴
    d.ellipse([nx - 250, ny + 10, nx - 130, ny + 130], fill=fill)  # 肩
    d.ellipse([nx + 130, ny + 10, nx + 250, ny + 130], fill=fill)
    font = ImageFont.load_default(size=56)
    for i, t in enumerate(['PLACEHOLDER', 'no art yet']):
        d.text((nx, ny + 140 + 70 * i), t, font=font, fill=(255, 255, 255, 235), anchor='mt', stroke_width=3, stroke_fill=(0, 0, 0, 200))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)


def placeholder_puppet():
    """仮の立ち絵の puppet.yaml：人影の絵ひとつ。表情は全部 素の顔（絵の差分なし）にして、台本の表情を全部受ける。
    まばたき・口・胸の揺れは無い（目と口の絵が無いので）。"""
    spec = {'base': PLACEHOLDER, 'face': 'normal', 'faces': {'normal': {}, **{n: {} for n in FACES}},
            'motion': {'breath': {'depth': 0, 'period': 4.4}, 'sway': {'angle': 0, 'shift': 0, 'period': 7.3},
                       'tilt': {'angle': 0}, 'talk': {'nod': 0}}}
    head = ['# 仮の立ち絵（絵がまだ無い）。tools/import_stream.py が書く。試作の assets/<id>/ に parts.json・base.png・',
            '# eyes_closed.png・mouth_half.png・mouth_open.png（と face_<表情>.png）が置かれたら、流し直すと本物に替わる。']
    return '\n'.join(head) + '\n' + dump(spec)


# ---------------------------------------------------------------- 配信の決まり

def duo_list(src, guests):
    """試作の src/duo/<主>-<相手>/NNN.yaml を組の並びに（試作の tools/build.py と同じ決まり：主は配信者、相手は配信者かゲスト）。"""
    gids = [g['id'] for g in guests]
    out = []
    for d in sorted(p for p in (src / 'src/duo').iterdir() if p.is_dir()):
        host, _, mate = d.name.partition('-')
        if host not in IDS or (mate not in IDS and mate not in gids) or host == mate:
            raise SystemExit(f'src/duo/{d.name}: フォルダ名は <主>-<相手>（主は配信者の id、相手は配信者かゲストの id）')
        files = sorted(d.glob('*.yaml'))
        if files:
            out.append({'key': d.name, 'host': host, 'with': mate, 'files': files})
    return out


def streams(src, cast, guests, duos, common):
    eps = {pid: sorted((src / f'src/episodes/{pid}').glob('*.yaml')) for pid in IDS}
    chans = []
    for s in cast:
        v = load(src / f'src/voice/{s["id"]}.yaml')
        r = s['rig']
        chans.append({
            'id': s['id'], 'actor': s['id'], 'tag': s['tag'], 'room': f"{s['id']}/room.jpg",
            'frame': {'cx': r['cx'], 'top': r['top'], 'bottom': r['bottom']},
            'voice': s['voice'],
            'episodes': [f'streams/{s["id"]}/{e.name}' for e in eps[s['id']]],
            'greet': [from_name(g) or [] for g in v['greet']],
            'first': from_name(v['first']), 'streak': from_name(v['streak']), 'stayed': from_name(v['stayed']),
            'bridges': v.get('bridges') or [],  # 回と回のあいだに挟む一言（差し込みなし。試作の build.py が確かめる）
        })
    out = ['# 配信の決まり（ADR 0048）。tools/import_stream.py が試作の src/ から作る。',
           f'logo: {LOGO}   # 上の帯の題名の前の印',
           f'voices: {VOICES}   # 台詞の音声の置き場（assets/ の下、tools/voices.py が作る）',
           f'timing: {flow(TIMING)}   # 拍の長さ（秒）',
           f'live: {flow(LIVE)}',
           'slot: {minutes: 60, rest: 0}   # 1枠60分の雑談をつなぎ、終わったらすぐ次の枠（いつも配信中）',
           f'away: {flow(AWAY)}',
           f'tips: {flow(TIPS)}',
           f'bounce: {{on: "{BOUNCE_ON}", amount: {BOUNCE_AMOUNT}}}   # 胸が弾む台詞（試作と同じ「！」「ｗｗ」「草」）と強さ。投げ銭でも弾む',
           'crowd:',
           '  # 最後の「魔王府の監察」は台本だけに出る人なので、雑談には出さない',
           f'  names: {flow(common["handles"][:-1])}',
           f'  lines: {flow(common["ambient"])}',
           f'  tip_lines: {flow(common["tipTexts"])}',
           f'  rate: {CROWD_RATE}   # 雑談は 1.2〜4.7 秒おき',
           'channels:']
    for c in chans:
        out.append(f'- id: {c["id"]}')
        for k in ('actor', 'tag', 'room', 'frame', 'voice', 'episodes'):
            out.append(f'  {k}: {flow(c[k])}')
        out.append('  greet:   # 覚えの段 0〜4')
        out += [f'  - {flow(g)}' for g in c['greet']]
        for k in ('first', 'streak', 'stayed'):
            out.append(f'  {k}: {flow(c[k])}')
        if c['bridges']:
            out.append('  bridges:   # 回と回のあいだに、この中から一つ挟む')
            out += [f'  - {flow(b)}' for b in c['bridges']]
    for g in guests:
        # ゲスト：一人配信・カード・部屋・回・挨拶を持たず、二人配信の with にだけなる（ADR 0048）。立ち絵・映す範囲・色・声は持つ
        r = g['rig']
        out.append(f'- id: {g["id"]}   # ゲスト（{g["name"]}）。二人配信の相手にだけ出る')
        out.append('  guest: true')
        out.append(f'  actor: {g["id"]}')
        out.append(f'  tag: {q(g["tag"])}')
        out.append(f'  color: {flow(g["color"])}')
        out.append(f'  frame: {flow({"cx": r["cx"], "top": r["top"], "bottom": r["bottom"]})}')
        out.append(f'  voice: {flow(g["voice"])}')
    out.append(f'duos:   # 二人配信（試作の src/duo/<主>-<相手>/）。各ホストの一人配信を unlock 分見たら流れる（DUO_UNLOCK）')
    for d in duos:
        files = [f'streams/{d["key"]}/{f.name}' for f in d['files']]
        out.append(f'- {{host: {d["host"]}, with: {d["with"]}, unlock: {DUO_UNLOCK}, episodes: {flow(files)}}}')
    if not duos:
        out[-1] = 'duos: []   # 二人配信の回はまだ無い'
    return '\n'.join(out) + '\n', eps


JA_CHAR = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]')  # かな・漢字（訳し残しの目安）
SHOW_CONFLICTS = 30  # 食い違いの一覧を何件まで出すか（--conflicts で全部）
CONFLICTS_ALL = False


def stream_build(src):
    """試作の tools/build.py（英訳の組を作る決まり：en_pairs・voice_pairs）を読み込む。試作のフォルダには何も書かない。"""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(src / 'tools'))
    import build as sb
    sys.path.pop(0)
    return sb


def en_pairs(src, cast, duos):
    """試作の src/en/ の英訳を、(場所, 日本語, 英語) の組の並びに。並びは voice（配信者の順）、次に回（配信者・番号の順）、
    次に二人配信の回（src/en/duo/<主>-<相手>/NNN.yaml。組・番号の順。一人配信と同じ決まりで突き合わせる）。
    壊れている・日本語と合わない（拍の並び、構造、判定、差し込み）ファイルは丸ごと外し、理由を出す（書き手が書いている途中でも流せるように）。"""
    sb = stream_build(src)
    out, skipped = [], []

    def take(what, fn):
        n = len(sb.errors)
        prs = fn()
        if len(sb.errors) > n:
            skipped.append((what, sb.errors[n:]))
            return
        out.extend(prs)
    for s in cast:
        pid = s['id']
        vf = src / f'src/en/voice/{pid}.yaml'
        if vf.exists():
            def voice_fn(pid=pid, vf=vf):
                doc = sb.load_en(f'en/voice/{pid}.yaml', vf)
                return [] if doc is None else sb.voice_pairs(f'en/voice/{pid}', load(src / f'src/voice/{pid}.yaml'), doc)
            take(f'en/voice/{pid}.yaml', voice_fn)
    for s in cast:
        pid = s['id']
        for f in sorted((src / f'src/episodes/{pid}').glob('*.yaml')):
            ef = src / f'src/en/episodes/{pid}/{f.name}'
            if not ef.exists():
                continue
            w = f'episodes/{pid}/{f.name}'
            ja = sb.episode(w, load(f), pid, [pid])
            take('en/' + w, lambda: sb.en_pairs(w, ja, ef, pid, [pid])[1])
    for d in duos:
        hosts = [d['host'], d['with']]
        for f in d['files']:
            ef = src / f'src/en/duo/{d["key"]}/{f.name}'
            if not ef.exists():
                continue
            w = f'duo/{d["key"]}/{f.name}'
            ja = sb.episode(w, load(f), d['host'], hosts)
            take('en/' + w, lambda: sb.en_pairs(w, ja, ef, d['host'], hosts)[1])
    return out, skipped


def lang_en(src, cast, duos, common, conflicts_all=False):
    en_cast = load(src / 'src/en/cast.yaml')
    en = load(src / 'src/en/common.yaml')
    text = {'Succubus Live': 'Succubus Live', '配信一覧': 'Streams'}
    where = {}  # 日本語 -> 最初に訳が出た場所
    conflicts = {}  # 日本語 -> [(場所, 英語)]（使わなかった訳）

    def put(w, ja, e):
        if not ja or not e:
            return
        if e == ja and JA_CHAR.search(ja):  # 日本語のまま写しただけ（訳し残し）
            return
        if ja in text:
            if text[ja] != e:
                conflicts.setdefault(ja, []).append((w, e))
            return
        text[ja] = e
        where[ja] = w
    for s in cast:  # 配信者とゲスト
        e = en_cast.get(s['id']) or {}
        if not e:
            print(f'注意: src/en/cast.yaml に {s["id"]} の英語の名前が無い')
        put('src/en/cast.yaml', s['name'], e.get('name'))
        put('src/en/cast.yaml', s['tag'], e.get('tag'))
    # 共通の handles・ambient・tipTexts は src/common.yaml と同じ並び・同じ数（i 番目が i 番目の訳）
    assert len(common['handles']) == len(en['handles']), '英語の handles の数が日本語と違う'
    for key in ('ambient', 'tipTexts'):
        assert len(common[key]) == len(en[key]), f'英語の {key} の数が日本語と違う'
    for ja, e in list(zip(common['handles'], en['handles'])) + list(zip(common['ambient'], en['ambient'])) + list(zip(common['tipTexts'], en['tipTexts'])):
        put('src/en/common.yaml', ja, e)
    prs, skipped = en_pairs(src, [s for s in cast if not s.get('guest')], duos)
    dropped = {t for _, _, _, t in DROPPED}  # 書き出さなかった答えの返し（gozen の表に無い文になるので訳も入れない）
    if not MEM_IDS:
        MEM_IDS.update(mem_ids(src))
    words = en.get('remember_values') or {}  # 覚える値の id -> 英語（台詞の {mem.鍵} に入る言葉）
    lacking = set()
    for w, ja, e in prs:
        ja, e = from_name(ja), from_name(e)
        if ja in dropped and '/duo/' in w:  # 同じ行が反応の本などにもあれば、そちらの訳は残す
            continue
        slots = mem_slots([ja])
        if not slots:
            put(w, ja, e)
            continue
        # 本では {mem.鍵} を値ごとの台詞に開いてある（book）。英語も同じように開く
        for word, i in mem_values(slots[0]):
            if i not in words:
                lacking.add(i)
                continue
            put(w, fill_mem(ja, slots[0], word), fill_mem(e, slots[0], str(words[i])))
    if lacking:
        print(f'注意: src/en/common.yaml の remember_values に英語の無い値（その台詞は日本語のまま）: {sorted(lacking)}')
    n_lines = len(prs)
    # 表示に出ない handles（最後の「魔王府の監察」は雑談に出さない）の訳は、gozen の check が「ゲームの文でない」と言うので外す
    text.pop(common['handles'][-1], None)
    print(f'英訳: 組 {n_lines}、表の項目 {len(text)}、食い違い {len(conflicts)}（同じ日本語に別の英語。最初の訳を使う）')
    for what, errs in skipped:
        print(f'注意: {what} を外した（{len(errs)} 件。python3 tools/build.py で全部見える）: {errs[0]}')
    shown = sorted(conflicts.items(), key=lambda kv: -len(kv[1]))
    for ja, others in shown if conflicts_all else shown[:SHOW_CONFLICTS]:
        alts = '／'.join(f'{e!r}（{w}）' for w, e in others[:3]) + (f' ほか {len(others) - 3}' if len(others) > 3 else '')
        print(f'  食い違い: {ja!r} → 使う {text[ja]!r}（{where[ja]}）、使わない {alts}')
    if len(conflicts) > SHOW_CONFLICTS and not conflicts_all:
        print(f'  …ほか {len(conflicts) - SHOW_CONFLICTS} 件（--conflicts で全部）')
    head = ['# 英語。tools/import_stream.py が試作の src/en/ から作る（手で直さない）。',
            '# 英訳の無い回・行は日本語のまま流れる。同じ日本語に別の英語があるときは最初の訳（voice、次に回の順）を使う。']
    return '\n'.join(head) + '\n' + yaml.safe_dump({'text': text}, allow_unicode=True, sort_keys=False, width=1 << 20)


def build(src):
    everyone = load(src / 'src/cast.yaml')['streamers']
    # ゲスト（guest: true）は一人配信と声（src/voice/）を持たず、二人配信の相手にだけなる（試作の tools/build.py と同じ）
    cast = [s for s in everyone if not s.get('guest')]
    guests = [s for s in everyone if s.get('guest')]
    assert [s['id'] for s in cast] == IDS, 'src/cast.yaml の配信者が変わった'
    common = load(src / 'src/common.yaml')
    real = [s['id'] for s in everyone if drawn(src, s['id'])]
    for s in cast:
        assert s['id'] in real, f'{s["id"]} の立ち絵が試作の assets/{s["id"]}/ にそろっていない'
    DRAWN.intersection_update(n for n in FACES if all((src / f'assets/{i}/face_{n}.png').exists() for i in real))
    duos = duo_list(src, guests)
    DROPPED.clear()
    # 作るものだけ消す（assets/fonts/ など手で置いたものは残す）
    for d in ['streams', 'lang', 'data'] + [f'assets/{s["id"]}' for s in everyone]:
        shutil.rmtree(GAME / d, ignore_errors=True)
    actors = {s['id']: {'name': s['name'], 'puppet': f'{s["id"]}/puppet.yaml'} for s in everyone}
    write('data/cast.yaml', '# 配信者とゲスト（話すだけの人物）。tools/import_stream.py が作る。\n' + dump({'actors': actors}))
    write('data/world.yaml', '# 開くと配信の一覧。tools/import_stream.py が作る。\n'
          + dump({'locations': {'lobby': LOBBY}}))
    text, eps = streams(src, cast, guests, duos, common)
    write('data/streams.yaml', text)
    for pid, files in eps.items():
        for e in files:
            write(f'streams/{pid}/{e.name}', episode(e, pid, f'streams/{pid}/{e.name}'))
    for d in duos:
        for e in d['files']:
            write(f'streams/{d["key"]}/{e.name}', episode(e, d['host'], f'streams/{d["key"]}/{e.name}'))
    write('assets/react.yaml', book_text(book(src)))
    for s in everyone:
        pid = s['id']
        if pid not in real:  # 絵がまだ無い（ゲストのギャル）：仮の立ち絵
            write(f'assets/{pid}/puppet.yaml', placeholder_puppet())
            placeholder_picture(s['rig'], s['color'], GAME / f'assets/{pid}/{PLACEHOLDER}')
            print(f'注意: {pid} の立ち絵が試作の assets/{pid}/ に無いので仮の立ち絵（assets/{pid}/{PLACEHOLDER}）にした')
            continue
        write(f'assets/{pid}/puppet.yaml', puppet(src, pid, s['rig']))
        for n in ['base', 'eyes_closed', 'mouth_half', 'mouth_open'] + [f'face_{f}' for f in FACES if (src / f'assets/{pid}/face_{f}.png').exists()]:
            shutil.copy(src / f'assets/{pid}/{n}.png', GAME / f'assets/{pid}/{n}.png')
        if not s.get('guest'):  # ゲストは部屋を持たない（二人配信は主の部屋）
            shutil.copy(src / f'assets/{pid}/room.jpg', GAME / f'assets/{pid}/room.jpg')
    # gozen export はゲームの直下の LICENSE と NOTICE.txt を書き出しに入れる（NOTICE.md は拾わない）。make notices が同じかを確かめる
    shutil.copyfile(ROOT / 'LICENSE', GAME / 'LICENSE')
    shutil.copyfile(ROOT / 'NOTICE.md', GAME / 'NOTICE.txt')
    if DROPPED:
        print(f'注意: 二人配信の答えの返しで、聞いた人でない人の行 {len(DROPPED)} 行は書き出さない'
              '（gozen の ask の r は聞いた人の行だけ。話す人を書けるようになったら通す）')
        for w, who, spk, t in DROPPED:
            print(f'  {w}: ask {who} の答えの {spk} の行「{t[:30]}」')
    write('lang/en.yaml', lang_en(src, everyone, duos, common, CONFLICTS_ALL))
    n_duo = sum(len(d['files']) for d in duos)
    print('ok:', sum(len(v) for v in eps.values()), '回、二人配信', len(duos), '組', n_duo, '回、ゲスト', [g['id'] for g in guests])


# ---------------------------------------------------------------- 比べる

def spans(sub, text):
    """text の中の sub の出現（重なりも含む）を (始, 終) で。正規表現を使わない（語が多いと re の控えが溢れて遅い）。"""
    i = text.find(sub)
    while sub and i >= 0:
        yield i, i + len(sub)
        i = text.find(sub, i + 1)


def hits(entry, raw):
    """作った語彙の一項目が、コメントに当たるか（gozen の本の照合を真似る）。

    打ち消しは「語の出現が打ち消す語の出現の中にあれば数えない」として真似る。
    """
    words, ex = (entry['words'], entry['except']) if isinstance(entry, dict) else (entry, [])
    n = norm(raw)
    blocked = None  # 打ち消しの範囲。語が見つかったときだけ求める（minor の打ち消しは数千あるので）

    def covered():
        nonlocal blocked
        if blocked is None:
            blocked = set()
            for e in ex:
                for a, b in spans(e, n):
                    blocked.update(range(a, b))
        return blocked
    for w in words:
        if isinstance(w, dict):
            if re.search(r'\b' + re.escape(w['word'].lower()) + r'\b', raw.lower(), re.ASCII) and not any(norm(w['word']) in e and e in n for e in ex):
                return True
            continue
        for a, b in spans(norm(w), n):
            if not set(range(a, b)) <= covered():
                return True
    return False


def compare(src):
    sys.dont_write_bytecode = True  # 試作のフォルダに何も書かない
    sys.path.insert(0, str(src / 'tools'))
    import kwtest  # 試作の試しの例文（共通の判定ごとの例文と、普通の雑談）
    tags = shared_tags(src)
    bk = load(GAME / 'assets/react.yaml')
    corpus = [t for ex in kwtest.EXAMPLES.values() for t in ex] + list(kwtest.PLAIN)
    for pid in IDS:
        corpus += [b['chat'][1] for e in sorted((src / f'src/episodes/{pid}').glob('*.yaml'))
                   for p in load(e)['parts'] for b in p['beats'] if 'chat' in b]
    corpus = list(dict.fromkeys(str(c) for c in corpus))
    bad = 0
    for p in bk['people']:
        v = load(src / f'src/voice/{p["id"]}.yaml')
        pats = [(tags[k['tag']] if 'tag' in k else k['match']) for k in v['keywords']]
        res = [re.compile(x, re.I | re.ASCII) for x in pats]
        rules = [r for r in p['rules'] if r.get('kind') != 'tip' and '__' not in r['id']]  # cases の決まり（<tag>__<n>）は試作の正規表現と比べない
        diff = []
        for t in corpus:
            a = next((i for i, r in enumerate(res) if r.search(t)), -1)
            b = next((i for i, r in enumerate(rules) if hits(bk['lexicon'][r['id']], t)), -1)
            if a != b:
                diff.append(f'  {t[:40]}  試作:{rules[a]["id"] if a >= 0 else "-"}  本:{rules[b]["id"] if b >= 0 else "-"}')
        print(f'== {p["id"]}: 例文 {len(corpus)} のうち食い違い {len(diff)}')
        print('\n'.join(diff))
        bad += len(diff)
    return bad


def main():
    args = sys.argv[1:]
    cmp_only = '--compare' in args
    global CONFLICTS_ALL
    CONFLICTS_ALL = '--conflicts' in args
    args = [a for a in args if a not in ('--compare', '--conflicts')]
    src = Path(args[0]).resolve() if args else SRC
    if cmp_only:
        compare(src)
    else:
        build(src)


if __name__ == '__main__':
    main()

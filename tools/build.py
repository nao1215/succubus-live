#!/usr/bin/env python3
"""src/ の原稿（YAML）を、ゲームが読む data/（JSON）に変換して確かめる。

  data/index.json                       起動時に読む：配信者、ゲスト（二人配信の相手だけ）、時間帯、二人配信、回の数、拍の長さの決まり
  data/<lang>/common.json               視聴者の名前、流れるコメント、台本のない人の返し
  data/<lang>/voice/<id>.json           その人の声（挨拶、条件を満たしたときの反応、投げ銭の読み上げ）
  data/<lang>/ep/<id>/<n>.json          配信の回（開いたときに読む）
  data/<lang>/duo/<a>-<b>/<n>.json      二人配信の回

lang は ja と en。英語は src/en/ に日本語と同じ並びで書く（拍の数と種類がずれていたら止まる）。
拍は JSON で次の形にそろえる：
  ["say", 話す人, 台詞] / ["chat", 名前, コメント] / ["ask", {who, q, options:[{c, r:[[話す人, 台詞]]}], npc}]

使い方:
  python3 tools/build.py           確かめて data/ を書き直す（ブラウザの下書き index.html・reader.html が読む）
  python3 tools/build.py --check   確かめるだけ（何も書かない・消さない。make check / make verify が使う）
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
OUT = ROOT / 'data'
CHECK_ONLY = False  # --check：確かめるだけで、data/ に書かない
LANGS = ['ja', 'en']
# 拍の長さ（秒）。app.js も index.json のこの値で流す。
TIMING = {'say_base': 2.0, 'per_char': 0.14, 'chat': 1.6, 'ask_wait': 12}  # 2026-10-27「字幕早いかも。喋りと考えると」で 1.8/0.11 から
# 自由コメントの共通の判定：src/tags.yaml の {組: {名前: 正規表現}} を {名前: 正規表現} に（名前は全部の組を通して一意）
TAG_GROUPS = yaml.safe_load(open(SRC / 'tags.yaml', encoding='utf-8'))
TAGS = {k: str(v) for g in TAG_GROUPS.values() for k, v in g.items()}
assert len(TAGS) == sum(len(g) for g in TAG_GROUPS.values()), 'src/tags.yaml の名前が組をまたいで重なっている'
FACES = {'smile', 'smug', 'shy', 'surprised', 'annoyed', 'sad', 'angry', 'laugh', 'sleepy', 'thinking', 'flustered'}
errors = []
notes = []
PAIRS = []  # 英訳の組 (場所, 日本語, 英語)。en_pairs / voice_pairs が足す


def err(where, msg):
    errors.append(f'{where}: {msg}')


def load(p):
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def line(where, x, host, ids):
    """台詞ひとつを [話す人, 台詞] に。文字列なら聞いた人の台詞。"""
    if isinstance(x, str):
        return [host, x]
    if isinstance(x, dict) and len(x) == 1:
        who, text = next(iter(x.items()))
        if who not in ids:
            err(where, f'話す人 {who} はこの枠にいない')
        return [who, str(text)]
    err(where, f'台詞の形が違う: {x!r}')
    return [host, str(x)]


def beats(where, items, host, ids):
    out = []
    for i, b in enumerate(items or []):
        w = f'{where} 拍{i + 1}'
        if not isinstance(b, dict) or len(b) != 1:
            err(w, f'拍の形が違う: {b!r}')
            continue
        k, v = next(iter(b.items()))
        if k == 'say' or k in ids:
            who = host if k == 'say' else k
            face = None
            if isinstance(v, dict):
                face = v.get('face')
                if face not in FACES:
                    err(w, f'face {face!r} は {sorted(FACES)} のどれか')
                v = v.get('text', '')
            out.append(['say', who, str(v), face])
        elif k == 'chat':
            if not (isinstance(v, list) and len(v) == 2):
                err(w, 'chat は [名前, コメント]')
                continue
            out.append(['chat', str(v[0]), str(v[1])])
        elif k == 'ask':
            who = v.get('who', host)
            if who not in ids:
                err(w, f'聞く人 {who} はこの枠にいない')
            opts = v.get('options') or []
            if not 2 <= len(opts) <= 4:
                err(w, '答えは2〜4個')
            options = [{'c': str(o['c']), 'r': [line(w, x, who, ids) for x in o.get('r') or []]} for o in opts]
            for o in options:
                if not o['r']:
                    err(w, f'答え「{o["c"]}」に返しがない')
            npc = v.get('npc') or []
            for n in npc:
                if not (isinstance(n, list) and len(n) == 2 and isinstance(n[1], int) and 0 <= n[1] < len(options)):
                    err(w, f'npc の答えが範囲外: {n!r}')
            if not npc:
                err(w, 'npc の答えが一つもない')
            out.append(['ask', {'who': who, 'q': str(v['q']), 'options': options, 'npc': npc}])
        else:
            err(w, f'知らない拍 {k}')
    return out


def episode(where, doc, host, ids):
    """回：parts（見出しごとの拍の並び）を一本の拍の列にする。"""
    flat = []
    for p in doc.get('parts') or []:
        flat.extend(beats(f'{where}「{p.get("title", "?")}」', p.get('beats'), host, ids))
    if not flat:
        err(where, '拍が一つもない')
    # family: true は子どもが出る回（gozen はこの回の間、コメントへの反応で下ネタの返しを選ばない）。試作は使わない
    if 'family' in doc and not isinstance(doc['family'], bool):
        err(where, 'family は true か false')
    return {'title': str(doc.get('title', '')), 'lobby': doc.get('lobby') or [], 'beats': flat}


def say_secs(text):
    return TIMING['say_base'] + len(text) * TIMING['per_char']


def duration(bs):
    """日本語の拍から、回の長さ（秒）を見積もる。質問は一番長い返しで数える。"""
    t = 0.0
    for b in bs:
        if b[0] == 'say':
            t += say_secs(b[2])
        elif b[0] == 'chat':
            t += TIMING['chat']
        else:
            t += TIMING['ask_wait'] + max(sum(say_secs(x[1]) for x in o['r']) for o in b[1]['options'])
    return round(t)


def shape(bs):
    """英訳と突き合わせる骨組み：拍の種類、話す人、質問の答えと返しの数。"""
    out = []
    for b in bs:
        if b[0] == 'ask':
            out.append(('ask', b[1]['who'], tuple(len(o['r']) for o in b[1]['options']), len(b[1]['npc'])))
        else:
            out.append((b[0], b[1] if b[0] == 'say' else ''))
    return out


CASE_KEYS = {'hour', 'visits', 'days', 'step', 'mem', 'family'}


def check_cases(where, kw, alts):
    w = f'{where} {kw.get("tag") or kw["match"][:20]}'
    if any('{mem.' in line for a in alts for line in a):
        err(w, '既定の alts に {mem.…} は書けない（試作では値がない）。cases の中だけで使う')
    rem = kw.get('remember') or {}
    if not isinstance(rem, dict) or not all(isinstance(k, str) and isinstance(x, (str, int)) and not isinstance(x, bool) for k, x in rem.items()):
        err(w, 'remember は {鍵: 値（文字列か数）}')
    for c in kw.get('cases') or []:
        cond, calts = c.get('if'), c.get('alts')
        if not isinstance(cond, dict) or not cond or set(cond) - CASE_KEYS:
            err(w, f'cases の if は {sorted(CASE_KEYS)} の組み合わせ: {cond!r}')
            continue
        for k in ('hour', 'visits', 'days', 'step'):
            if k in cond and not (isinstance(cond[k], list) and len(cond[k]) == 2 and isinstance(cond[k][0], int)
                                  and (cond[k][1] is None or isinstance(cond[k][1], int))):
                err(w, f'cases の {k} は [下限, 上限]（hour は [始, 終)、上限 null は無制限）: {cond[k]!r}')
        if 'mem' in cond and not (isinstance(cond['mem'], dict) and all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in cond['mem'].values())):
            err(w, f'cases の mem は {{鍵: 値}}（値 * は「何か覚えていれば」）: {cond["mem"]!r}')
        if 'family' in cond and cond['family'] not in (0, 1):
            err(w, f'cases の family は 1（子どもが出る回）か 0: {cond["family"]!r}')
        if not calts:
            err(w, 'cases に alts がない')


def voice(where, v):
    out = {}
    for k in ('greet', 'first', 'streak', 'stayed', 'echo', 'tips', 'fallback'):
        if k in v:
            out[k] = v[k]
    if 'keywords' in v:
        out['keywords'] = []
        for kw in v['keywords']:
            # tag：src/tags.yaml の名前で、全員共通の判定（下ネタ・年齢・見た目・荒らし・挨拶など）を使う
            if 'tag' in kw:
                if kw['tag'] not in TAGS:
                    err(where, f'tag {kw["tag"]!r} は src/tags.yaml にない（{sorted(TAGS)}）')
                    continue
                kw = dict(kw, match=TAGS[kw['tag']])
            try:
                re.compile(kw['match'])
            except re.error as e:
                err(where, f'match {kw["match"]!r} が正規表現として読めない: {e}')
            # say：返しの台詞の並び。alts：返しの候補を何通りも（どれか一つを選ぶ）
            if 'alts' in kw:
                alts = [a if isinstance(a, list) else [a] for a in kw['alts']]
            elif 'say' in kw:
                alts = [kw['say'] if isinstance(kw['say'], list) else [kw['say']]]
            else:
                err(where, f'match {kw["match"]!r} に say も alts もない')
                alts = []
            # cases（条件つきの返し）と remember（覚える値）は gozen の反応の本だけが使う（tools/import_stream.py が変換する）。
            # 試作は既定の alts だけを使うので、既定の alts には {mem.…} を書かない
            check_cases(where, kw, alts)
            out['keywords'].append([kw['match'], alts])
    # safe_refusal：未成年と申告した視聴者・子どもが出る回で、下ネタ（tags.yaml の lewd の組）に返す性的でない断り。
    # 1〜3通り。tools/import_stream.py が lewd の組の反応すべての前に、条件つきで足す（voice の各反応には書かない）
    if 'safe_refusal' in v:
        sr = [a if isinstance(a, list) else [a] for a in (v['safe_refusal'] or [])]
        if not (1 <= len(sr) <= 3 and all(a and all(isinstance(x, str) and x.strip() for x in a) for a in sr)):
            err(where, 'safe_refusal は返しの候補 1〜3 通り（各候補は台詞か台詞の並び）')
        elif any('{mem.' in x for a in sr for x in a):
            err(where, 'safe_refusal に {mem.…} は書かない')
        else:
            out['safe_refusal'] = sr
    # bridges：回と回のあいだに挟む、つなぎの一言（gozen が使う。試作の app.js は使わない）。
    # 音声を前もって作るので差し込み（{name} など）は書かない
    if 'bridges' in v:
        b = v['bridges']
        if not (isinstance(b, list) and b and all(isinstance(x, str) and x.strip() for x in b)):
            err(where, 'bridges は台詞（文字列）の一覧')
        else:
            for x in b:
                if '{' in x or '}' in x:
                    err(where, f'bridges に差し込みは書かない: {x!r}')
            out['bridges'] = b
    if 'tips' in out and len(out['tips']) != 4:
        err(where, 'tips は投げ銭の4段ぶん（500/2000/10000/50000円）')
    return out


# ---------------------------------------------------------------- 英訳の突き合わせ
# 英訳は日本語の台詞と一対一の組（日本語, 英語）にして、succubus-live の tools/import_stream.py が
# gozen の言語の表（lang/en.yaml の「日本語の原文 → 英語」）に入れる。組を作る決まりはここだけに置く。

SLOT = re.compile(r'\{[^{}]*\}')  # {name} {days} {text} {mem.x} などの差し込み
JA_CHAR = re.compile(r'[぀-ヿ㐀-鿿ｦ-ﾟ]')  # かな・漢字・半角カナ（訳し残しの目安）
# voice の英訳で、日本語と同じでなければならない鍵（判定。台詞ではない）。ほかの文字列は全部台詞として組にする
JUDGE = {'tag', 'match', 'remember', 'if'}
VOICE_KEYS = {'greet', 'first', 'streak', 'stayed', 'safe_refusal', 'keywords', 'echo', 'tips', 'bridges', 'fallback'}


def load_en(where, p):
    """英訳の YAML（書き手が書いている途中で壊れていることがある）。読めなければ止める理由にして None。"""
    try:
        return load(p)
    except yaml.YAMLError as e:
        err(where, 'YAML として読めない: ' + ' '.join(str(e).split()))
        return None


def pair(where, ja, en, out):
    """台詞ひとつの組。差し込み（{name} など）は日本語と同じ数だけ同じものを書く（gozen の check が止める）。"""
    ja, en = str(ja), str(en)
    if ja.strip() and not en.strip():
        err(where, f'英訳が空（日本語：{ja[:30]}）')
        return
    if sorted(SLOT.findall(ja)) != sorted(SLOT.findall(en)):
        err(where, f'差し込みが日本語と違う：{SLOT.findall(ja)} / {SLOT.findall(en)}（{en[:40]}）')
    out.append((where, ja, en))


def episode_pairs(where, ja, en):
    """回（episode() の形）どうしの組：題、lobby、台詞、チャットの名前とコメント、ask の q・c・r・npc の名前。
    拍の並びは呼ぶ側が shape() で確かめてあること。"""
    out = []
    pair(f'{where} title', ja['title'], en['title'], out)
    if len(ja['lobby']) != len(en['lobby']):
        err(where, f'lobby の数が日本語と違う（{len(ja["lobby"])} / {len(en["lobby"])}）')
    else:
        for i, (a, b) in enumerate(zip(ja['lobby'], en['lobby'])):
            pair(f'{where} lobby[{i}]', a, b, out)
    for i, (jb, eb) in enumerate(zip(ja['beats'], en['beats'])):
        w = f'{where} 拍{i + 1}'
        if jb[0] == 'say':
            pair(w, jb[2], eb[2], out)
        elif jb[0] == 'chat':
            pair(w + ' 名前', jb[1], eb[1], out)
            pair(w, jb[2], eb[2], out)
        else:
            ja_ask, en_ask = jb[1], eb[1]
            pair(w + ' q', ja_ask['q'], en_ask['q'], out)
            for k, (jo, eo) in enumerate(zip(ja_ask['options'], en_ask['options'])):
                pair(f'{w} 答え{k + 1}', jo['c'], eo['c'], out)
                for n, (jr, er) in enumerate(zip(jo['r'], eo['r'])):
                    if jr[0] != er[0]:
                        err(f'{w} 答え{k + 1} 返し{n + 1}', f'話す人が日本語と違う（{jr[0]} / {er[0]}）')
                    pair(f'{w} 答え{k + 1} 返し{n + 1}', jr[1], er[1], out)
            for k, (jn, en_) in enumerate(zip(ja_ask['npc'], en_ask['npc'])):
                if jn[1] != en_[1]:
                    err(f'{w} npc{k + 1}', f'答えの番号が日本語と違う（{jn[1]} / {en_[1]}）')
                pair(f'{w} npc{k + 1} 名前', jn[0], en_[0], out)
    return out


def voice_pairs(where, ja, en):
    """voice（YAML を読んだままの形）どうしの組。英訳は日本語と同じ構造で、判定（JUDGE の鍵）は日本語と同じ値、
    台詞（それ以外の文字列）だけを英語にする。候補の数・行の数も日本語と同じにする（一対一の組にするため）。
    英訳に無い項目（greet など丸ごと）は日本語のまま流れる（note）。"""
    out = []
    extra = set(en) - set(ja)
    if extra:
        err(where, f'日本語の voice に無い項目: {sorted(extra)}')
    missing = [k for k in ja if k in VOICE_KEYS and k not in en]
    if missing:
        notes.append(f'{where}: 英訳の無い項目（日本語のまま）: {missing}')

    def walk(w, j, e):
        if isinstance(j, dict):
            if not isinstance(e, dict) or set(j) != set(e):
                err(w, f'項目が日本語と違う（{sorted(j) if isinstance(j, dict) else j!r} / {sorted(e) if isinstance(e, dict) else e!r}）')
                return
            for k in j:
                if k in JUDGE:
                    if j[k] != e[k]:
                        err(f'{w}.{k}', f'判定は日本語と同じにする（{str(j[k])[:40]} / {str(e[k])[:40]}）')
                else:
                    walk(f'{w}.{k}', j[k], e[k])
        elif isinstance(j, list):
            if not isinstance(e, list) or len(j) != len(e):
                err(w, f'数が日本語と違う（{len(j)} / {len(e) if isinstance(e, list) else type(e).__name__}）')
                return
            for i, (a, b) in enumerate(zip(j, e)):
                walk(f'{w}[{i}]', a, b)
        elif isinstance(j, str):
            if not isinstance(e, str):
                err(w, f'台詞（文字列）のはずが {e!r}')
                return
            pair(w, j, e, out)
        elif j != e:
            err(w, f'日本語と同じ値にする（{j!r} / {e!r}）')

    for k in ja:
        if k in en:
            walk(f'{where} {k}', ja[k], en[k])
    return out


def untranslated(where, pairs):
    """英訳にかな・漢字が残っている行の数を note で知らせる（訳し残しの目安。止めない）。"""
    left = [p for p in pairs if JA_CHAR.search(p[2])]
    if left:
        notes.append(f'{where}: 英訳にかな・漢字が残る行 {len(left)}（例：{left[0][0].split(" ", 1)[-1]}「{left[0][2][:30]}」）')


def en_pairs(where, ja_beats_doc, en_file, host, ids):
    """回の英訳ファイルを読み、拍の並びを確かめて (英訳の回, 組) を返す。読めない・合わないときは (None, [])。"""
    raw = load_en('en/' + where, en_file)
    if raw is None:
        return None, []
    en = episode('en/' + where, raw, host, ids)
    if shape(en['beats']) != shape(ja_beats_doc['beats']):
        js, es = shape(ja_beats_doc['beats']), shape(en['beats'])
        at = next((i for i, (a, b) in enumerate(zip(js, es)) if a != b), min(len(js), len(es)))
        err('en/' + where, f'日本語と拍の並び（種類・話す人・答えと返しの数）が合わない：拍{at + 1} から'
            f'（日本語 {js[at] if at < len(js) else "なし"} / 英語 {es[at] if at < len(es) else "なし"}、拍の数 {len(js)} / {len(es)}）')
        return None, []
    return en, episode_pairs('en/' + where, ja_beats_doc, en)


def write(path, obj):
    if CHECK_ONLY:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def pool(kind, key, host, ids):
    """回の一覧：src/<kind>/<key>/NNN.yaml。英訳があれば並びを突き合わせる。"""
    eps = []
    files = sorted((SRC / kind / key).glob('*.yaml'))
    for i, f in enumerate(files):
        w = f'{kind}/{key}/{f.name}'
        ja = episode(w, load(f), host, ids)
        secs = duration(ja['beats'])
        if not 10 * 60 <= secs <= 15 * 60:  # 1本は10〜15分の雑談配信（WRITERS.md）
            notes.append(f'{w}: {secs // 60}分（10〜15分が目安）')
        write(OUT / 'ja' / (kind if kind == 'duo' else 'ep') / key / f'{i}.json', dict(ja, secs=secs))
        en_file = SRC / 'en' / kind / key / f.name
        has_en = en_file.exists()
        if has_en:
            en, prs = en_pairs(w, ja, en_file, host, ids)
            if en is not None:
                for eb, jb in zip(en['beats'], ja['beats']):
                    if eb[0] == 'say':
                        eb[3] = jb[3]  # 表情は日本語のもの
                untranslated('en/' + w, prs)
                PAIRS.extend(prs)
                write(OUT / 'en' / (kind if kind == 'duo' else 'ep') / key / f'{i}.json', dict(en, secs=secs))
            has_en = en is not None
        eps.append({'secs': secs, 'en': has_en})
    for f in sorted((SRC / 'en' / kind / key).glob('*.yaml')):
        if not (SRC / kind / key / f.name).exists():
            err(f'en/{kind}/{key}/{f.name}', '日本語の同じ名前の回が無い')
    return eps


def main():
    import shutil
    global CHECK_ONLY
    CHECK_ONLY = '--check' in sys.argv[1:]
    if not CHECK_ONLY:
        shutil.rmtree(OUT, ignore_errors=True)
    cast = load(SRC / 'cast.yaml')['streamers']
    names_en = load(SRC / 'en' / 'cast.yaml') if (SRC / 'en' / 'cast.yaml').exists() else {}
    # ゲスト（guest: true）：一人配信・チャンネル・声を持たず、二人配信の相手にだけなれる。一覧（streamers）には入れず、index の guests に出す
    guests = [s for s in cast if s.get('guest')]
    cast = [s for s in cast if not s.get('guest')]
    guest_ids = [s['id'] for s in guests]
    for s in guests:
        s['en'] = names_en.get(s['id'], {})
        if (SRC / 'episodes' / s['id']).exists() or (SRC / 'voice' / f'{s["id"]}.yaml').exists():
            err(f'cast/{s["id"]}', 'ゲストは一人配信の回と声を持たない（guest: true を外すか、episodes/・voice/ を消す）')
    ids = [s['id'] for s in cast]
    for s in cast:
        s['en'] = names_en.get(s['id'], {})
        s['episodes'] = pool('episodes', s['id'], s['id'], [s['id']])
        if not s['episodes']:
            notes.append(f'{s["id"]}: 配信の回がまだない')
    # 二人配信：src/duo/<主>-<相手>/ があれば、その二人がそろって配信中のときに流れることがある
    duos = []
    for d in sorted(p for p in (SRC / 'duo').iterdir() if p.is_dir()):
        host, _, mate = d.name.partition('-')
        if host not in ids or (mate not in ids and mate not in guest_ids):
            err(f'duo/{d.name}', 'フォルダ名は <主>-<相手>（主は配信者の id、相手は配信者かゲストの id）')
            continue
        eps = pool('duo', d.name, host, [host, mate])
        if eps:
            duos.append(dict({'key': d.name, 'host': host, 'with': mate, 'episodes': eps}, **({'guest': True} if mate in guest_ids else {})))
    index = {'timing': TIMING, 'langs': LANGS, 'streamers': cast, 'guests': guests, 'duos': duos}
    write(OUT / 'index.json', index)
    for lang in LANGS:
        base = SRC if lang == 'ja' else SRC / 'en'
        common = load(base / 'common.yaml') if (base / 'common.yaml').exists() else load(SRC / 'common.yaml')
        write(OUT / lang / 'common.json', dict(common, generic=voice(f'{lang}/common', common['generic'])))
        for s in cast:
            vf = base / 'voice' / f'{s["id"]}.yaml'
            if vf.exists():
                if lang == 'en':
                    # 英訳の voice：日本語と同じ構造で、判定（tag・match・remember・cases の if）は日本語と同じ、台詞だけ英語。
                    # 判定が日英で同じなので、どちらの言語のコメントにも同じ反応が当たり、返しだけが表示の言語になる
                    doc = load_en(f'en/voice/{s["id"]}.yaml', vf)
                    if doc is None:
                        continue
                    prs = voice_pairs(f'en/voice/{s["id"]}', load(SRC / 'voice' / f'{s["id"]}.yaml'), doc)
                    untranslated(f'en/voice/{s["id"]}', prs)
                    PAIRS.extend(prs)
                    # 英訳に無い項目は日本語のまま（試作の app.js も同じ voice を読む）
                    doc = dict(load(SRC / 'voice' / f'{s["id"]}.yaml'), **doc)
                    v = voice(f'{lang}/voice/{s["id"]}', doc)
                else:
                    v = voice(f'{lang}/voice/{s["id"]}', load(vf))
                if lang == 'ja' and 'safe_refusal' not in v:
                    notes.append(f'voice/{s["id"]}.yaml に safe_refusal がない（gozen では common.yaml の generic.safe_refusal を使う）')
                write(OUT / lang / 'voice' / f'{s["id"]}.json', v)
        for f in sorted((SRC / 'en' / 'voice').glob('*.yaml')) if lang == 'en' else []:
            if f.stem not in ids:
                err(f'en/voice/{f.name}', '配信者の id ではない')
    for n in notes:
        print('note:', n)
    if errors:
        print('\n'.join(errors))
        sys.exit(1)
    n_ep = sum(len(s['episodes']) for s in cast) + sum(len(d['episodes']) for d in duos)
    hours = (sum(e['secs'] for s in cast for e in s['episodes']) + sum(e['secs'] for d in duos for e in d['episodes'])) / 3600
    n_en = sum(e['en'] for s in cast for e in s['episodes']) + sum(e['en'] for d in duos for e in d['episodes'])
    n_voice = len(list((SRC / 'en' / 'voice').glob('*.yaml')))
    left = sum(1 for p in PAIRS if JA_CHAR.search(p[2]))
    print(f'ok: 回 {n_ep}（英訳 {n_en}、voice の英訳 {n_voice}、英訳の行 {len(PAIRS)}、うちかな・漢字が残る {left}）、計 {hours:.1f} 時間')


if __name__ == '__main__':
    main()

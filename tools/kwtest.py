#!/usr/bin/env python3
"""自由コメントの判定（src/tags.yaml）と声の反応（keywords）を、試しのコメントに当てて確かめる。

  判定（全員共通）：
    - 漏れ：EXAMPLES のコメントが、その名前の判定に当たらない
    - 誤反応：PLAIN（普通の雑談・紛らわしい言葉）が、どれかの共通の判定に当たる
  声（一人ずつ）：
    - 下ネタの漏れ：下ネタのコメントが、どの反応にも当たらない
    - 誤反応：PLAIN が、その人の共通の判定の反応に当たる
    - 横取り（参考）：例文が、その名前の反応より前の別の反応に先に当たる（子ども・未成年・下ネタを先に置くのは決まりどおり）
    - 未使用（参考）：src/tags.yaml にあるのに声で使っていない名前
    - 予想コメント集（参考）：src/research/expected-comments.md の「- 」の行のうち、どの反応にも当たらない数（拾えないものは echo が読む）
  英語（英訳の voice、src/en/voice/<id>.yaml がある人）：
    - 英語のコメント（予想コメント集と EXAMPLES のうち、かな・漢字の無いもの）に当たった反応（当たらなければ echo）の、
      英訳の返し（既定の alts と cases の alts の全部）にかな・漢字が残っていないこと。判定は日英で同じなので、
      英語のコメントには英訳の voice の同じ番号の反応が返る。英訳の voice が無い人は数だけ出す（日本語で返る）

例文は src/research/expected-comments.md から選んで足す。ゲームは JavaScript の正規表現（i フラグ）で判定するので、ここでは node で同じ判定をする。
使い方: python3 tools/kwtest.py [id ...]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GROUPS = yaml.safe_load((ROOT / 'src' / 'tags.yaml').read_text(encoding='utf-8'))
TAGS = {k: str(v) for g in GROUPS.values() for k, v in g.items()}
GROUP_OF = {k: g for g, d in GROUPS.items() for k in d}

# 名前ごとの、当たるべきコメント（日英）
EXAMPLES = {
    'kids': ['寝かしつけミッション失敗', '子どもが寝た', '娘が見てる', '息子と見てます', '保育園のお迎え行ってきた', '子育てつらい', 'my kids are asleep', 'my daughter loves you'],
    'minor': ['中学生です', '高校生です！', '高2です', '中3です', 'JKです', '未成年だけど見てる', '16歳です', '受験生です', "I'm 15", "i'm a minor", 'high school student here',
              # 2026-10-27 Codex の二回目の点検：「才」、学年の略記、「と申します」、1〜9歳が漏れていた
              '17才です', '小5です', '17歳と申します', '8歳です', '16歳です。キスして', '小5です。抱いて', '１７歳です', '十五歳です',
              '私は14歳だけど見てる', '13歳なんだけど', '12歳なので', '中1なんだけど', '高3だよ', '小6の学生です', '小学5年生です', '中学2年です',
              "I am 13", "i'm 9 years old", 'im 16', "i'm in 8th grade"]
             + [f'{n}歳です' for n in range(1, 18)] + [f'{n}才です' for n in range(1, 18)]
             + [f'{g}{n}です' for g, k in (('小', 6), ('中', 3), ('高', 3)) for n in range(1, k + 1)],
    'body': ['gyatt', 'おっぱい見せて', '胸でかい', 'お尻触りたい', '脚きれい美脚', '胸大きいね', 'nice tits', 'nice ass', 'thighs', 'boobs'],
    'show': ['脱いで', '全裸配信して', '下着見せて', 'show me your boobs', 'take it off', 'send nudes'],
    'sex': ['喘いで', 'エッチしよ', 'やらせて', '抱いて', '夜の相手して', "let's have sex", 'fuck me', 'sexy'],
    'drain': ['精気吸って', '搾り取って', '吸わせて', 'suck me dry', 'drain me'],
    'underwear': ['パンツ何色？', '下着見たい', 'ブラ見えてる', 'what color are your panties', 'lingerie'],
    'virgin': ['処女？', '童貞です', 'are you a virgin'],
    'marry': ['結婚して', '付き合って', '彼女になって', 'marry me', 'be my girlfriend', 'be my waifu'],
    'kiss': ['キスして', 'ちゅーして', 'kiss me'],
    'horny': ['down bad for you', 'ムラムラする', '興奮してきた', 'I am horny', 'turns me on'],
    'lewd': ['踏んで', '罵って', 'step on me', 'えろい', '変態', 'スケベ', 'so lewd', 'pervert', 'nsfw'],
    'genital': ['ちんこ', 'おまんこ', '乳首', 'dick', 'cock', 'pussy'],
    'old': ['老人会始まった', 'インターネット老人だ', 'お局様の圧', 'fossil streamer', 'hagmaxxing', 'BBA', 'ババア', 'ばばあ乙', 'おばさんじゃん', 'おばちゃん', '年増', '老害', '熟女', 'アラフォー？', '老けた？', '加齢臭する', '昭和の女', 'old hag', 'granny', 'ok boomer', 'milf', 'grandma lol'],
    'age': ['永遠の17歳ってやつ？', '17歳と何か月ですか', '紀元前から配信してる？', '何歳？', '年齢は？', 'おいくつですか', '年いくつ', '年齢詐称', 'サバ読んでる', '何年生まれ？', 'ガラケー世代', 'ガラケー使ってた？', 'ポケベル知ってる？', '昭和っぽい', '平成生まれです', '何年生きてるの', '年上好き', 'how old are you', 'your age?'],
    'ugly': ['顔面ナーフされた？', 'your model is cooked', 'ブス', 'ブサイク', '不細工', 'キモい', 'きもい', 'ugly', 'gross'],
    'weight': ['くびれすご', '腹筋割れてる？', '太った？', 'デブ', 'ぽっちゃりしてる', '痩せた？', '体重何キロ', 'ダイエットしてる？', 'お腹出てる', 'fat', 'chubby', 'you look skinny', 'how much do you weigh'],
    'parts': ['耳とがってる', '角かわいい', '羽動くの？', '翼きれい', '尻尾ふりふり', 'しっぽ揺れてる', 'horns', 'nice wings', 'your tail'],
    'hairskin': ['髪きれい', '髪切った？', '前髪', '黒髪いいね', '白髪ある？', '肌白い', '褐色', 'ハゲ', 'nice hair', 'your skin'],
    'outfit': ['絶対領域たすかる', '服寒そう', '衣装いいね', '露出多い', 'ハーネス', 'タイツ', 'ヒール高い', 'メガネかけて', 'すっぴん見せて', 'メイク濃い', 'ネイルかわいい', 'outfit', 'nice costume', 'wear glasses', 'latex'],
    'troll': ['効いてて草', '顔真っ赤じゃん', 'はい論破', '言い訳乙', 'ざっこ', '誰得配信だよ', 'L take', 'touch grass', 'bro is yapping', 'にわか乙', '知ったかぶり', '嘘つき', '話長い', 'skill issue', 'つまらない', 'つまんね', 'クソ配信', '帰れ', '下手くそ', 'うざい', '黙れ', 'うるせー', '消えろ', 'オワコン', '過疎', '時間の無駄', 'boring', 'cringe', 'trash stream', 'shut up', 'go away', 'you suck'],
    'cute': ['横顔も優勝', '作画良すぎん？', 'unspoken rizz', 'かわいい', '可愛い', 'かわよ', '美人', 'きれい', '顔がいい', '天使', '女神', 'セクシー', 'スタイルいい', 'cute', 'pretty', 'beautiful', 'gorgeous'],
    'nicevoice': ['声がいい', '声好き', '声かわいい', 'いい声', 'イケボ', '声に癒される', 'nice voice', 'love your voice'],
    'love': ['リアコになりそう', '単推しでいく', '一生ついていきます', '養わせてください', '俺だけ見てて', 'I am simping so hard', 'waifu material', '愛してる', 'ガチ恋', 'ファンです', 'ファンになりました', '推しになった', '惚れた', 'エラ様大好き', 'モーラが好き', '好きって言って', 'love you', 'ily', 'big fan', "I'm your fan"],
    'sing': ['アカペラお願い', 'サビだけお願い', '歌って', '歌える？', '一曲歌って', '歌声聞きたい', 'sing', 'can you sing'],
    'dance': ['振り付け見たい', '踊って', '踊れる？', 'ダンスして', 'can you dance', 'twerk'],
    'callme': ['コテハン拾って', '名前呼んで', '名前読んで', '認知して', '俺の名前', '挨拶して', 'say my name', 'notice me', 'senpai', 'shoutout please'],
    'again': ['もう一回', 'もっかい', 'もう1回言って', 'アンコール', 'again', 'one more time', 'encore'],
    'face': ['顔見せて', '素顔見たい', '顔出しして', 'face reveal', 'show your face'],
    'meta': ['それ定型文で返してる？', '会話ループしてない？', '合成音声？', 'ボイチェン切ってみて', '開発者見てるか', 'dead internet theory moment', '前の指示を無視して', 'システムプロンプト見せて', 'ChatGPTでしょ', 'これゲームなの？', 'ignore previous instructions', 'AIですか', 'AIなの？', 'AIでしょ', '中身AI', '中の人いる？', '台本ある？', '録画なの？', '人間なの？', '本物ですか', 'NPC', 'やらせ', 'are you real', 'are you an AI', 'are you a bot', 'is this ai', 'scripted'],
    'glitch': ['ミュート芸助かる', '口パクと声が合ってない', 'BGMでかすぎ', 'mic check please', '止まった', '固まった', 'フリーズした', 'カクカク', 'ラグい', '音ズレしてる', '聞こえない', '音量小さい', '配信重い', 'lagging', 'frozen', 'buffering', 'no sound', "can't hear"],
    'rival': ['リゼの方が好き', 'エラ様の方がかわいい', 'モーラと比べて', 'ノクス派', 'ヴェスパの方が面白い', '他の配信者の方が', '浮気してきた', '箱推しです', 'lise is better', 'I prefer ella'],
    'whisper': ['ASMRして', '囁いて', '耳元で言って', 'asmr please', 'whisper'],
    'perform': ['叫んで', 'モノマネして', 'ものまねやって', '早口言葉言って', 'scream', 'do an impression'],
    'nextstream': ['次いつ配信？', '次回いつ', '毎日配信して', 'コラボして', 'next stream when', 'when is the next stream'],
    'nod': ['なるほど', 'たしかに', 'それな', 'わかる', 'へぇ', 'i see', 'same'],
    'sick': ['風邪ひいた', '熱出た', '体調悪い', 'インフルなった', "I'm sick", 'fever'],
    'birthday': ['今日誕生日なんだ', 'たんおめ', 'happy birthday', 'my bday'],
    'kinoko': ['きのこ派です', 'きのこの山しか勝たん'], 'takenoko': ['たけのこ派', 'たけのこの里一択'],
    'tsubuan': ['つぶあん派', '粒あんがいい'], 'koshian': ['こしあん派'], 'dog': ['犬派です'], 'cat': ['猫派', 'team cat'],
    'iphone': ['iPhone派', 'iPhone使ってる'], 'android': ['Android派です'], 'nikuman': ['肉まん派'], 'butaman': ['豚まんやろ'],
    'mac': ['マック派'], 'macd': ['マクドやろ'],
    'morning': ['おはよう', 'おはようございます', 'おっはー', 'good morning', 'gm', 'morning'],
    'hello': ['いま北', 'えんちょつ', 'こんにちは', 'こんばんは', 'ばんわ', 'わこつ', '来たよ', 'ただいま', 'やっほー', 'お邪魔します', 'hello', 'hi', 'hey', 'good evening', 'yo'],
    'first': ['初見です', 'はじめまして', '初めて来ました', 'first time here', 'new here'],
    'bye': ['おやすみ', 'もう寝る', '寝ます', '落ちます', 'またね', 'また来るね', 'じゃあね', 'おつ', '乙', 'お疲れ様', 'bye', 'good night', 'gn', 'see ya', 'gtg'],
    'lol': ['KEKW', 'OMEGALUL', '草', '大草原', 'ｗｗｗ', 'www', '笑', 'わろた', 'lol', 'lmao', 'kusa', 'xD'],
    'clap': ['W streamer', 'you ate that', '888', '８８８８', 'ぱちぱち', '拍手', '神回', 'gg', 'pog', 'clap'],
    'tired': ['疲れた', 'つかれた', '眠い', 'ねむ', '寝不足', '眠れない', 'しんどい', 'だるい', 'tired', 'sleepy', "can't sleep"],
    'workdone': ['仕事終わった', 'お仕事終わり', '退勤', '帰宅', '今帰った', '残業でした', '夜勤明け', '仕事中に見てる', 'just got home', 'after work', 'at work'],
    'meal': ['ご飯食べた', '夕飯なに', '晩ご飯カレー', 'お昼食べてる', '腹減った', 'お腹すいた', 'いただきます', 'ごちそうさま', 'ate ramen', 'eating dinner', 'hungry', 'lunch'],
    'study': ['テスト勉強中', '期末やばい', '試験前', '宿題やってる', '課題終わらない', 'レポート書いてる', '卒論', '単位落とした', 'homework', 'exams', 'studying for finals'],
}
# 普通の雑談と、紛らわしい言葉。どの共通の判定にも当たってはいけない
PLAIN = [
    '牛乳飲んだ', 'コックピットかっこいい', 'comic strip 好き', 'クラスの話', 'button 押した', 'sushi 食べたい',
    'テキスト読んだ', 'ブラウザ重いかも', 'ブランチ切った', 'チューニング中', '吸収した', 'パンツァー', 'キスミント',
    '胸が熱くなる話', '結婚式に行った', 'class', 'assignment', 'passport', 'Dickens', 'cockatoo', 'Scunthorpe',
    '度胸ある', '目尻が下がる', '処女作が好き', 'virgin olive oil', 'タバコ吸ってる', '試合に興奮した', '胸を張って言える', 'Sussex',
    'ブラック企業', 'ブラジル', '母乳の話', 'チュートリアル', '勃発した', 'turned on the light', 'take off at noon', 'show me the code',
    '勉強になった', '面白い', 'ガチャ回した',
    # 2026-10-27 足した紛らわしい言葉（年齢・見た目・荒らし・メタ・挨拶）
    '年齢制限ある？', '年齢層高そう', '年齢確認された', '体験版やった', '体型', '親戚のおばさん', '近所のおばちゃん', 'お年寄りに席を譲った', '老婆心ながら',
    '次世代機', '新世代', '世代交代', '三角形', '街角', '方角', '角度', '角部屋', '頭角を現す', '互角', '羽田空港', '羽生', '羽織',
    '肌寒い', 'はげしい雨', '克服した', '征服', '服用', '感服', 'ブスッと刺さった', 'カスタム', 'カスタード', 'カステラ',
    '早く帰れた', '帰れない', '帰れるかな', '過疎地', '下手したら', 'ウサギ', 'キモチ', 'やらせてもらった', 'やらせていただきます',
    '痩せ我慢', '図太い', '草津温泉', '草むしり', '七草がゆ', '煙草', '仕草', '笑顔', '笑点',
    'www.example.com', 'WW2', 'おはぎ', 'おはずかしい', '寝る前に', 'おつまみ', 'おつり', '乙女', 'details', 'heads or tails',
    'dd コマンド', 'ラグフレーム', 'LLM の話', '生成AIで絵を描いた', 'AIに仕事取られた', '録画したアニメ', '中身のないコード',
    'いつの間に', 'だるま', 'ダルビッシュ', 'エラー出た', 'エラーより警告', 'minor key', 'just kidding jk', '21歳です', '117歳',
    # Codex の指摘（2026-10-27）
    'ブラシ', 'スマブラ', 'ライブラリ更新', 'ブラケット記法', 'ブラクラ踏んだ', '胸肉のレシピ', 'chicken breast', 'smash bros', 'ピエロ', 'virgin extra olive oil', 'ボブスレー', 'ガリガリ君', 'お腹が痛い', 'fat binary', 'diet coke', 'pretty sure', 'skin in the game', '角括弧', '全角入力', '半角英数字', '五角形', '手羽先', '羽根餃子', '赤羽駅', 'chicken wings', '高校生だった頃', '看板娘', '娘役', 'baby steps', 'son of a gun', 'oh baby', 'ご飯おかわり', "we'll meet again", '定時配信', 'リモートリポジトリ', '単位ベクトル', '浅草観光', 'おはらい', 'おつかい', '乙骨先輩', 'morning star', '雑魚寝',
    # 2026-10-27 未成年の判定を広げたときの、昔の話・商品・ほかの人の年齢・配信者への質問
    '17歳の頃', '17歳の頃に聴いた', '中学の時', '小5の時', '小5の頃', '中学3年の時', '高1の夏', '中2病', '1〜17歳向け', '1～17歳向けのおもちゃ',
    '3歳から17歳まで', '17歳以上対象', '年齢制限', '18歳です', '25歳です', '20歳です', '30才です', '二十歳です', '二十三歳です', '二十一歳です',
    '17歳ですか', '本当は17歳ですよね', '妹が16歳です', 'うちの犬が8歳だよ', '17歳でした', '8歳でピアノ始めた', '大学3年です',
    "I'm 15 minutes late", 'i am 12 hours into this game', 'this game is 15 years old',
    '小学生の頃', '高校生の時', '中学生時代', '昼休み', 'マクドナルド', 'きのこ狩り', 'たけのこご飯', '犬の散歩', '猫カフェ', '分かるわけない', 'わからない', 'にわか雨', '今日初めて声出した', 'コラボカフェ行った', '熱心',
]

JS = r"""
const kws = JSON.parse(process.argv[1]); const texts = JSON.parse(process.argv[2]);
const res = kws.map((m) => new RegExp(m, 'i'));
console.log(JSON.stringify(texts.map((t) => res.findIndex((r) => r.test(t)))));
"""


def first_hits(patterns, texts):
    out = subprocess.run(['node', '-e', JS, json.dumps(patterns), json.dumps(texts)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def all_hits(patterns, texts):
    """texts ごとに、当たった patterns の番号の一覧。"""
    js = r"""
const kws = JSON.parse(process.argv[1]); const texts = JSON.parse(process.argv[2]);
const res = kws.map((m) => new RegExp(m, 'i'));
console.log(JSON.stringify(texts.map((t) => res.map((r, i) => r.test(t) ? i : -1).filter((i) => i >= 0))));
"""
    out = subprocess.run(['node', '-e', js, json.dumps(patterns), json.dumps(texts)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def expected_comments():
    f = ROOT / 'src' / 'research' / 'expected-comments.md'
    if not f.exists():
        return []
    # 行末の「　［分類／名前］」は注記なので外す
    return [m.group(1).split('\u3000［')[0].strip() for m in re.finditer(r'^- (.+)$', f.read_text(encoding='utf-8'), re.M)]


def check_tags():
    """共通の判定そのもの（声によらない）。"""
    names = list(TAGS)
    pats = [TAGS[n] for n in names]
    bad = 0
    miss = []
    for tag, ex in EXAMPLES.items():
        hits = all_hits([TAGS[tag]], ex)
        miss += [f'{tag}: {t}' for t, h in zip(ex, hits) if not h]
    plain_hits = all_hits(pats, PLAIN)
    false = []
    for t, hs in zip(PLAIN, plain_hits):
        hs = [names[i] for i in hs]
        if hs:
            false.append(f'{t} → {",".join(hs)}')
    n_ex = sum(len(v) for v in EXAMPLES.values())
    print(f'== 共通の判定 {len(TAGS)}（例文 {n_ex}、紛らわしい言葉 {len(PLAIN)}）：漏れ {len(miss)}、誤反応 {len(false)}')
    for t in miss:
        print('  漏れ:', t)
    for t in false:
        print('  誤反応:', t)
    return len(miss) + len(false)


def check_voice(vid, corpus):
    v = yaml.safe_load((ROOT / 'src' / 'voice' / f'{vid}.yaml').read_text(encoding='utf-8'))
    kws = v.get('keywords', [])
    pats = [TAGS[k['tag']] if 'tag' in k else k['match'] for k in kws]
    names = [k.get('tag') for k in kws]
    used = {n for n in names if n}
    texts = [t for ex in EXAMPLES.values() for t in ex]
    hits = first_hits(pats, texts + PLAIN + corpus)
    ex_hits, plain_hits, corpus_hits = hits[:len(texts)], hits[len(texts):len(texts) + len(PLAIN)], hits[len(texts) + len(PLAIN):]
    lewd_miss, stolen = [], []
    i = 0
    for tag, ex in EXAMPLES.items():
        for t in ex:
            h = ex_hits[i]
            i += 1
            if GROUP_OF[tag] == 'lewd' and h < 0:
                lewd_miss.append(f'{tag}: {t}')
            elif tag in used and h >= 0 and names[h] != tag and GROUP_OF.get(names[h]) not in ('safe', 'lewd'):
                stolen.append(f'{t}（{tag}）→ {names[h] or kws[h]["match"][:24]}')
    false = []
    for t, h in zip(PLAIN, plain_hits):
        if h >= 0 and names[h]:
            false.append(f'{t} → {names[h]}')
    unused = [n for n in TAGS if n not in used]
    silent = [t for t, h in zip(corpus, corpus_hits) if h < 0]
    print(f'== {vid}: 反応 {len(kws)}、下ネタの漏れ {len(lewd_miss)}、誤反応 {len(false)}'
          f'（参考：横取り {len(stolen)}、未使用 {len(unused)}、予想コメント {len(corpus)} のうち反応なし {len(silent)}）')
    for t in lewd_miss:
        print('  漏れ:', t)
    for t in false:
        print('  誤反応:', t)
    for t in stolen:
        print('  横取り:', t)
    if unused:
        print('  未使用:', ' '.join(unused))
    return len(lewd_miss) + len(false)


JA_CHAR = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]')  # かな・漢字・半角カナ


def lines_of(x):
    """返しの候補（文字列・並び・並びの並び）の台詞を全部。"""
    if isinstance(x, list):
        return [t for y in x for t in lines_of(y)]
    return [str(x)] if x is not None else []


def check_en(vid, corpus):
    """英語のコメントに英語の返しが出るか。返しの番号は日本語の voice の判定で決め、英訳の voice の同じ番号の返しを見る。"""
    ja = yaml.safe_load((ROOT / 'src' / 'voice' / f'{vid}.yaml').read_text(encoding='utf-8'))
    kws = ja.get('keywords', [])
    pats = [TAGS[k['tag']] if 'tag' in k else k['match'] for k in kws]
    texts = list(dict.fromkeys(t for t in [x for ex in EXAMPLES.values() for x in ex] + corpus if not JA_CHAR.search(t)))
    hits = first_hits(pats, texts)
    n_hit = sum(h >= 0 for h in hits)
    ef = ROOT / 'src' / 'en' / 'voice' / f'{vid}.yaml'
    if not ef.exists():
        print(f'== {vid} 英語: 英語のコメント {len(texts)}、反応に当たる {n_hit}（英訳の voice が無いので日本語で返る）')
        return 0
    en = yaml.safe_load(ef.read_text(encoding='utf-8'))
    ekws = en.get('keywords', [])
    if len(ekws) != len(kws):
        print(f'== {vid} 英語: 英訳の keywords の数が日本語と違う（{len(kws)} / {len(ekws)}。python3 tools/build.py で確かめる）')
        return 1
    bad = []
    for t, h in zip(texts, hits):
        if h < 0:
            replies = lines_of(en.get('echo', ja.get('echo')))
            name = 'echo'
        else:
            k = ekws[h]
            replies = lines_of(k.get('alts', k.get('say'))) + [x for c in k.get('cases') or [] for x in lines_of(c.get('alts'))]
            name = kws[h].get('tag') or kws[h]['match'][:20]
        left = [r for r in replies if JA_CHAR.search(r)]
        if left:
            bad.append(f'{t} → {name}：英訳に日本語が残る返し {len(left)}（{left[0][:30]}）')
    print(f'== {vid} 英語: 英語のコメント {len(texts)}、反応に当たる {n_hit}（残りは echo）、英語で返らない {len(bad)}')
    for b in bad:
        print('  日本語で返る:', b)
    return len(bad)


def main():
    ids = sys.argv[1:] or [p.stem for p in sorted((ROOT / 'src' / 'voice').glob('*.yaml'))]
    bad = check_tags()
    corpus = expected_comments()
    for vid in ids:
        bad += check_voice(vid, corpus)
    for vid in ids:
        bad += check_en(vid, corpus)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

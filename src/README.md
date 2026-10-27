# 原稿の書き方

原稿は src/ の YAML。`python3 tools/build.py` で data/ の JSON に変換し、形を確かめる（誤りがあれば場所を出して止まる）。ゲームは data/ だけを読む。

## 仕組み

- 画面を開くたびに、誰が配信中かを決める。初めて開いたときは全員、それ以後は8割ほど（少なくとも6割）。残りは「お休み中」。
- 配信中の人は、その視聴者がまだ見ていない次の回を流す（回の6割以上を見たら見たことになり、次に進む）。回が尽きたら最初に戻るので、回を足すほど同じ話を見なくなる。
- 配信は開いた少し前（0〜4分前）に始まっている扱い。途中から開くと、その時刻の位置から流れる。一覧のカードにも、その時刻の台詞が出る。
- 二人配信は duo/<主>-<相手>/ に回があれば、その二人がそろって配信中のとき、ときどき（4回に1回ほど）二人配信になる。
- 日本語で書いてから英語に訳す。英語は src/en/ に同じ場所・同じ名前で置き、拍の並び（種類・話す人・質問の答えと返しの数）を日本語とそろえる。ずれていたら変換が止まる。英訳のない回は、英語を選んだ人にも日本語で流れる。

## ファイル

- cast.yaml：配信者の見た目（立ち絵の首・胸・映す範囲）
  - `guest: true` の項目はゲスト（例：Rabbit Run のギャル）。一人配信・声・チャンネルを持たず、duo/<主>-<ゲスト>/ の相手にだけなれる（主にはなれない）。tools/build.py は一覧（streamers）から外し、index.json の guests に出す
- common.yaml：視聴者の名前（handles。最後の「魔王府の監察」は雑談に出さない）、流れる雑談（ambient）、投げ銭に添えるコメント（tipTexts）、声のない人の返し（generic）
- bible/<id>.yaml：キャラのバイブル（書き手が読む。ゲームは読まない）
- tags.yaml：自由コメントの共通の判定（正規表現）。声から `tag: 名前` で使う。確かめは `python3 tools/kwtest.py`
- research/expected-comments.md：プレイヤーが自由コメント欄に打ちそうなコメントの分類
- voice/<id>.yaml：その人の声。全部の回で共通
  - greet：入ってきたときの挨拶。覚えの段（0〜4）ごと。0 は null
  - first：初めて来た人への反応（{name}）
  - streak：3日以上続けて来た人への反応（{name}、{days} 日数）
  - stayed：回の6割以上を見た人への、終わりの礼（{name}）
  - keywords：自由コメントへの返し。上から順に判定し、最初に当たったものの alts から一つを返す。並びは src/tags.yaml の冒頭のとおり
    - `tag: 名前`：src/tags.yaml の共通の判定（子ども・未成年、下ネタ、年齢・見た目、荒らし、メタ、要望、ほかの配信者、雑談の派閥、褒め、挨拶・日常の報告）を名前で使う
    - `match: 正規表現`：その人だけの判定（得意領域など）。書ける正規表現の範囲は src/tags.yaml の冒頭
    - `alts`：返しの候補（[台詞, ...] を何通りも）。{name} が視聴者の名前
    - `remember: {鍵: 値}`：当たったら、その視聴者について値を覚える（例：`{kinoko_takenoko: きのこ}`）。保存をまたいで残る
    - `cases`：条件つきの返し。`- if: {...}` と `alts` を並べ、上から最初に条件を満たしたものを使う。どれも満たさなければ下の alts。
      if に書けるもの：`hour: [始, 終]`（時刻。始 > 終 なら日をまたぐ。[23, 5] は 23〜4 時）、`visits: [下限, 上限]`（その配信者の回を開いた回数。上限 null は無制限）、
      `days: [下限, 上限]`（連続の日数）、`step: [下限, 上限]`（覚えの段 0〜4）、`mem: {鍵: 値}`（覚えた値と同じ。値 '*' は何か覚えていれば）、
      `family: 1`（子どもが出る回の間。回の YAML の `family: true` が、gozen でコメントの value.family になる）。
      cases の alts では {mem.鍵} で覚えた値を差し込める
    - 未成年の視聴者：`- tag: minor` には `remember: {minor: 1}` を付ける（その視聴者が未成年と申告したことを覚え、会話の途中で解除しない）
    - remember と cases は gozen の反応の本（succubus-live の tools/import_stream.py が変換する）だけが使う。この試作（app.js）は既定の alts だけを使うので、既定の alts に {mem.…} は書かない（変換で止まる）
    例：
    ```yaml
    - tag: kinoko
      remember: {kinoko_takenoko: きのこ}
      cases:
      - if: {mem: {kinoko_takenoko: たけのこ}}
        alts:
        - ['{name}、前はたけのこって言ってたよね。']
      alts:
      - ['きのこ派ね。同じ！']
    - tag: hello
      cases:
      - if: {hour: [23, 5]}
        alts:
        - ['{name}、まだ起きてるの。']
      - if: {mem: {kinoko_takenoko: '*'}}
        alts:
        - ['{mem.kinoko_takenoko}派の{name}、いらっしゃい。']
      alts:
      - ['いらっしゃい、{name}。']
    ```
  - safe_refusal：未成年と申告した視聴者（覚えた minor が 1）か、子どもが出る回（family: true）のときに、下ネタのコメント（src/tags.yaml の lewd の組の名前すべて）へ返す、性的でない断り。1〜3通り（alts と同じ形）。
    各反応の cases には書かない。succubus-live の tools/import_stream.py が、lewd の組の反応すべての前に `tag.<名前> > 0 && (mem.minor == "1" || value.family == 1)` の決まりとして自動で足す。
    無い人は common.yaml の generic.safe_refusal を使う（tools/build.py が note で知らせる）。性的な代案・条件つきの誘い（「大人になったら」など）・ほかの下ネタへの言い換えは書かない。試作（app.js）は使わない
    ```yaml
    safe_refusal:
    - ['{name}様、そのお願いはお受けできません。今日はお話だけにいたしましょう。']
    - ['その話はいたしません、{name}様。最近お聴きになった曲を教えてくださいまし。']
    ```
  - echo：拾えなかった自由コメントを読むときの返し（{text} がコメント）
  - tips：投げ銭の読み上げ。500 / 2000 / 10000 / 50000 円の4段
  - bridges：回と回のあいだに挟む、つなぎの一言の一覧（1人20〜30行、1行は1〜2文）。gozen は1回の配信枠（60分）の中でその人の回を続けて流し、回の間にこの中から一つ挟む（succubus-live の tools/import_stream.py が data/streams.yaml の channel の `bridges:` に写す。試作の app.js は使わない）。どの回の前にも挟めるよう、次の回の題や中身に触れない。音声を前もって作るので差し込み（{name} など）は書かない。時間帯の言葉（おはよう、もう深夜だね）も書かない。
- episodes/<id>/NNN.yaml：一人配信の回（001 から順に番号）
- duo/<主>-<相手>/NNN.yaml：二人配信の回
- en/…：上の英訳（en/cast.yaml は英語の名前 {id: {name, tag}}）。下の「英訳の形」
- old/：前の形の台本と、やめた時間割（制作中の控え。このリポジトリには入れていない。台本の注にある src/old/… はその控えの場所）

## 英訳の形

英訳は日本語の台詞と一対一の組になり、gozen の言語の表（succubus-live の lang/en.yaml、「日本語の原文 → 英語」）に入る（succubus-live の tools/import_stream.py が、tools/build.py の組を作る決まりを使って入れる）。英訳の無い回・行・項目は、英語を選んだ人にも日本語で流れる。

- en/episodes/<id>/NNN.yaml：日本語の回と同じ名前。拍の並び（種類・話す人・ask の答えの数と返しの数と話す人・npc の数と答えの番号）を日本語とそろえる。訳すのは title、lobby（数も同じ）、台詞、chat の名前とコメント、ask の q・c・r・npc の名前。face と family は日本語のものを使う（英訳に書いても使わない）
- en/voice/<id>.yaml：日本語の voice/<id>.yaml と同じ構造（同じ項目、同じ並び、同じ数）で、台詞だけを英語にする
  - 日本語と同じ値をそのまま写すもの（判定）：keywords の `tag`・`match`・`remember`、cases の `if`。判定は日英の語を両方持っているので、英語のコメントにも日本語のコメントにも同じ反応が当たり、返しだけが表示の言語になる
  - 英語にするもの（台詞）：greet（段 0 の null はそのまま）、first、streak、stayed、safe_refusal、keywords と cases の `alts`（`say` の人は say）、echo、tips、bridges
  - 返しの候補の数、候補ごとの行の数は日本語と同じにする（日本語の1行が英語の1行になる）。日本語で `'台詞'` と書いた所は英語も文字列、`['台詞']` は並び
  - 書いていない項目（greet ごと無い、など）は日本語のまま流れる（tools/build.py が note で知らせる）
  - 例（日本語 → 英訳）：
    ```yaml
    # src/voice/lise.yaml                      # src/en/voice/lise.yaml
    - tag: hello                               - tag: hello
      cases:                                     cases:
      - if: {hour: [23, 5]}                      - if: {hour: [23, 5]}
        alts:                                      alts:
        - ['{name}、まだ起きてるの。']               - ["{name}, you're still up?"]
      alts:                                      alts:
      - ['いらっしゃい、{name}。']                 - ['Hey, {name}.']
    ```
- どちらも、差し込み（{name}、{days}、{text}、{mem.鍵}）は日本語と同じものを同じ数だけ書く（gozen の check が止める）
- 同じ日本語の文（「おはよう」など）は、表では一つの英語にしかならない。別々に訳したときは import_stream.py が食い違いの一覧を出し、最初に出たもの（回は配信者・番号の順、その前に voice）を使う。場面で訳し分けたいときは日本語の文を変える（gozen の訳の決まり、ADR 0027）
- 英訳にかな・漢字が残る行は、tools/build.py が訳し残しの目安として note で数える（止めない）

## 回の形

```yaml
title: 配信タイトル
family: true                    # 子どもが出る回だけ書く（子育ての回、子どもが主役の昔話など）。この回の間、gozen は下ネタのコメントに safe_refusal を返す。台本にも性的な冗談を置かない
parts:                          # 見出しごとに拍を並べる（見出しは書き手の目印。画面には出ない）
- title: オープニング
  beats:
  - say: 台詞                   # 主が話す
  - say: {face: smile, text: 台詞}  # 表情を付ける（smile 笑顔, smug ドヤ, shy 照れ, surprised 驚き, annoyed ジト目）。次の台詞で元に戻る
  - mora: 台詞                  # その人が話す（二人配信）
  - chat: [視聴者の名前, コメント]
  - ask:                        # チャットに聞く。答えの札が出る
      who: lise                 # 聞く人（省略すると主）
      q: 質問
      options:                  # 2〜4個
      - c: 札の文字
        r:                      # 返し。聞いた人の行（{id: 台詞} で別の人の行も書けるが、gozen 版の game/ には入らない。
                                #   tools/import_stream.py が数えて外す。二人の掛け合いにしたいときは ask の後の拍に書く）
        - '{name}は……'          # {name} は答えた人
      npc: [[視聴者の名前, 答えの番号], ...]
```

拍の長さ：台詞は 2.0 秒＋1文字 0.14 秒、チャットは 1.6 秒、質問は 12 秒＋返し（tools/build.py の TIMING）。1回は 10〜15 分の雑談（tools/build.py が外れたら note を出す）。

## 書き方の規則

- 一人語りを読ませる。ただし説明口調（講義・解説の読み上げ）にしない。体験談・失敗談から入り、持論をぶつけ、脱線し、チャットに言い返し、オチを付ける。
- 中身は本物の知識。実在の作品・人物・出来事・技術の名前を出してよい。事実の誤りは厳禁で、自信のない年や数字は書かない。
- チャットの拍で、配信者に突っ込み・質問・間違いの指摘をさせ、配信者がそれに反応して話を転がす。
- 下ネタはサキュバスなので可（冗談・匂わせ・下品なボケ）。露骨な性行為の描写はしない。実在の人物を性的にしない。未成年に見える要素は入れない。
- キャラの口調と芯はバイブルどおり。ASMR はしない。

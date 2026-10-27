# 二人配信 リゼ×ノクス の出典（src/duo/lise-nox/）

## 001：ノクスが来た。重いときに二回押すと、報酬が二回もらえるバグ

台詞の主張 → 出典。

- （2026-10-27 深夜の直しで台詞から外した。残しておく）スーパーマリオブラザーズ（初代）の「21フレームのフレームルール」：ゴールしても次の面は21コマおきの区切りでしか始まらない。縮めた数コマは、一つ前の区切りに届かなければ待ち時間になるだけ。「21コマおきに来るバス」のたとえは走者の間で定番（FlibidyDibidy の動画） → https://tasvideos.org/Forum/Posts/467021 、https://destructoid.com/?p=402968 、https://www.techradar.com/gaming/a-new-super-mario-bros-speedrun-record-has-been-set
- 処理落ちのコマ（ラグフレーム）：一コマ分の計算が間に合わないコマでは、ボタンを読まないことが多い → https://tasvideos.org/Glossary 、https://tasvideos.org/Forum/Topics/16042 （「ゲームがボタンを読まなかったコマ」がラグフレームの定義）。台詞は「ことが多い」とぼかした。
- NES 版テトリス（任天堂が1989年に北米で出したもの。日本のファミコン版は1988年の BPS 版で別のゲーム）のクラッシュ：レベル155から起こりうる。点数を足す処理（レベル＋1回だけ足し算を繰り返す作り。一列消しが一番遅い）が長くなり、描画の処理がゲームの処理が終わる前に割り込んで、前提が崩れて固まる。必ず落ちるのではなく、レベル155に一列消しで入るなど、消し方しだい。人のプレイで初めて固めたのは2023年12月21日、レベル157（2026-10-27 深夜に biggieblog と Wikipedia で確かめ直した。台詞は「海外のファミコン、NESの任天堂のテトリス」「レベル百五十五から、消し方によって固まることがある」「人のプレイで、初めてそこまで行って止めた人」） → https://biggieblog.com/celebrating-the-first-nes-tetris-game-crash/ 、https://en.wikipedia.org/wiki/Tetris_(NES_video_game) 、https://gigazine.net/gsc_news/en/20240508-tetris-hack/
  - 達成した人の名前と年齢は出していない（未成年なので、名前を出さず「初めて止めた人」とだけ言う）。
- GIF の読み方：作者ウィルハイトが2013年の Webby 賞の授賞式で「ジフ」と宣言 → src/sources/common-topics.md（https://en.wikipedia.org/wiki/Pronunciation_of_GIF）
- emacs に標準でテトリス（M-x tetris）、自動で遊ぶ autotetris-mode がある → src/sources/common-topics.md（https://doc.emacsen.de/28.2/fun/tetris.html 、https://nullprogram.com/blog/2014/10/19/）
- 冪等性（何回送っても一回分）と、決済の会社が同じ注文に同じ札（idempotency key）を付けて送らせ、二回目には一回目の結果を返す仕組み → https://docs.stripe.com/api/idempotent_requests 、https://www.rfc-editor.org/rfc/rfc9110#name-idempotent-methods

## 作り話（バイブルの person / life に従う。実在の出来事ではない）

- ノクスが小さな班を見ていること（設計を読む係、レビューのコメントが四十個、振り返りに人の名前を書かない、新しい人に合わせて会議でギフ）：2026-10-27 深夜のユーザーの方針（ノクスはシニア級でテックリード。設計のレビュー、障害対応の指揮、後輩の育成、責めない振り返り）に合わせたこの回の作り話。bible は別の担当が直す。
- リゼの一行の報告書のレビュー、ゆうべの録画を数えて十回中二回：この回の作り話。

- リゼの放置ゲーの「重いときに二回押すと二回入る」バグ（ゲームの名前は出さない。どう押すかは台詞で言わない。プレイヤー同士で売り買いできる設定も作り話）。
- ノクスの二〇一四年の「こちらでは再現しません」で閉じられた報告（三年後に別の人の報告で直った。bible の grudges）、九時間ずれ事件と二重の請求書、0.05 BTC と固定した乱数の種、よる、THANKS の41行（うち一行はサボテン）、nxo、×3.7、六回中四回のカップヌードル、vim、ジフ（会議ではギフ）：src/bible/nox.yaml と src/bible/likes/nox.yaml。
- リゼの重複です九件、朝五時の報告者と三分差、ねぼすけ一号の十九日、十五分のカップヌードル、emacs と autotetris、ギフ：src/bible/lise.yaml と src/bible/likes/lise.yaml。
- ノクスの「よる」の仮説（合図の係が来たとき準備が途中なのでは）を確かめて外れた、もこの回の作り話。テトリスの事実とは「割り込みが、途中の処理の前提を崩す」という形だけを重ねた。

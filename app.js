// Succubus Live：一覧（配信中とこのあと）、配信画面、チャット、投げ銭、条件で起きる反応、見ていない間の稼ぎ、日英切り替え。
'use strict';

// 処理が止まったときは、理由を画面に出す（スマホでは開発者ツールが見られないため）
function showError(msg) {
  const box = document.getElementById('errbox');
  if (!box) return;
  box.hidden = false;
  box.textContent += (box.textContent ? '\n' : '') + 'エラー: ' + msg;
}
window.addEventListener('error', (e) => showError(`${e.message} (${(e.filename || '').split('/').pop()}:${e.lineno})`));
window.addEventListener('unhandledrejection', (e) => showError(String(e.reason && (e.reason.stack || e.reason))));

// ---------- 保存 ----------
const SAVE_KEY = 'succubus-stream-v2';
const fresh = () => ({
  name: '', yen: 3000, lastSeen: Date.now(), skill: 0, cap: 0, lang: 'ja',
  gens: {}, aff: {}, visits: {}, progress: {}, opened: false, tts: false, worked: 0,
});
let S = fresh();
function load() {
  try {
    const v = JSON.parse(localStorage.getItem(SAVE_KEY) || 'null');
    if (v) S = Object.assign(fresh(), v);
  } catch (e) { /* 保存が使えなくても遊べる */ }
}
function save() {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) { /* 同上 */ }
}

// ---------- 時刻（?t=2026-10-31T22:40 で今の時刻を差し替えて試せる。?fresh で初回の状態から） ----------
const params = new URLSearchParams(location.search);
const offset = params.has('t') ? new Date(params.get('t')).getTime() - Date.now() : 0;
const nowMs = () => Date.now() + offset;
const DAY = 86400000;
// 時刻はすべて日本時間で数える（配信の時間割が日本時間のため）
const JST = 9 * 3600000;
const dayOf = (ms) => Math.floor((ms + JST) / DAY);               // 日本時間の日付（通し番号）

// ---------- 言葉 ----------
const UI = {
  ja: {
    comment: 'コメントする', send: '送信', answer: '答える：', live: '配信中', next: 'お休み中', offline: 'オフライン', sideHead: '配信中のチャンネル', chatHead: '配信チャット', backShort: '一覧', watching: (n) => `${n.toLocaleString('ja-JP')}人が視聴中`,
    none: '今は誰も配信していません。', yourName: 'あなたの名前', nameLead: '配信者に読まれる名前です。', decide: '決める',
    welcome: 'おかえりなさい', receive: '受け取る', close: '閉じる', ended: '配信は終了しました', back: '一覧へ',
    tipNote: '入力欄の文も一緒に送られます。', loadFail: '配信の読み込みに失敗しました', remembered: (n, lv) => `${n}に覚えられた（★${lv}）`,
    awayText: (y) => `いない間に、<b>${y}</b> たまりました。`, anon: '名無しの使い魔',
  },
  en: {
    comment: 'Say something', send: 'Send', answer: 'Answer:', live: 'Live now', next: 'Offline', offline: 'Offline', sideHead: 'Live channels', chatHead: 'Stream chat', backShort: 'Browse', watching: (n) => `${n.toLocaleString('en-US')} watching`,
    none: 'Nobody is live right now.', yourName: 'Your name', nameLead: 'The streamers will read this name.', decide: 'OK',
    welcome: 'Welcome back', receive: 'Collect', close: 'Close', ended: 'The stream has ended', back: 'Back',
    tipNote: 'Whatever is in the comment box goes with it.', loadFail: 'Could not load the stream', remembered: (n, lv) => `${n} remembers you (★${lv})`,
    awayText: (y) => `While you were away, <b>${y}</b> piled up.`, anon: 'Nameless familiar',
  },
};
const ui = () => UI[S.lang === 'en' ? 'en' : 'ja'];
const primary = () => (S.lang === 'en' ? 'en' : 'ja');
const nameOf = (s) => (S.lang === 'en' && s.en?.name) || s.name;
function applyUI() {
  const u = ui();
  $('#say').placeholder = u.comment;
  $('#send').textContent = u.send;
  $('#nameTitle').textContent = u.yourName;
  $('#nameLead').textContent = u.nameLead;
  $('#nameok').textContent = u.decide;
  $('#awayTitle').textContent = u.welcome;
  $('#awayok').textContent = u.receive;
  $('#liveHead').textContent = u.live;
  $('#sideHead').textContent = u.sideHead;
  $('#chatHead').textContent = u.chatHead;
  $('#backText').textContent = u.backShort;
  $('#choices').dataset.label = u.answer;
  $('#endText').textContent = u.ended;
  $('#endback').textContent = u.back;
  $('#langbtn').textContent = { ja: '日本語', en: 'English', both: '日/EN' }[S.lang];
  document.documentElement.lang = primary();
}

// ---------- データ ----------
let DATA = null;          // data/index.json
let STREAMERS = [];
let COMMON = {};          // 言語ごとの共通の言葉
const cache = new Map();
async function getJSON(path) {
  if (cache.has(path)) return cache.get(path);
  const r = await fetch(path);
  if (!r.ok) throw new Error(path + ' ' + r.status);
  const v = await r.json();
  cache.set(path, v);
  return v;
}
async function getOpt(path) {
  try { return await getJSON(path); } catch (e) { return null; }
}
const fixRe = (kws) => (kws || []).map(([re, lines]) => [new RegExp(re, 'i'), lines]);

// ---------- 誰が配信中か：開くたびに決める ----------
// 初めて開いたときは全員、それ以後は8割ほど。配信中の人は、あなたがまだ見ていない次の回を流す。
// 二人とも配信中で二人配信の回があれば、ときどき二人配信になる。
// 配信ひとつ：{hosts, s(主), key(進み具合の鍵), start, end, path(言語抜き), en}
let SHOWS = [];
let OFFLINE = [];
function nextEpisode(key, eps) {
  const n = S.progress[key] || 0;
  return n % eps.length;
}
function decideShows() {
  const loadAt = nowMs();
  const first = !S.opened;
  const live = STREAMERS.filter((s) => s.episodes.length && (first || Math.random() < 0.8));
  // 一人もいないのは寂しいので、少なくとも6割は配信中にする
  const want = Math.ceil(STREAMERS.length * 0.6);
  for (const s of STREAMERS) if (live.length < want && !live.includes(s) && s.episodes.length) live.push(s);
  const used = new Set();
  const shows = [];
  for (const d of DATA.duos) {
    const a = live.find((s) => s.id === d.host), b = live.find((s) => s.id === d.with);
    if (!a || !b || used.has(a) || used.has(b) || !d.episodes.length || Math.random() > 0.25) continue;
    used.add(a); used.add(b);
    const key = 'duo:' + d.key, i = nextEpisode(key, d.episodes);
    shows.push({ hosts: [a.id, b.id], s: a, key, secs: d.episodes[i].secs, path: `duo/${d.key}/${i}.json`, en: d.episodes[i].en });
  }
  for (const s of live) {
    if (used.has(s)) continue;
    const i = nextEpisode(s.id, s.episodes);
    shows.push({ hosts: [s.id], s, key: s.id, secs: s.episodes[i].secs, path: `ep/${s.id}/${i}.json`, en: s.episodes[i].en });
  }
  // 配信は少し前に始まっている（0〜4分前）。長さは回の台本の長さ。
  for (const x of shows) {
    x.start = loadAt - Math.random() * 240000;
    x.end = x.start + x.secs * 1000;
  }
  SHOWS = shows.sort((a, b) => STREAMERS.indexOf(a.s) - STREAMERS.indexOf(b.s));
  OFFLINE = STREAMERS.filter((s) => !shows.some((x) => x.hosts.includes(s.id)));
  S.opened = true;
  save();
}
const liveNow = () => SHOWS.filter((x) => nowMs() < x.end);
// 回を見終えた（6割以上見た）ら、その人の次の回へ進める
function markSeen(show) {
  if (show.seenMarked) return;
  show.seenMarked = true;
  S.progress[show.key] = (S.progress[show.key] || 0) + 1;
  save();
}
// その言語の回（英訳がなければ日本語）
async function episodeOf(show, lang) {
  if (lang === 'en' && !show.en) return null;
  return getOpt(`data/${lang}/${show.path}`);
}

// ---------- お金：いない間にたまる ----------
// 仕事の種類や買い物はない。戻ってきたら「いない間に ¥〇〇 たまった」と出すだけ（2026-10-27 ユーザーの指示）。
const yen = (n) => '¥' + Math.floor(n).toLocaleString('ja-JP');
const AWAY_RATE = 1500;            // 1時間あたり
const AWAY_CAP = 24;               // たまるのは24時間ぶんまで
// 覚えてもらった★の合計1つにつき +10%
function affBonus() {
  let lv = 0;
  for (const s of STREAMERS) lv += affLevel(s.id);
  return 1 + 0.1 * lv;
}
const hourly = () => AWAY_RATE * affBonus();

// ---------- 覚え ----------
const AFF_STEPS = [0, 30, 150, 600, 3000];
function affLevel(id) {
  const p = S.aff[id] || 0;
  let lv = 0;
  for (let i = 0; i < AFF_STEPS.length; i++) if (p >= AFF_STEPS[i]) lv = i;
  return lv;
}
function addAff(id, p) {
  const before = affLevel(id);
  S.aff[id] = (S.aff[id] || 0) + p;
  const after = affLevel(id);
  if (after > before) toast(ui().remembered(nameOf(byId(id)), after));
  refreshWallet();
}
const stars = (id) => '★'.repeat(affLevel(id)) + '☆'.repeat(4 - affLevel(id));

// ---------- 道具 ----------
const $ = (s) => document.querySelector(s);
const byId = (id) => STREAMERS.find((s) => s.id === id);
const fill = (t, vars) => t.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ''));
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function toast(text) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = text;
  $('#toasts').appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function refreshWallet() {
  $('#yen').textContent = yen(S.yen);
  if (watching) $('#aff').textContent = stars(watching.opened.id);
}

// ---------- 立ち絵 ----------
function rigDef(s) {
  return Object.assign({ waist: s.rig.neck[1] + 520 }, s.rig);
}
const camOf = (s) => ({ cx: s.rig.cx, y: s.rig.top, h: s.rig.bottom - s.rig.top });
// 二人配信では少し引いて、二人を左右に置く
function duoCam(cam, n, i) {
  if (n < 2) return cam;
  const h = cam.h * 1.25;
  return { cx: cam.cx, y: cam.y - (h - cam.h) * 0.3, h, shift: i === 0 ? 0.22 : -0.22 };
}
const t0 = performance.now();
const clock = () => (performance.now() - t0) / 1000;

// ---------- 読み上げ（ブラウザのときだけ） ----------
// アプリ（Wails）の中では出さない。ブラウザに読み上げ機能があるときだけ🔊を出す。
const canSpeak = () => 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined' && !window.wails && !window.go;
function speak(text, who, onEnd) {
  const u = new SpeechSynthesisUtterance(text.replace(/[「」『』（）]/g, ''));
  u.lang = primary() === 'en' ? 'en-US' : 'ja-JP';
  const voices = speechSynthesis.getVoices().filter((v) => v.lang.replace('_', '-').startsWith(u.lang.slice(0, 2)));
  if (voices.length) u.voice = voices[0];
  const v = byId(who)?.voice || {};
  u.pitch = v.pitch ?? 1;
  u.rate = v.rate ?? 1;
  let done = false;
  const finish = () => { if (!done) { done = true; onEnd(); } };
  u.onend = finish;
  u.onerror = finish;
  speechSynthesis.speak(u);
  return finish;
}
function stopSpeaking() { if (canSpeak()) speechSynthesis.cancel(); }

// ---------- 拍の時刻 ----------
// 回の頭からの秒で、各拍がいつ始まるか（build.py と同じ決まり）
function beatTimes(beats) {
  const T = DATA.timing;
  const say = (text) => T.say_base + text.length * T.per_char;
  const out = [];
  let t = 0;
  for (const b of beats) {
    out.push(t);
    if (b[0] === 'say') t += say(b[2]);
    else if (b[0] === 'chat') t += T.chat;
    else t += T.ask_wait + Math.max(...b[1].options.map((o) => o.r.reduce((a, x) => a + say(x[1]), 0)));
  }
  return out;
}
// 経った秒に当たる拍の番号（質問の途中なら次の拍から）
function beatAt(times, secs) {
  let i = 0;
  while (i + 1 < times.length && times[i + 1] <= secs) i++;
  return i;
}

// ---------- 一覧画面 ----------
let cards = [];
let lobbyKey = '';
async function renderLobby() {
  const live = liveNow();
  const key = live.map((x) => x.path + x.start).join('|') + S.lang;
  if (key !== lobbyKey) {
    lobbyKey = key;
    await buildLiveCards(live);
  }
  renderUpcoming();
}

async function buildLiveCards(live) {
  const grid = $('#grid');
  grid.innerHTML = '';
  cards = [];
  $('#none').hidden = live.length > 0;
  $('#none').textContent = ui().none;
  for (const show of live) {
    const s = show.s;
    const card = document.createElement('button');
    card.className = 'card' + (show.hosts.length > 1 ? ' collab' : '');
    card.style.setProperty('--c', s.color);
    // 一番上の1人は大きく（配信サイトの注目枠）。横でチャットが流れる
    const featured = cards.length === 0;
    if (featured) card.classList.add('featured');
    const tag = (S.lang === 'en' && s.en?.tag) || s.tag || '';
    card.style.setProperty('--room', `url(assets/${s.id}/room.jpg)`);
    card.innerHTML = `
      <div class="frame"><canvas></canvas><span class="live">LIVE</span><span class="viewers"></span>
        <div class="cap"></div></div>
      ${featured ? '<div class="minichat side"></div>' : ''}
      <div class="meta">${avatarHTML(s, true)}<div><div class="nm">${esc(show.hosts.map((h) => nameOf(byId(h))).join(' × '))}</div>
        <div class="ct">${esc(tag)}</div><div class="tags"><span>${S.lang === 'en' ? 'English' : '日本語'}</span><span class="st"></span></div></div></div>`;
    card.onclick = () => openStream(show);
    grid.appendChild(card);
    const c = { show, s, el: card, canvas: card.querySelector('canvas'), viewers: 300 + Math.floor(Math.random() * 4000), rig: null, ep: null, times: null, last: -1, talkUntil: 0,
      chat: card.querySelector('.minichat'), keep: featured ? 18 : 3, nextAmbient: 0 };
    cards.push(c);
  }
  await Promise.all(cards.map(async (c) => {
    c.ep = await episodeOf(c.show, primary()) || await episodeOf(c.show, 'ja');
    if (c.ep) {
      c.times = beatTimes(c.ep.beats);
    }
    try {
      const r = new Puppet.Rig(c.canvas);
      await r.load('assets/' + c.s.id, rigDef(c.s));
      c.rig = r;
    } catch (e) { c.rig = null; }
  }));
  updateCardMeta();
}

// カードの立ち絵が描けないときは、描画の枠を隠して動かない絵を出す
function cardFallback(c) {
  const bad = !c.rig || c.rig.lost();
  c.canvas.style.visibility = bad ? 'hidden' : '';
  const f = c.el.querySelector('.frame');
  if (!bad) { f.style.removeProperty('--still'); return; }
  const r = f.getBoundingClientRect(), cam = camOf(c.s), k = r.height / cam.h;
  f.style.setProperty('--still', `url(assets/${c.s.id}/base.png) ${r.width / 2 - cam.cx * k}px ${-cam.y * k}px / ${1024 * k}px ${1536 * k}px no-repeat`);
}

function updateCardMeta() {
  for (const c of cards) {
    cardFallback(c);
    c.viewers = Math.max(20, Math.round(c.viewers + (Math.random() - 0.48) * 12));
    c.el.querySelector('.viewers').textContent = ui().watching(c.viewers);
    c.el.querySelector('.st').textContent = stars(c.s.id);
  }
}

// 左の一覧（スマホでは上の横並び）：配信中のチャンネルと、オフラインの人
function renderUpcoming() {
  const live = cards.map((c) => `<li data-i="${cards.indexOf(c)}">${avatarHTML(c.s)}<div><div class="nm">${esc(c.show.hosts.map((h) => nameOf(byId(h))).join(' × '))}</div>
    <div class="ct">${esc((S.lang === 'en' && c.s.en?.tag) || c.s.tag || '')}</div></div><span class="vw">${c.viewers.toLocaleString()}</span></li>`);
  const off = OFFLINE.map((s) => `<li class="off">${avatarHTML(s)}<div><div class="nm">${esc(nameOf(s))}</div><div class="ct">${esc(ui().offline)}</div></div><span class="vw"></span></li>`);
  $('#sidelist').innerHTML = live.join('') + off.join('');
  $('#sidelist').querySelectorAll('li[data-i]').forEach((li) => { li.onclick = () => openStream(cards[+li.dataset.i].show); });
}

// 丸いアバター：立ち絵の顔のあたりを切り出す
function avatarHTML(s, big = false, id = '') {
  const size = big ? 44 : 30, k = size / 140;
  const hx = (s.rig.neck[0] - 10) * k, hy = (s.rig.neck[1] - 95) * k;
  return `<span class="av${big ? ' big' : ''}"${id ? ` id="${id}"` : ''} style="background-image:url(assets/${s.id}/base.png);background-size:${1024 * k}px ${1536 * k}px;background-position:${size / 2 - hx}px ${size / 2 - hy}px"></span>`;
}

// チャットの名前の色：人ごとに決まった色（配信サイトと同じく）
const NAME_COLORS = ['#c0392b', '#1e7d4f', '#1f5fbf', '#a0522d', '#8e44ad', '#b0477a', '#0f7b8a', '#7a6a00', '#d2691e', '#3f51b5'];
function nameColor(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return NAME_COLORS[h % NAME_COLORS.length];
}

const ICON = {
  person: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>',
  speaker: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 010 6M18.5 6.5a8 8 0 010 11"/></svg>',
  mute: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>',
};

// 一覧のカードは、その配信の今の台詞を出す（生配信なので時刻で決まる）
// 一覧のカードの小さなチャット（古いものから消える）
function cardChat(c, who, text, cls = '') {
  if (!c.chat) return;
  const el = document.createElement('div');
  el.className = 'mc ' + cls;
  el.innerHTML = `<b>${esc(who)}</b> ${esc(text)}`;
  c.chat.appendChild(el);
  while (c.chat.children.length > c.keep) c.chat.firstChild.remove();
}

// 一覧のカードは、その配信の今の台詞とチャットを出す（生配信なので時刻で決まる）
function lobbyTick(t) {
  for (const c of cards) {
    if (!c.ep) continue;
    const i = beatAt(c.times, (nowMs() - c.show.start) / 1000);
    if (i !== c.last) {
      c.last = i;
      const b = c.ep.beats[i];
      const text = b[0] === 'say' ? b[2] : b[0] === 'ask' ? b[1].q : null;
      if (text) {
        c.el.querySelector('.cap').innerHTML = `<span>${esc(text)}</span>`;
        c.talkUntil = t + Math.min(3.5, 0.6 + text.length * 0.07);
        if (c.rig && /[！!]|草/.test(text)) c.rig.beginLine(1);
        if (c.chat && c.keep > 3) cardChat(c, nameOf(byId(b[0] === 'say' ? b[1] : b[1].who)), text, 'streamer');
      } else if (b[0] === 'chat') {
        cardChat(c, b[1], b[2]);
      }
    }
    // 流れる雑談
    if (t >= c.nextAmbient) {
      c.nextAmbient = t + (c.keep > 3 ? 0.8 : 2) + Math.random() * 3;
      if (c.nextAmbient - t < 10 && Math.random() < 0.85) cardChat(c, pick(COMMON.handles.slice(0, -1)), pick(ambientNow()));
    }
    if (c.rig) c.rig.setTalking(t < c.talkUntil);
  }
}

// ---------- 配信画面 ----------
let watching = null;

class Stream {
  constructor({ show, ep, epEn, voices }) {
    this.show = show;
    this.hosts = show.hosts;
    this.opened = show.s;
    this.ep = ep;
    this.epEn = epEn;                 // 日英併記のときの英語（同じ並び）
    this.times = beatTimes(ep.beats);
    this.voice = (id) => voices[id] || {};
    const v = this.voice(this.opened.id), g = COMMON.generic;
    this.kw = fixRe(v.keywords || g.keywords);
    this.v = v;
    this.g = g;
    this.queue = [];       // 割り込み（読み上げ・返事・反応）
    this.busyUntil = 0;
    this.ask = null;
    this.talk = {};
    this.viewers = cards.find((c) => c.show === show)?.viewers || 200;
    this.pendingMine = [];
    // 生配信：今の時刻の拍から
    this.bi = beatAt(this.times, (nowMs() - show.start) / 1000);
    if (this.ep.beats[this.bi][0] === 'ask') this.bi++;
    this.firstBeat = this.bi;
    this.seen = 0;
    this.nextAmbient = 0;
    this.nextNpcTip = clock() + 40 + Math.random() * 60;
    this.done = false;
  }

  line(key, vars) {
    const a = this.v[key] || this.g[key];
    return a ? fill(pick(a), vars) : null;
  }

  // 入ってきたときの反応：初めて、覚えの段、何日も続けて
  start() {
    const id = this.opened.id, name = S.name;
    const today = dayOf(nowMs());
    const vis = S.visits[id] || { last: -1, streak: 0, count: 0 };
    const isFirst = vis.count === 0;
    if (vis.last !== today) {
      vis.streak = vis.last === today - 1 ? vis.streak + 1 : 1;
      vis.last = today;
      vis.count++;
    }
    S.visits[id] = vis;
    save();
    const lines = [];
    if (isFirst) {
      const l = this.line('first', { name });
      if (l) lines.push(l);
    } else {
      const g = (this.v.greet || this.g.greet)[affLevel(id)];
      if (g) lines.push(...g.map((l) => fill(l, { name })));
      if (vis.streak >= 3) {
        const l = this.line('streak', { name, days: vis.streak });
        if (l) lines.push(l);
      }
    }
    this.queue.push(...lines.map((l) => ['say', id, l]));
  }

  // face：表情（smile, smug, shy, surprised, annoyed）。次の台詞まで続く
  say(who, text, en, face) {
    const t = clock();
    const s = byId(who);
    rigs[who]?.setFace(face || null);
    showCaption(text, en, this.hosts.length > 1 ? s : null);
    addChat({ who: nameOf(s), text, en, streamer: true, color: s.color });
    // 弾むのは「！」や笑いの台詞だけ（毎回は揺らさない）
    if (/[！!]|[wｗ]{2}|草/.test(text)) rigs[who]?.beginLine(1);
    this.talk[who] = t + Math.min(4, 0.5 + text.length * 0.07);
    this.busyUntil = t + DATA.timing.say_base + text.length * DATA.timing.per_char;
    // 読み上げ中は、読み終わるまで次の台詞へ進まない（念のため長すぎたら打ち切る）
    if (S.tts && canSpeak()) {
      const limit = t + 5 + text.length * 0.4;
      this.busyUntil = limit;
      this.talk[who] = limit;
      const me = this;
      speak(text, who, () => { if (watching === me) { me.busyUntil = clock() + 0.25; me.talk[who] = clock(); } });
    }
  }

  step() {
    if (this.queue.length) return this.run(this.queue.shift());
    if (this.ask) return this.resolveAsk();
    if (this.pendingMine.length) {
      const text = this.pendingMine.shift();
      const r = this.reactTo(text);
      if (r) { this.queue.push(...r.map((l) => ['say', this.opened.id, l])); addAff(this.opened.id, 2); return this.step(); }
    }
    if (this.bi < this.ep.beats.length) {
      const i = this.bi++;
      this.seen++;
      if (this.seen >= (this.ep.beats.length - this.firstBeat) * 0.6) markSeen(this.show);
      return this.run(this.ep.beats[i], this.epEn?.beats[i]);
    }
    return this.finish();
  }

  run(b, en) {
    if (b[0] === 'say') return this.say(b[1], b[2], en ? en[2] : b[4], b[3]);
    if (b[0] === 'chat') { addChat({ who: b[1], text: b[2], en: en && en[2] }); this.busyUntil = clock() + DATA.timing.chat; return; }
    if (b[0] === 'ask') {
      const a = b[1], ae = en && en[1];
      this.say(a.who, a.q, ae && ae.q);
      this.ask = { a, ae, mine: null };
      this.busyUntil = clock() + DATA.timing.ask_wait;
      showChoices(a.options.map((o, i) => (ae ? `${o.c} / ${ae.options[i].c}` : o.c)), (i) => {
        if (!this.ask || this.ask.mine !== null) return;
        this.ask.mine = i;
        addChat({ who: S.name, text: a.options[i].c, mine: true });
        hideChoices();
      });
      a.npc.forEach(([who, i], k) => setTimeout(() => {
        if (watching === this) addChat({ who, text: a.options[i].c });
      }, 1500 + k * 2200 + Math.random() * 800));
    }
  }

  resolveAsk() {
    const { a, ae, mine } = this.ask;
    this.ask = null;
    hideChoices();
    let who, i;
    const chance = [0.6, 0.75, 0.9, 1, 1][affLevel(this.opened.id)];
    if (mine !== null && Math.random() < chance) { who = S.name; i = mine; for (const h of this.hosts) addAff(h, 5); }
    else { [who, i] = pick(a.npc); }
    a.options[i].r.forEach(([sp, l], k) => {
      const enLine = ae ? fill(ae.options[i].r[k][1], { name: who }) : null;
      this.queue.push(['say', sp, fill(l, { name: who }), null, enLine]);
    });
    this.step();
  }

  reactTo(text) {
    // 反応の言葉に当たったら必ず返す（候補が何通りもあれば一つを選ぶ）
    for (const [re, alts] of this.kw) if (re.test(text)) return pick(alts).map((l) => fill(l, { name: S.name, text }));
    const echo = this.v.echo || this.g.echo;
    if (text.length <= 24 && Math.random() < 0.35) return [fill(pick(echo), { name: S.name, text })];
    return null;
  }

  comment(text) {
    addChat({ who: S.name, text, mine: true });
    addAff(this.opened.id, 1);
    if (this.pendingMine.length < 2) this.pendingMine.push(text);
  }

  tip(amount, text) {
    const tier = amount >= 50000 ? 3 : amount >= 10000 ? 2 : amount >= 2000 ? 1 : 0;
    addChat({ who: S.name, text, mine: true, tip: amount, tier });
    addAff(this.opened.id, amount / 100);
    const lines = [];
    if (text) lines.push(S.lang === 'en' ? `"${text}"` : `「${text}」`);
    lines.push(...(this.v.tips || this.g.tips)[tier].map((l) => fill(l, { name: S.name })));
    this.queue.unshift(...lines.map((l) => ['say', this.opened.id, l]));
    rigs[this.opened.id]?.jiggle(0.8 + tier * 0.3);
  }

  // 回の終わり：最後まで見ていたら、名前を呼んで礼を言う
  finish() {
    markSeen(this.show);
    const total = this.ep.beats.length - this.firstBeat;
    if (!this.thanked && total > 0 && this.seen / total >= 0.6 && S.name) {
      this.thanked = true;
      const l = this.line('stayed', { name: S.name });
      if (l) { addAff(this.opened.id, 10); this.queue.push(['say', this.opened.id, l]); return this.step(); }
    }
    this.done = true;
    this.busyUntil = Infinity;
    $('#endbox').hidden = false;
  }

  tick(t) {
    for (const h of this.hosts) rigs[h]?.setTalking(t < (this.talk[h] || 0));
    if (t >= this.busyUntil) this.step();
    if (this.done) return;
    if (t >= this.nextAmbient) {
      this.nextAmbient = t + 1.2 + Math.random() * 3.5;
      addChat({ who: pick(COMMON.handles.slice(0, -1)), text: pick(ambientNow()) });
      this.viewers = Math.max(20, Math.round(this.viewers + (Math.random() - 0.47) * 8));
      $('#sviewers').innerHTML = `${ICON.person}${ui().watching(this.viewers)}`;
    }
    if (t >= this.nextNpcTip) {
      this.nextNpcTip = t + 60 + Math.random() * 90;
      const amount = pick([500, 500, 2000, 2000, 10000]);
      const who = pick(COMMON.handles.slice(0, -1));
      const tier = amount >= 10000 ? 2 : amount >= 2000 ? 1 : 0;
      addChat({ who, text: pick(COMMON.tipTexts || ['']), tip: amount, tier });
      const reader = pick(this.hosts);
      const tips = this.voice(reader).tips || COMMON.generic.tips;
      this.queue.push(['say', reader, fill(pick(tips[Math.min(tier, 1)]), { name: who })]);
    }
  }
}

// 時間帯に合わない挨拶は流さない
function ambientNow() {
  const h = new Date(nowMs() + JST).getUTCHours();
  const morning = h >= 5 && h < 11, evening = h >= 17 || h < 5;
  return COMMON.ambient.filter((t) => !(/おは|good morning/i.test(t) && !morning) && !(/こんばんは|good evening/i.test(t) && !evening));
}

let rigs = {};
const stageRigs = [];   // 配信画面の描画の枠は使い回す

// 立ち絵が描けないとき（WebGL が使えない、枠を取り上げられた）は、動かない絵を出す
function stageFallback(show) {
  const box = $('#sfallback');
  const s = show.s;
  const ok = show.hosts.every((h) => rigs[h] && !rigs[h].lost());
  box.hidden = ok;
  // 取り上げられた描画の枠は白い板として残るので、枠ごと隠す
  for (const c of [$('#scanvas'), $('#scanvas2')]) c.style.visibility = ok ? '' : 'hidden';
  if (ok) return;
  const st = $('#stage').getBoundingClientRect();
  const cam = camOf(s);
  const k = st.height / cam.h;
  box.style.backgroundImage = `url(assets/${s.id}/base.png)`;
  box.style.backgroundSize = `${1024 * k}px ${1536 * k}px`;
  box.style.backgroundPosition = `${st.width / 2 - cam.cx * k}px ${-cam.y * k}px`;
}
for (const id of ['scanvas', 'scanvas2']) {
  document.addEventListener('DOMContentLoaded', () => {
    $('#' + id).addEventListener('webglcontextlost', (e) => { e.preventDefault(); if (watching) stageFallback(watching.show); });
  });
}
window.addEventListener('resize', () => { if (watching) stageFallback(watching.show); });

async function openStream(show) {
  if (!S.name) return askName(() => openStream(show));
  const lang = primary();
  let ep = await episodeOf(show, lang);
  if (!ep) ep = await episodeOf(show, 'ja');
  if (!ep) return toast(ui().loadFail);
  const epEn = S.lang === 'both' ? await episodeOf(show, 'en') : null;
  const voices = {};
  for (const h of show.hosts) voices[h] = await getOpt(`data/${lang}/voice/${h}.json`) || await getOpt(`data/ja/voice/${h}.json`) || {};
  const s = show.s;
  $('#lobby').hidden = true;
  $('#stream').hidden = false;
  $('#endbox').hidden = true;
  $('#chat').innerHTML = '';
  $('#sname').textContent = show.hosts.map((h) => nameOf(byId(h))).join(' × ');
  $('#stag').textContent = (S.lang === 'en' && s.en?.tag) || s.tag || '';
  $('#savatar').outerHTML = avatarHTML(s, true, 'savatar');
  $('#stitle').textContent = ep.title;
  $('#caption').textContent = '';
  $('#captionEn').textContent = '';
  $('#stage').style.setProperty('--c', s.color);
  $('#stage').style.setProperty('--room', `url(assets/${s.id}/room.jpg)`);
  $('#stage').classList.toggle('duo', show.hosts.length > 1);
  // 一覧のカードの描画の枠を返してから、配信画面の枠を使う（スマホは同時に持てる数が少ない）
  for (const c of cards) { c.rig?.release(); c.rig = null; }
  lobbyKey = '';
  rigs = {};
  const canvases = [$('#scanvas'), $('#scanvas2')];
  for (let i = 0; i < show.hosts.length && i < 2; i++) {
    try {
      const r = stageRigs[i] && !stageRigs[i].lost() ? stageRigs[i] : new Puppet.Rig(canvases[i]);
      stageRigs[i] = r;
      await r.load('assets/' + show.hosts[i], rigDef(byId(show.hosts[i])));
      rigs[show.hosts[i]] = r;
    } catch (e) { /* 描けなければ、動かない絵を出す */ }
  }
  stageFallback(show);
  watching = new Stream({ show, ep, epEn, voices });
  watching.start();
  refreshWallet();
  history.pushState({ s: s.id }, '', location.search + '#' + s.id);
}

function closeStream() {
  watching = null;
  stopSpeaking();
  hideChoices();
  $('#stream').hidden = true;
  $('#lobby').hidden = false;
  lobbyKey = '';
  renderLobby();
}
window.addEventListener('popstate', () => { if (watching) closeStream(); });

function showCaption(text, en, speaker) {
  const el = $('#caption');
  el.textContent = '';
  el.classList.remove('in');
  void el.offsetWidth;
  el.classList.add('in');
  $('#captionEn').textContent = en || '';
  const who = $('#capwho');
  who.hidden = !speaker;
  if (speaker) { who.textContent = nameOf(speaker); who.style.color = speaker.color; }
  let i = 0;
  clearInterval(showCaption.timer);
  showCaption.timer = setInterval(() => {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) clearInterval(showCaption.timer);
  }, 38);
}

function addChat({ who, text, en, mine, streamer, tip, tier, color }) {
  const box = $('#chat');
  const el = document.createElement('div');
  el.className = 'msg' + (mine ? ' mine' : '') + (streamer ? ' streamer' : '') + (tip ? ' tip t' + tier : '');
  const nameStyle = ` style="color:${color || nameColor(who)}"`;
  const sub = en ? `<span class="en">${esc(en)}</span>` : '';
  el.innerHTML = tip
    ? `<div class="tiphead"><b>${esc(who)}</b><span>${yen(tip)}</span></div>${text ? `<div>${esc(text)}</div>` : ''}`
    : `<b${nameStyle}>${esc(who)}</b> ${esc(text)}${sub}`;
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.appendChild(el);
  while (box.children.length > 150) box.firstChild.remove();
  if (atBottom || mine) box.scrollTop = box.scrollHeight;
}

function showChoices(labels, onPick) {
  const el = $('#choices');
  el.innerHTML = '';
  labels.forEach((l, i) => {
    const b = document.createElement('button');
    b.textContent = l;
    b.onclick = () => onPick(i);
    el.appendChild(b);
  });
  el.hidden = false;
}
function hideChoices() { $('#choices').hidden = true; }

// ---------- 入力 ----------
function sendComment() {
  const input = $('#say');
  const text = input.value.trim().slice(0, 60);
  if (!text || !watching) return;
  input.value = '';
  watching.comment(text);
}

const TIP_TIERS = [500, 2000, 10000, 50000];
function openTip() {
  const box = $('#tipbox');
  box.innerHTML = '';
  for (const a of TIP_TIERS) {
    const b = document.createElement('button');
    b.className = 'tier t' + TIP_TIERS.indexOf(a);
    b.textContent = yen(a);
    b.disabled = S.yen < a;
    b.onclick = () => {
      if (S.yen < a || !watching) return;
      S.yen -= a;
      const text = $('#say').value.trim().slice(0, 40);
      $('#say').value = '';
      watching.tip(a, text);
      box.hidden = true;
      refreshWallet();
      save();
    };
    box.appendChild(b);
  }
  const note = document.createElement('p');
  note.textContent = ui().tipNote;
  box.appendChild(note);
  box.hidden = !box.hidden;
}

function askName(then) {
  const m = $('#namebox');
  m.hidden = false;
  const input = $('#nameinput');
  input.placeholder = ui().anon;
  input.focus();
  $('#nameok').onclick = () => {
    S.name = input.value.trim().slice(0, 16) || ui().anon;
    save();
    m.hidden = true;
    then && then();
  };
}

async function cycleLang() {
  S.lang = { ja: 'en', en: 'both', both: 'ja' }[S.lang] || 'ja';
  save();
  await loadCommon();
  applyUI();
  refreshWallet();
  if (watching) { const show = watching.show; closeStream(); openStream(show); } else { lobbyKey = ''; renderLobby(); }
}
async function loadCommon() {
  COMMON = await getOpt(`data/${primary()}/common.json`) || await getJSON('data/ja/common.json');
}

// 閉じていた間にたまったお金
function settleAway() {
  const away = (Date.now() - S.lastSeen) / 3600000;
  S.lastSeen = Date.now();
  if (away < 1 / 60) return;
  const h = Math.min(away, AWAY_CAP);
  const got = hourly() * h;
  S.yen += got;
  save();
  $('#awaytext').innerHTML = ui().awayText(yen(got));
  $('#away').hidden = false;
}

// ---------- ループ ----------
let lastSec = 0;
function frame() {
  const t = clock();
  if (watching) {
    watching.tick(t);
    const n = watching.hosts.length;
    watching.hosts.forEach((h, i) => rigs[h]?.render(t, duoCam(camOf(byId(h)), n, i)));
  } else {
    lobbyTick(t);
    for (const c of cards) if (c.rig) c.rig.render(t, camOf(c.s));
  }
  if (t - lastSec >= 1) {
    const dt = t - lastSec;
    lastSec = t;
    S.lastSeen = Date.now();
    refreshWallet();
    if (Math.floor(t) % 10 === 0) {
      save();
      if (!watching) { updateCardMeta(); renderLobby(); }
    }
  }
  requestAnimationFrame(frame);
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { S.lastSeen = Date.now(); save(); }
  else settleAway();
});

// ---------- 起動 ----------
window.addEventListener('DOMContentLoaded', async () => {
  load();
  $('#back').onclick = () => history.back();
  $('#endback').onclick = () => history.back();
  $('#send').onclick = sendComment;
  $('#say').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) sendComment(); });
  $('#tipbtn').onclick = openTip;
  $('#langbtn').onclick = cycleLang;
  $('#ttsbtn').hidden = !canSpeak();
  const ttsLabel = () => { $('#ttsbtn').innerHTML = S.tts ? ICON.speaker : ICON.mute; $('#ttsbtn').classList.toggle('on', S.tts); };
  ttsLabel();
  $('#ttsbtn').onclick = () => { S.tts = !S.tts; save(); ttsLabel(); if (!S.tts) stopSpeaking(); };
  $('#awayok').onclick = () => { $('#away').hidden = true; };
  try {
    DATA = await getJSON('data/index.json');
    STREAMERS = DATA.streamers;
    await loadCommon();
  } catch (e) {
    document.body.textContent = '配信データを読み込めませんでした。 / Could not load the data.';
    return;
  }
  if (params.has('fresh')) { S = fresh(); save(); }
  decideShows();
  applyUI();
  settleAway();
  refreshWallet();
  await renderLobby();
  if (!S.name) askName();
  requestAnimationFrame(frame);
});

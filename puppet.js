// 立ち絵を WebGL の格子に貼って動かす（呼吸・頭の揺れ・話し始めの胸の弾み・まばたき・口パク）。
// 座標はすべて base.png（1024x1536）の画素。
'use strict';

const Puppet = (() => {
  const VS = `
    attribute vec2 aPos; attribute vec2 aUV;
    uniform vec2 uView; uniform vec4 uCam;
    varying vec2 vUV;
    void main() {
      vec2 p = (aPos - uCam.xy) * uCam.z;
      gl_Position = vec4(p.x / uView.x * 2.0 - 1.0, 1.0 - p.y / uView.y * 2.0, 0.0, 1.0);
      vUV = aUV;
    }`;
  const FS = `
    precision mediump float;
    uniform sampler2D uTex; varying vec2 vUV;
    void main() { gl_FragColor = texture2D(uTex, vUV); }`;

  function shader(gl, type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }

  function loadImage(src) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  const smooth = (e0, e1, x) => {
    const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
    return t * t * (3 - 2 * t);
  };

  class Rig {
    constructor(canvas) {
      const gl = canvas.getContext('webgl', { premultipliedAlpha: false, alpha: true, antialias: true });
      if (!gl) throw new Error('WebGL が使えません');
      this.gl = gl;
      this.canvas = canvas;
      const prog = gl.createProgram();
      gl.attachShader(prog, shader(gl, gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, shader(gl, gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      gl.useProgram(prog);
      this.prog = prog;
      this.loc = {
        pos: gl.getAttribLocation(prog, 'aPos'),
        uv: gl.getAttribLocation(prog, 'aUV'),
        view: gl.getUniformLocation(prog, 'uView'),
        cam: gl.getUniformLocation(prog, 'uCam'),
      };
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      this.posBuf = gl.createBuffer();
      this.uvBuf = gl.createBuffer();
      this.idxBuf = gl.createBuffer();
      this.parts = {};
      this.textures = [];
      this.state = { eyes: 'open', mouth: 'closed', face: null };
      this.springs = null;  // 胸のばね（左右それぞれ）
      this.lastT = null;
      this.talking = false;
      this.nextBlink = 2;
      this.blinkAt = -99;
      this.mouthAt = 0;
    }

    async load(dir, def) {
      this.freeTextures();
      this.def = def;
      this.springs = null;
      const base = await loadImage(dir + '/base.png');
      if (!base) throw new Error('立ち絵が読めません: ' + dir);
      this.W = base.width;
      this.H = base.height;
      this.base = this.mesh(this.texture(base), 0, 0, this.W, this.H, 28, 42);
      let parts = null;
      try {
        const r = await fetch(dir + '/parts.json');
        if (r.ok) parts = await r.json();
      } catch (e) { parts = null; }
      if (parts) {
        const faces = ['face_smile', 'face_smug', 'face_shy', 'face_surprised', 'face_annoyed'];
        for (const [group, names] of [['face', faces], ['eyes', ['eyes_half', 'eyes_closed']], ['mouth', ['mouth_half', 'mouth_open']]]) {
          const rect = parts[group];
          if (!rect) continue;
          for (const n of names) {
            const img = await loadImage(dir + '/' + n + '.png');
            if (img) this.parts[n] = this.mesh(this.texture(img), rect.x, rect.y, rect.w, rect.h, 4, 4);
          }
        }
      }
    }

    // 作ったテクスチャを覚えておき、読み直すときに片付ける（描画の枠の中に溜めない）
    freeTextures() {
      for (const t of this.textures || []) this.gl.deleteTexture(t);
      this.textures = [];
      this.parts = {};
      this.base = null;
    }

    // 描画の枠（WebGL のコンテキスト）をブラウザに返す。スマホは同時に持てる数が少ない
    release() {
      this.freeTextures();
      const ext = this.gl.getExtension('WEBGL_lose_context');
      if (ext) ext.loseContext();
    }

    lost() { return this.gl.isContextLost(); }

    texture(img) {
      const gl = this.gl;
      const t = gl.createTexture();
      this.textures.push(t);
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    }

    // 矩形 (x,y,w,h) を nx×ny の格子にした網。頂点は毎フレーム動かす。
    mesh(tex, x, y, w, h, nx, ny) {
      const rest = [], uv = [], idx = [];
      for (let j = 0; j <= ny; j++) {
        for (let i = 0; i <= nx; i++) {
          rest.push(x + w * i / nx, y + h * j / ny);
          uv.push(i / nx, j / ny);
        }
      }
      for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
          const a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1;
          idx.push(a, b, c, b, d, c);
        }
      }
      return { tex, rest: new Float32Array(rest), pos: new Float32Array(rest.length), uv: new Float32Array(uv), idx: new Uint16Array(idx) };
    }

    // 話し始めに呼ぶ：胸が弾んで、ばねで揺れ戻る。strength は勢い（「！」で強く）。
    beginLine(strength = 1) { this.jiggle(strength); }
    jiggle(strength = 1) {
      if (!this.springs) return;
      this.springs.forEach((sp, k) => {
        sp.vy -= this.def.bounce * 11 * strength * (1 - 0.12 * k);
        sp.vx += (k === 0 ? -1 : 1) * this.def.bounce * 1.5 * strength;
      });
    }
    setTalking(on) { this.talking = on; }
    setFace(name) { this.state.face = name; }

    // 体（胸の付け根）の動き：呼吸、話している間の小さな上下、体の揺れ
    anchor(t, k) {
      const d = this.def;
      const [cx, cy] = d.chest[k];
      const up = smooth(d.waist, d.neck[1] - 120, cy);
      const breath = -Math.sin(t * 2 * Math.PI / 4.4) * d.breath * up;
      const bob = this.talking ? Math.sin(t * 2 * Math.PI * 2.6) * 0.4 : 0;
      const sway = Math.sin(t * 2 * Math.PI / 9.1) * d.sway * (1 - cy / this.H);
      return [sway, breath + bob];
    }

    // 胸のばねを進める：付け根に遅れてついていき、行き過ぎて揺れ戻る
    physics(t) {
      const d = this.def;
      if (!this.springs) this.springs = d.chest.map(() => ({ x: 0, y: 0, vx: 0, vy: 0, ax: 0, ay: 0 }));
      let dt = this.lastT === null ? 0 : t - this.lastT;
      this.lastT = t;
      if (dt <= 0) return;
      dt = Math.min(dt, 0.05);
      const steps = Math.ceil(dt / 0.008), h = dt / steps;
      this.springs.forEach((sp, k) => {
        // 固めのばねを強く止める：揺れは小さく、1〜2回で収まる（2026-10-27「揺れすぎ」の指摘）
        const kk = 170 + k * 14, damp = 15;
        for (let i = 0; i < steps; i++) {
          const tt = t - dt + (i + 1) * h;
          const [axn, ayn] = this.anchor(tt, k);
          const vax = (axn - sp.ax) / h, vay = (ayn - sp.ay) / h;
          sp.ax = axn; sp.ay = ayn;
          // x, y は付け根からのずれ。付け根が動くと、慣性でその分だけ遅れる
          sp.vx += (-kk * sp.x - damp * sp.vx) * h - (vax - (sp.pvax || 0));
          sp.vy += (-kk * sp.y - damp * sp.vy) * h - (vay - (sp.pvay || 0));
          sp.pvax = vax; sp.pvay = vay;
          sp.x += sp.vx * h;
          sp.y += sp.vy * h;
          const lim = d.bounce * 1.2;
          sp.y = Math.max(-lim, Math.min(lim, sp.y));
          sp.x = Math.max(-lim / 2, Math.min(lim / 2, sp.x));
        }
      });
    }

    // 立ち絵の上の点 (x,y) が時刻 t にどこへ動くか。
    displace(x, y, t) {
      const d = this.def;
      let px = x, py = y;
      // 呼吸：腰より上が少し持ち上がる。
      const breath = Math.sin(t * 2 * Math.PI / 4.4);
      const up = smooth(d.waist, d.neck[1] - 120, y);
      py -= breath * d.breath * up;
      // 胸：ばねのずれを、胸の楕円の中ほど強く。上側（付け根）は動きを小さく、下側を大きく。
      if (this.springs) {
        for (let k = 0; k < d.chest.length; k++) {
          const [cx, cy, r] = d.chest[k];
          const dist = Math.hypot((x - cx) / 1.1, y - cy) / r;
          if (dist < 1) {
            const w = (1 - smooth(0.2, 0.85, dist)) * (0.45 + 0.55 * smooth(cy - r, cy + r * 0.6, y));
            py += w * this.springs[k].y;
            px += w * this.springs[k].x;
          }
        }
      }
      // 頭：首を軸にゆっくり傾く。話している間は小さくうなずく。
      const [nx, ny] = d.neck;
      const headW = 1 - smooth(ny - 60, ny + 60, y);
      if (headW > 0) {
        let a = d.tilt * Math.PI / 180 * Math.sin(t * 2 * Math.PI / 7.3);
        let nod = this.talking ? Math.sin(t * 7.1) * 1.2 : 0;
        a *= headW;
        const dx = px - nx, dy = py - ny;
        const c = Math.cos(a), s = Math.sin(a);
        px = nx + dx * c - dy * s;
        py = ny + dx * s + dy * c + nod * headW;
      }
      // 体全体のわずかな揺れ（足元を軸に）。
      const sway = Math.sin(t * 2 * Math.PI / 9.1) * d.sway;
      px += sway * (1 - y / this.H);
      return [px, py];
    }

    update(m, t) {
      for (let i = 0; i < m.rest.length; i += 2) {
        const [x, y] = this.displace(m.rest[i], m.rest[i + 1], t);
        m.pos[i] = x;
        m.pos[i + 1] = y;
      }
    }

    drawMesh(m) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
      gl.bufferData(gl.ARRAY_BUFFER, m.pos, gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(this.loc.pos);
      gl.vertexAttribPointer(this.loc.pos, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.uvBuf);
      gl.bufferData(gl.ARRAY_BUFFER, m.uv, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(this.loc.uv);
      gl.vertexAttribPointer(this.loc.uv, 2, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.idxBuf);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, m.idx, gl.STATIC_DRAW);
      gl.bindTexture(gl.TEXTURE_2D, m.tex);
      gl.drawElements(gl.TRIANGLES, m.idx.length, gl.UNSIGNED_SHORT, 0);
    }

    // まばたきと口の形を時刻から決める。
    face(t) {
      if (t >= this.nextBlink) {
        this.blinkAt = t;
        this.nextBlink = t + 2.2 + Math.random() * 4.5;
      }
      const b = t - this.blinkAt;
      this.state.eyes = b < 0.05 ? 'half' : b < 0.13 ? 'closed' : b < 0.19 ? 'half' : 'open';
      if (this.talking) {
        if (t - this.mouthAt > 0.085) {
          this.mouthAt = t;
          const r = Math.random();
          this.state.mouth = r < 0.3 ? 'closed' : r < 0.65 ? 'half' : 'open';
        }
      } else {
        this.state.mouth = 'closed';
      }
    }

    // cam: 画面に映す立ち絵の範囲 {x, y, scale}
    render(t, cam) {
      this.t = t;
      const gl = this.gl;
      if (!this.base || gl.isContextLost()) return;
      const c = this.canvas;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
      if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      const scale = h / cam.h;
      // shift：人物を画面の左右へずらす割合（コラボで二人を並べる）
      const camX = cam.cx - (w / scale) / 2 + (cam.shift || 0) * (w / scale);
      gl.uniform2f(this.loc.view, w, h);
      gl.uniform4f(this.loc.cam, camX, cam.y, scale, 0);
      this.face(t);
      this.physics(t);
      this.update(this.base, t);
      this.drawMesh(this.base);
      // 表情（上の顔）→ まばたき → 口 の順に重ねる
      const fc = this.state.face && this.parts['face_' + this.state.face];
      if (fc) { this.update(fc, t); this.drawMesh(fc); }
      // 表情が出ている間はまばたきを重ねない（閉じ目は元の顔から作ったので、頬紅などの上で縁が浮く）
      const eyes = !fc && this.parts['eyes_' + this.state.eyes];
      if (eyes) { this.update(eyes, t); this.drawMesh(eyes); }
      const mouth = this.parts['mouth_' + this.state.mouth];
      if (mouth) { this.update(mouth, t); this.drawMesh(mouth); }
    }
  }

  return { Rig };
})();

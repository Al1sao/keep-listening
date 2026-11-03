/* ===========================================================================
 * Keep Listening - estudio 3D
 * Vinilo y particulas en WebGL que reaccionan al audio del
 * reproductor. Si WebGL no esta disponible queda un vinilo en CSS.
 * =========================================================================== */
(function () {
  "use strict";

  const reduce = window.KL.util.reduce;
  const ACENTOS = [
    [0.776, 0.961, 0.306],
    [0.941, 0.765, 0.416],
    [0.553, 0.949, 0.78],
    [0.878, 0.541, 0.416],
    [0.62, 0.78, 0.98],
  ];

  const vivo = {
    sonando: false,
    spin: 0,
    accent: ACENTOS[0],
    disco: { estilo: 0, a: [0.78, 0.96, 0.3], b: [0.94, 0.76, 0.42] },
    portada: "",
    titulo: "Nada en reproducción",
    artista: "Elegí un tema y el vinilo lo sigue desde acá.",
  };

  // -----------------------------------------------------------------------
  // Diseño del disco: cada tema tiene el suyo, siempre el mismo. El hip hop
  // tira a negro, salpicado y neón; el pop, a color, marmolado y picture disc.
  // -----------------------------------------------------------------------
  const DISENOS = ["Negro clásico", "Color translúcido", "Marmolado", "Salpicado", "Picture disc", "Neón"];
  const POR_GENERO = {
    "hip hop": [0, 3, 5, 4, 2],
    pop: [1, 2, 4, 3, 5],
  };

  window.KLDisco = {
    diseno(pista) {
      const clave = String((pista && (pista.id || pista.titulo)) || "keep");
      let hash = 0;
      for (let i = 0; i < clave.length; i += 1) hash = (hash * 33 + clave.charCodeAt(i)) >>> 0;
      const genero = String((pista && pista.genero) || "").toLowerCase();
      const opciones = POR_GENERO[genero] || [0, 1, 2, 3, 4, 5];
      const estilo = opciones[hash % opciones.length];
      return { estilo, nombre: DISENOS[estilo] };
    },
  };

  // Graves, medios y agudos los lee el núcleo una vez por cuadro (KL.nivel).
  const nivel = (window.KL && window.KL.nivel) || { bass: 0, mid: 0, high: 0 };

  function acentoDe(texto) {
    let hash = 0;
    const fuente = texto || "keep";
    for (let i = 0; i < fuente.length; i += 1) hash = (hash * 31 + fuente.charCodeAt(i)) >>> 0;
    return ACENTOS[hash % ACENTOS.length];
  }

  // -----------------------------------------------------------------------
  // Matrices 4x4, columna mayor (el orden que espera WebGL)
  // -----------------------------------------------------------------------
  function mat() {
    return new Float32Array(16);
  }

  function multiply(out, a, b) {
    const r = mat();
    for (let c = 0; c < 4; c += 1) {
      for (let f = 0; f < 4; f += 1) {
        r[c * 4 + f] =
          a[f] * b[c * 4] +
          a[4 + f] * b[c * 4 + 1] +
          a[8 + f] * b[c * 4 + 2] +
          a[12 + f] * b[c * 4 + 3];
      }
    }
    out.set(r);
    return out;
  }

  function perspective(out, fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2);
    const nf = 1 / (near - far);
    out.set([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * nf, -1,
      0, 0, 2 * far * near * nf, 0,
    ]);
    return out;
  }

  function lookAt(out, eye, target, up) {
    let zx = eye[0] - target[0];
    let zy = eye[1] - target[1];
    let zz = eye[2] - target[2];
    let len = Math.hypot(zx, zy, zz) || 1;
    zx /= len;
    zy /= len;
    zz /= len;
    let xx = up[1] * zz - up[2] * zy;
    let xy = up[2] * zx - up[0] * zz;
    let xz = up[0] * zy - up[1] * zx;
    len = Math.hypot(xx, xy, xz) || 1;
    xx /= len;
    xy /= len;
    xz /= len;
    const yx = zy * xz - zz * xy;
    const yy = zz * xx - zx * xz;
    const yz = zx * xy - zy * xx;
    out[0] = xx;
    out[1] = yx;
    out[2] = zx;
    out[3] = 0;
    out[4] = xy;
    out[5] = yy;
    out[6] = zy;
    out[7] = 0;
    out[8] = xz;
    out[9] = yz;
    out[10] = zz;
    out[11] = 0;
    out[12] = -(xx * eye[0] + xy * eye[1] + xz * eye[2]);
    out[13] = -(yx * eye[0] + yy * eye[1] + yz * eye[2]);
    out[14] = -(zx * eye[0] + zy * eye[1] + zz * eye[2]);
    out[15] = 1;
    return out;
  }

  function rotateX(angulo) {
    const c = Math.cos(angulo);
    const s = Math.sin(angulo);
    const out = mat();
    out.set([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]);
    return out;
  }

  function rotateY(angulo) {
    const c = Math.cos(angulo);
    const s = Math.sin(angulo);
    const out = mat();
    out.set([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]);
    return out;
  }

  function traducir(x, y, z) {
    const out = mat();
    out.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]);
    return out;
  }

  function escalar(s) {
    const out = mat();
    out.set([s, 0, 0, 0, 0, s, 0, 0, 0, 0, s, 0, 0, 0, 0, 1]);
    return out;
  }

  // -----------------------------------------------------------------------
  // Geometria
  // -----------------------------------------------------------------------
  function intercalar(posiciones, uvs, normales) {
    const n = posiciones.length / 3;
    const datos = new Float32Array(n * 8);
    for (let i = 0; i < n; i += 1) {
      datos[i * 8] = posiciones[i * 3];
      datos[i * 8 + 1] = posiciones[i * 3 + 1];
      datos[i * 8 + 2] = posiciones[i * 3 + 2];
      datos[i * 8 + 3] = uvs[i * 2];
      datos[i * 8 + 4] = uvs[i * 2 + 1];
      datos[i * 8 + 5] = normales[i * 3];
      datos[i * 8 + 6] = normales[i * 3 + 1];
      datos[i * 8 + 7] = normales[i * 3 + 2];
    }
    return datos;
  }

  function disco(segmentos) {
    const pos = [0, 0, 0];
    const uv = [0.5, 0.5];
    const nor = [0, 1, 0];
    const idx = [];
    for (let i = 0; i <= segmentos; i += 1) {
      const a = (i / segmentos) * Math.PI * 2;
      const x = Math.cos(a);
      const z = Math.sin(a);
      pos.push(x, 0, z);
      uv.push(x * 0.5 + 0.5, z * 0.5 + 0.5);
      nor.push(0, 1, 0);
    }
    for (let i = 1; i <= segmentos; i += 1) idx.push(0, i, i + 1);
    return { datos: intercalar(pos, uv, nor), indices: new Uint16Array(idx) };
  }

  function brazo() {
    const pos = [];
    const uv = [];
    const nor = [];
    function quad(x0, x1, z0, z1, y) {
      const base = pos.length / 3;
      [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]].forEach((p) => {
        pos.push(p[0], p[1], p[2]);
        uv.push(0, 0);
        nor.push(0, 1, 0);
      });
      return [base, base + 1, base + 2, base, base + 2, base + 3];
    }
    const idx = [...quad(0.16, 0.92, -0.018, 0.018, 0.045), ...quad(0.78, 1.02, -0.055, 0.055, 0.03)];
    return { datos: intercalar(pos, uv, nor), indices: new Uint16Array(idx) };
  }

  function particulas(cantidad) {
    const pos = [];
    const uv = [];
    const nor = [];
    for (let i = 0; i < cantidad; i += 1) {
      const ang = Math.random() * Math.PI * 2;
      const radio = 1.15 + Math.random() * 0.85;
      pos.push(Math.cos(ang) * radio, Math.random() * 2.2 - 1.1, Math.sin(ang) * radio);
      uv.push(Math.random(), 0);
      nor.push(0, 1, 0);
    }
    return { datos: intercalar(pos, uv, nor), indices: null, cantidad };
  }

  const VERT = `
    precision mediump float;
    attribute vec3 aPos;
    attribute vec2 aUv;
    attribute vec3 aNormal;
    uniform mat4 uMvp;
    uniform float uMode;
    uniform float uTime;
    uniform float uBass;
    uniform float uPunto;
    varying vec3 vPos;
    varying vec2 vUv;
    varying vec3 vNormal;
    void main() {
      vUv = aUv;
      vNormal = aNormal;
      if (uMode > 2.5) {
        vec3 p = aPos;
        p.y = mod(p.y + uTime * (0.12 + aUv.x * 0.28) + uBass, 2.4) - 1.2;
        p.x += sin(uTime * 0.6 + aUv.x * 6.2831) * 0.06;
        vPos = p;
        gl_PointSize = (1.2 + aUv.x * 1.4 + uBass * 1.6) * uPunto;
        gl_Position = uMvp * vec4(p, 1.0);
        return;
      }
      vPos = aPos;
      gl_Position = uMvp * vec4(aPos, 1.0);
    }
  `;

  const FRAG = `
    precision mediump float;
    varying vec3 vPos;
    varying vec2 vUv;
    varying vec3 vNormal;
    uniform float uMode;
    uniform float uTime;
    uniform float uBass;
    uniform float uHasTex;
    uniform vec3 uAccent;
    uniform sampler2D uTex;
    uniform float uEstilo;
    uniform vec3 uColA;
    uniform vec3 uColB;

    float azar(vec2 p) {
      return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453);
    }

    // Cara del disco según el diseño del tema (ver KLDisco más abajo).
    vec3 cara(float r, float ang, vec2 p) {
      if (uEstilo < 0.5) return vec3(0.11, 0.11, 0.12);
      if (uEstilo < 1.5) {
        // Color translúcido: más claro hacia el borde, como la luz atravesándolo.
        return uColA * (0.75 + r * 0.35);
      }
      if (uEstilo < 2.5) {
        float veta = sin(ang * 3.0 + r * 16.0 + sin(r * 29.0 + ang * 5.0) * 1.7) * 0.5 + 0.5;
        return mix(uColA, uColB, smoothstep(0.25, 0.75, veta));
      }
      if (uEstilo < 3.5) {
        vec2 q = p * 7.0;
        vec2 celda = floor(q);
        float h = azar(celda);
        vec2 centro = vec2(azar(celda + 1.7), azar(celda + 9.2)) - 0.5;
        float gota = 1.0 - smoothstep(0.1 + h * 0.16, 0.14 + h * 0.16, length(fract(q) - 0.5 - centro * 0.4));
        vec3 tinta = h > 0.8 ? uColB : uColA;
        return mix(vec3(0.09), tinta, gota * step(0.45, h));
      }
      if (uEstilo < 4.5) {
        vec3 foto = texture2D(uTex, p * 0.5 + 0.5).rgb;
        return mix(uColA, foto, uHasTex);
      }
      float linea = smoothstep(0.86, 1.0, sin(r * 70.0) * 0.5 + 0.5);
      return vec3(0.03) + uColA * linea * (0.55 + uBass * 1.6);
    }

    void main() {
      if (uMode > 2.5) {
        vec2 pc = gl_PointCoord * 2.0 - 1.0;
        if (dot(pc, pc) > 1.0) discard;
        gl_FragColor = vec4(0.93, 0.9, 0.84, 0.35);
        return;
      }
      if (uMode > 1.5) {
        vec3 n = normalize(vNormal);
        float fres = pow(1.0 - abs(dot(n, vec3(0.15, 0.65, 0.75))), 1.6);
        vec3 col = mix(uAccent * 0.35, vec3(1.0), fres);
        gl_FragColor = vec4(col, 0.55 + fres * 0.4);
        return;
      }
      if (uMode > 0.5) {
        gl_FragColor = vec4(0.86, 0.84, 0.78, 1.0);
        return;
      }
      float r = length(vPos.xz);
      float ang = atan(vPos.z, vPos.x);
      bool foto = uEstilo > 3.5 && uEstilo < 4.5;
      float agujero = smoothstep(0.045, 0.06, r);
      // En el picture disc la portada ocupa todo: la etiqueta queda chiquita.
      float radioSello = foto ? 0.13 : 0.31;
      float etiqueta = 1.0 - smoothstep(radioSello - 0.03, radioSello + 0.03, r);
      float surco = 0.5 + 0.5 * sin(r * 220.0);
      vec3 vinilo = cara(r, ang, vPos.xz) + surco * (foto ? 0.008 : 0.02);
      float brillo = pow(max(cos(ang + 0.5), 0.0), 28.0);
      vinilo += brillo * vec3(0.16) * (1.0 - etiqueta);
      // Canto del disco: un filo de luz.
      vinilo += vec3(0.12) * smoothstep(0.965, 0.995, r);
      vec4 tex = texture2D(uTex, vPos.xz / (radioSello * 2.0) + 0.5);
      vec3 sello = foto ? uColB : mix(vec3(0.18, 0.17, 0.16), tex.rgb, uHasTex);
      vec3 col = mix(vinilo, sello, etiqueta) * agujero;
      col += vec3(0.85, 0.82, 0.74) * uBass * 0.05 * (1.0 - etiqueta);
      gl_FragColor = vec4(col, 1.0);
    }
  `;

  function compilar(gl, tipo, fuente) {
    const shader = gl.createShader(tipo);
    gl.shaderSource(shader, fuente);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function crearMalla(gl, geometria) {
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, geometria.datos, gl.STATIC_DRAW);
    let ibo = null;
    if (geometria.indices) {
      ibo = gl.createBuffer();
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, geometria.indices, gl.STATIC_DRAW);
    }
    return {
      buffer,
      ibo,
      cantidad: geometria.indices ? geometria.indices.length : geometria.cantidad || geometria.datos.length / 8,
    };
  }

  function Estudio(canvas, opts) {
    this.canvas = canvas;
    this.hero = !!opts.hero;
    this.gl = canvas.getContext("webgl", { alpha: true, antialias: true, premultipliedAlpha: false });
    this.ok = false;
    this.texturaLista = 0;
    this.portadaCargada = "";
    this.error = "";
    if (!this.gl) {
      this.error = "sin-webgl";
      return;
    }
    const gl = this.gl;
    const vs = compilar(gl, gl.VERTEX_SHADER, VERT);
    const fs = compilar(gl, gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) {
      this.error = "shader";
      return;
    }
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.bindAttribLocation(prog, 0, "aPos");
    gl.bindAttribLocation(prog, 1, "aUv");
    gl.bindAttribLocation(prog, 2, "aNormal");
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      this.error = (gl.getProgramInfoLog(prog) || "link").slice(0, 180);
      return;
    }
    this.prog = prog;
    this.u = {
      mvp: gl.getUniformLocation(prog, "uMvp"),
      mode: gl.getUniformLocation(prog, "uMode"),
      time: gl.getUniformLocation(prog, "uTime"),
      bass: gl.getUniformLocation(prog, "uBass"),
      punto: gl.getUniformLocation(prog, "uPunto"),
      accent: gl.getUniformLocation(prog, "uAccent"),
      hasTex: gl.getUniformLocation(prog, "uHasTex"),
      estilo: gl.getUniformLocation(prog, "uEstilo"),
      colA: gl.getUniformLocation(prog, "uColA"),
      colB: gl.getUniformLocation(prog, "uColB"),
      tex: gl.getUniformLocation(prog, "uTex"),
    };
    this.disco = crearMalla(gl, disco(96));
    this.brazo = crearMalla(gl, brazo());
    this.puntos = crearMalla(gl, particulas(18));
    this.textura = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.textura);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([198, 245, 78, 255]));
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.p = mat();
    this.v = mat();
    this.mvp = mat();
    this.tmp = mat();
    this.ok = true;
  }

  Estudio.prototype.cargarPortada = function cargarPortada(url) {
    if (!url || url === this.portadaCargada || !this.ok) return;
    this.portadaCargada = url;
    const img = new Image();
    // Las portadas de Apple vienen de otro dominio: sin permiso CORS WebGL no las acepta.
    img.crossOrigin = "anonymous";
    const self = this;
    img.onload = function () {
      if (self.portadaCargada !== url) return;
      const gl = self.gl;
      try {
        gl.bindTexture(gl.TEXTURE_2D, self.textura);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        self.texturaLista = 1;
      } catch (error) {
        self.texturaLista = 0;
      }
    };
    // Si la tapa nueva no carga (CORS, red), no queda la del tema anterior en la etiqueta.
    img.onerror = function () {
      if (self.portadaCargada === url) self.texturaLista = 0;
    };
    img.src = url;
  };

  Estudio.prototype.enlazar = function enlazar(malla) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, malla.buffer);
    gl.enableVertexAttribArray(0);
    gl.enableVertexAttribArray(1);
    gl.enableVertexAttribArray(2);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 32, 0);
    gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 32, 12);
    gl.vertexAttribPointer(2, 3, gl.FLOAT, false, 32, 20);
    if (malla.ibo) gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, malla.ibo);
  };

  Estudio.prototype.dibujar = function dibujar(malla, modelo, modo) {
    const gl = this.gl;
    multiply(this.mvp, this.v, modelo);
    multiply(this.mvp, this.p, this.mvp);
    gl.uniformMatrix4fv(this.u.mvp, false, this.mvp);
    gl.uniform1f(this.u.mode, modo);
    this.enlazar(malla);
    if (malla.ibo) gl.drawElements(gl.TRIANGLES, malla.cantidad, gl.UNSIGNED_SHORT, 0);
    else if (modo > 2.5) gl.drawArrays(gl.POINTS, 0, malla.cantidad);
    else gl.drawArrays(gl.TRIANGLES, 0, malla.cantidad);
  };

  Estudio.prototype.frame = function frame(ahora) {
    if (!this.ok) return;
    const gl = this.gl;
    const ancho = this.canvas.clientWidth;
    const alto = this.canvas.clientHeight;
    if (ancho < 2 || alto < 2) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.floor(ancho * dpr);
    const h = Math.floor(alto * dpr);
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.useProgram(this.prog);
    const t = ahora * 0.001;
    const aspecto = w / Math.max(h, 1);
    const ajuste = aspecto < 1 ? Math.min(1 / aspecto, 1.7) : 1;
    perspective(this.p, Math.PI / 4.2, aspecto, 0.1, 20);
    const alturaCam = this.hero ? 1.55 : 1.35;
    const lejos = (this.hero ? 3.35 : 3.55) * ajuste;
    lookAt(this.v, [0, alturaCam, lejos], [0, 0.05, 0], [0, 1, 0]);
    gl.uniform1f(this.u.time, reduce ? 0 : t);
    gl.uniform1f(this.u.bass, nivel.bass);
    gl.uniform1f(this.u.punto, this.hero ? 0.7 : 1.15);
    gl.uniform3fv(this.u.accent, vivo.accent);
    gl.uniform1f(this.u.hasTex, this.texturaLista);
    gl.uniform1f(this.u.estilo, vivo.disco.estilo);
    gl.uniform3fv(this.u.colA, vivo.disco.a);
    gl.uniform3fv(this.u.colB, vivo.disco.b);
    gl.uniform1i(this.u.tex, 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.textura);

    const giro = reduce ? 0.4 : vivo.spin;
    let modelo = multiply(this.tmp, rotateX(0.72), rotateY(giro));
    const escala = 1 + nivel.bass * 0.045;
    modelo = multiply(mat(), modelo, escalar(escala));
    this.dibujar(this.disco, modelo, 0);

    const apoyo = vivo.sonando ? 0.22 : 0.55;
    let brazo = multiply(mat(), rotateY(-0.15), rotateZ(apoyo));
    brazo = multiply(mat(), rotateX(0.72), brazo);
    this.dibujar(this.brazo, brazo, 1);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    this.dibujar(this.puntos, escalar(1.15), 3);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
  };

  function rotateZ(angulo) {
    const c = Math.cos(angulo);
    const s = Math.sin(angulo);
    const out = mat();
    out.set([c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
    return out;
  }

  // -----------------------------------------------------------------------
  // Arranque: el vinilo del costado. La vista grande vive en ahora.js.
  // -----------------------------------------------------------------------
  const heroCanvas = document.getElementById("kl-hero-canvas");
  const fallback = document.getElementById("kl-vinilo-css");
  let hero = null;
  let heroVisible = true;
  let ahoraAbierto = false;

  if (heroCanvas) {
    hero = new Estudio(heroCanvas, { hero: true });
    if (hero.ok) heroCanvas.dataset.gl = "1";
    else {
      heroCanvas.dataset.error = hero.error || "fallo";
      if (fallback) fallback.hidden = false;
    }
    if ("IntersectionObserver" in window) {
      const obs = new IntersectionObserver((entradas) => {
        heroVisible = entradas.some((e) => e.isIntersecting);
        encender();
      });
      obs.observe(heroCanvas);
    }
  }

  // Se suscribe al reloj común solo mientras el vinilo se ve. En reposo dibuja
  // uno de cada tres cuadros: gira despacio y no hace falta más.
  let cuadros = 0;
  function tick(dt, ahora) {
    if (!hero || !hero.ok || !heroVisible || ahoraAbierto) return false;
    // Más lento que 33⅓ (igual que el resto de los discos) y un empujón con los graves.
    if (!reduce) vivo.spin += (vivo.sonando ? 0.5 + nivel.bass * 0.4 : 0.08) * dt;
    cuadros += 1;
    if (!vivo.sonando && cuadros % 3) return true;
    if (vivo.portada) hero.cargarPortada(vivo.portada);
    hero.frame(ahora);
    return !reduce;
  }

  function encender() {
    if (hero && hero.ok && heroVisible && !ahoraAbierto && window.KL.reloj) window.KL.reloj.agregar("vinilo-lateral", tick);
  }

  function pintarStage() {
    const stageTitulo = document.getElementById("kl-stage-titulo");
    const stageArtista = document.getElementById("kl-stage-artista");
    if (stageTitulo) stageTitulo.textContent = vivo.titulo;
    if (stageArtista) stageArtista.textContent = vivo.artista;
    document.querySelectorAll(".kl-stage [data-estudio-play]").forEach((boton) => {
      boton.replaceChildren();
      const icono = document.createElement("i");
      icono.className = vivo.sonando ? "bi bi-pause-fill" : "bi bi-play-fill";
      icono.setAttribute("aria-hidden", "true");
      boton.append(icono, vivo.sonando ? " Pausa" : " Play");
    });
    document.body.classList.toggle("kl-en-vivo", vivo.sonando);
  }

  document.addEventListener("kl:reproductor", (evento) => {
    const detalle = evento.detail || {};
    vivo.sonando = !!detalle.sonando;
    if (detalle.pista) {
      vivo.titulo = detalle.pista.titulo || vivo.titulo;
      vivo.artista = detalle.pista.artista || vivo.artista;
      vivo.portada = detalle.pista.portada || "";
      vivo.accent = acentoDe(detalle.pista.titulo);
      vivo.disco.estilo = KLDisco.diseno(detalle.pista).estilo;
    }
    pintarStage();
    if (reduce && hero && hero.ok) hero.frame(performance.now());
    encender();
  });

  // Los colores del disco salen de la portada (los calcula ambiente.js).
  document.addEventListener("kl:paleta", (evento) => {
    const colores = evento.detail || [];
    const brillante = (c) => c.map((v) => Math.min(1, v * 1.35 + 0.04));
    if (colores[0]) vivo.disco.a = brillante(colores[0]);
    if (colores[1]) vivo.disco.b = brillante(colores[1]);
    if (reduce && hero && hero.ok) hero.frame(performance.now());
    encender();
  });

  document.addEventListener("kl:ahora", (evento) => {
    ahoraAbierto = !!(evento.detail && evento.detail.abierto);
    encender();
  });

  encender();
})();

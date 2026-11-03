/* ===========================================================================
 * Keep Listening - fondo vivo
 * Mientras suena un tema, detrás de toda la app corre un degradado armado con
 * los colores de la portada. Respira con la música sin sacudirse: el audio se
 * suaviza acá antes de usarlo, los medios aceleran el movimiento de a poco y
 * los golpes fuertes largan una onda suave desde el centro (un clic en el
 * fondo, desde donde se tocó). Sin WebGL queda un degradado en CSS.
 * =========================================================================== */
(function () {
  "use strict";

  const reduce = window.KL.util.reduce;
  const raiz = document.documentElement;
  const canvas = document.getElementById("kl-ambiente");
  let ultimoAmbiente = "";
  if (!canvas) return;

  const BASE = [
    [0.36, 0.52, 0.12],
    [0.08, 0.3, 0.22],
    [0.55, 0.38, 0.12],
    [0.05, 0.07, 0.06],
  ];

  const vivo = {
    sonando: false,
    abierto: false,
    intensidad: 0,
    raton: [0.5, 0.5],
    ratonObjetivo: [0.5, 0.5],
    ondas: [],
    colores: BASE.map((c) => c.slice()),
    objetivo: BASE.map((c) => c.slice()),
    portada: "",
  };

  // -----------------------------------------------------------------------
  // Paleta desde la portada
  // -----------------------------------------------------------------------
  const muestra = document.createElement("canvas");
  muestra.width = 28;
  muestra.height = 28;
  const ctxMuestra = muestra.getContext("2d", { willReadFrequently: true });

  function hsl(r, g, b) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    const d = max - min;
    const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
    return { s, l };
  }

  function distancia(a, b) {
    return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  }

  // Cuantiza en cubos de 4 bits, puntúa por cantidad y saturación y se queda
  // con cuatro colores que no se parezcan entre sí.
  function extraer(img) {
    ctxMuestra.clearRect(0, 0, 28, 28);
    ctxMuestra.drawImage(img, 0, 0, 28, 28);
    const datos = ctxMuestra.getImageData(0, 0, 28, 28).data;
    const cubos = new Map();
    for (let i = 0; i < datos.length; i += 4) {
      if (datos[i + 3] < 200) continue;
      const clave = ((datos[i] >> 4) << 8) | ((datos[i + 1] >> 4) << 4) | (datos[i + 2] >> 4);
      const cubo = cubos.get(clave) || { n: 0, r: 0, g: 0, b: 0 };
      cubo.n += 1;
      cubo.r += datos[i];
      cubo.g += datos[i + 1];
      cubo.b += datos[i + 2];
      cubos.set(clave, cubo);
    }
    const candidatos = [];
    cubos.forEach((cubo) => {
      const color = [cubo.r / cubo.n / 255, cubo.g / cubo.n / 255, cubo.b / cubo.n / 255];
      const tono = hsl(color[0], color[1], color[2]);
      // Los casi negros y casi blancos cuentan poco: la paleta la ponen los colores con carácter.
      const luz = tono.l < 0.1 ? 0.06 : tono.l < 0.18 ? 0.35 : tono.l > 0.92 ? 0.3 : 1;
      candidatos.push({ color, puntaje: cubo.n * (0.12 + Math.pow(tono.s, 1.3) * 2.2) * luz });
    });
    candidatos.sort((a, b) => b.puntaje - a.puntaje);
    const elegidos = [];
    for (const candidato of candidatos) {
      if (elegidos.every((c) => distancia(c, candidato.color) > 0.22)) elegidos.push(candidato.color);
      if (elegidos.length === 4) break;
    }
    while (elegidos.length < 4) {
      const previo = elegidos[elegidos.length - 1] || BASE[0];
      elegidos.push(previo.map((v) => v * 0.55));
    }
    // El fondo no puede encandilar: se baja la luz y se deja el último casi negro.
    return elegidos.map((color, indice) => {
      const techo = indice === 3 ? 0.16 : 0.72;
      const maximo = Math.max(color[0], color[1], color[2], 0.001);
      const factor = maximo > techo ? techo / maximo : 1;
      return color.map((v) => v * factor);
    });
  }

  function paletaDeTexto(texto) {
    let hash = 0;
    for (let i = 0; i < texto.length; i += 1) hash = (hash * 31 + texto.charCodeAt(i)) >>> 0;
    const giro = (hash % 360) / 360;
    return [0, 0.18, 0.5, 0.72].map((paso, indice) => {
      const h = (giro + paso) % 1;
      const l = indice === 3 ? 0.06 : 0.34;
      const a = 0.6 * Math.min(l, 1 - l);
      const f = (n) => {
        const k = (n + h * 12) % 12;
        return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
      };
      return [f(0), f(8), f(4)];
    });
  }

  // Para botones y brillos: mismo tono, pero con luz y saturación mínimas.
  function acento(color) {
    const [r, g, b] = color;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    if (max !== min) {
      const d = max - min;
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else h = ((r - g) / d + 4) / 6;
    }
    const tono = hsl(r, g, b);
    const s = tono.s < 0.12 ? 0.1 : Math.max(tono.s, 0.55);
    const l = Math.min(0.78, Math.max(tono.l, 0.64));
    const a = s * Math.min(l, 1 - l);
    const f = (n) => {
      const k = (n + h * 12) % 12;
      return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    };
    return [f(0), f(8), f(4)];
  }

  function aplicarPaleta(colores) {
    vivo.objetivo = colores;
    // Los componentes del "Ahora suena" se tiñen con estos tres colores.
    colores.slice(0, 3).forEach((color, indice) => {
      const rgb = acento(color).map((v) => Math.round(v * 255)).join(", ");
      raiz.style.setProperty(`--kl-c${indice + 1}`, rgb);
    });
    document.dispatchEvent(new CustomEvent("kl:paleta", { detail: colores }));
  }

  function cargarPaleta(url, titulo) {
    if (!url || url === vivo.portada) return;
    vivo.portada = url;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => {
      if (vivo.portada !== url) return;
      try {
        aplicarPaleta(extraer(img));
      } catch (error) {
        // La imagen no vino con permiso de lectura: se inventa una paleta estable.
        aplicarPaleta(paletaDeTexto(titulo || url));
      }
    };
    img.onerror = () => {
      if (vivo.portada === url) aplicarPaleta(paletaDeTexto(titulo || url));
    };
    img.src = url;
  }

  // -----------------------------------------------------------------------
  // WebGL
  // -----------------------------------------------------------------------
  const VERT = `
    attribute vec2 aPos;
    varying vec2 vUv;
    void main() {
      vUv = aPos * 0.5 + 0.5;
      gl_Position = vec4(aPos, 0.0, 1.0);
    }
  `;

  const FRAG = `
    precision mediump float;
    varying vec2 vUv;
    uniform vec2 uRes;
    uniform float uTime;
    uniform float uFase;
    uniform float uBass;
    uniform float uHigh;
    uniform float uFuerza;
    uniform vec2 uRaton;
    uniform vec3 uC0;
    uniform vec3 uC1;
    uniform vec3 uC2;
    uniform vec3 uC3;
    uniform vec4 uOndas[4];

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    float ruido(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
                 mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
    }

    float mancha(vec2 p, vec2 centro, float radio) {
      vec2 d = p - centro;
      return exp(-dot(d, d) / (radio * radio));
    }

    void main() {
      float aspecto = uRes.x / max(uRes.y, 1.0);
      vec2 p = vUv;
      p.x *= aspecto;
      vec2 raton = vec2(uRaton.x * aspecto, uRaton.y);
      // La fase se acumula en JS: cambiar la velocidad no hace saltar el dibujo.
      float t = uFase;

      // Las ondas empujan el espacio hacia afuera desde donde nacieron.
      vec2 empuje = vec2(0.0);
      float anillos = 0.0;
      for (int i = 0; i < 4; i++) {
        vec4 onda = uOndas[i];
        if (onda.w <= 0.0) continue;
        vec2 centro = vec2(onda.x * aspecto, onda.y);
        vec2 d = p - centro;
        float r = length(d);
        float frente = onda.z * 0.9;
        float banda = exp(-pow((r - frente) * 9.0, 2.0)) * onda.w;
        empuje += normalize(d + 0.0001) * banda * 0.045;
        anillos += banda;
      }
      p -= empuje;

      // Deformación de dominio: el degradado se mueve como tinta en agua.
      vec2 q = vec2(ruido(p * 1.6 + t), ruido(p * 1.6 - t + 4.1));
      vec2 w = p + (q - 0.5) * (0.55 + uBass * 0.15);

      vec2 a = vec2(0.25 * aspecto + sin(t * 1.3) * 0.18, 0.72 + cos(t * 0.9) * 0.14);
      vec2 b = vec2(0.78 * aspecto + cos(t * 1.1) * 0.2, 0.3 + sin(t * 1.4) * 0.16);
      vec2 c = vec2(0.55 * aspecto + sin(t * 0.7 + 2.0) * 0.26, 0.55 + sin(t * 1.2 + 1.0) * 0.2);

      float crecer = 1.0 + uBass * 0.16;
      float ma = mancha(w, a, 0.42 * crecer);
      float mb = mancha(w, b, 0.46 * crecer);
      float mc = mancha(w, c, 0.34 * crecer);
      float mr = mancha(p, raton, 0.26 + uBass * 0.04) * 0.85;

      vec3 col = uC3;
      col = mix(col, uC1, clamp(mb, 0.0, 1.0));
      col = mix(col, uC0, clamp(ma, 0.0, 1.0));
      col = mix(col, uC2, clamp(mc * 0.9, 0.0, 1.0));
      col += uC0 * mr * 0.55 + vec3(0.04) * mr;
      col += (uC0 + uC2) * 0.5 * anillos * 0.3;
      col *= 0.98 + uBass * 0.16;

      // Viñeta y grano: el grano sube con los agudos.
      vec2 centro = vUv - 0.5;
      col *= 1.0 - dot(centro, centro) * 1.1;
      col += (hash(vUv * uRes + uTime) - 0.5) * (0.022 + uHigh * 0.012);

      gl_FragColor = vec4(col * uFuerza, uFuerza);
    }
  `;

  function compilar(gl, tipo, fuente) {
    const shader = gl.createShader(tipo);
    gl.shaderSource(shader, fuente);
    gl.compileShader(shader);
    return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
  }

  const gl = canvas.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: true });
  let u = null;
  if (gl) {
    const vs = compilar(gl, gl.VERTEX_SHADER, VERT);
    const fs = compilar(gl, gl.FRAGMENT_SHADER, FRAG);
    if (vs && fs) {
      const prog = gl.createProgram();
      gl.attachShader(prog, vs);
      gl.attachShader(prog, fs);
      gl.bindAttribLocation(prog, 0, "aPos");
      gl.linkProgram(prog);
      if (gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        gl.useProgram(prog);
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
        gl.enableVertexAttribArray(0);
        gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
        const nombres = ["uRes", "uTime", "uFase", "uBass", "uHigh", "uFuerza", "uRaton", "uC0", "uC1", "uC2", "uC3", "uOndas"];
        u = {};
        nombres.forEach((nombre) => { u[nombre] = gl.getUniformLocation(prog, nombre); });
      }
    }
  }
  if (!u) canvas.dataset.fallback = "1";

  const ondasPlanas = new Float32Array(16);
  const VIDA_ONDA = 1.6;
  // Entre dos ondas del ritmo pasa al menos esto: un golpe por compás, no por cada bombo.
  const PAUSA_ONDA_RITMO = 1.2;

  function lanzarOnda(x, y, fuerza) {
    vivo.ondas.push({ x, y, edad: 0, fuerza });
    if (vivo.ondas.length > 4) vivo.ondas.shift();
  }

  // Graves, medios, agudos y golpes: los mide el núcleo (KL.nivel) una vez por cuadro.
  // Acá se suavizan otra vez y con el tiempo real del cuadro, así el fondo no
  // tiembla con cada pico ni depende de los cuadros por segundo de la pantalla.
  const nivel = window.KL.nivel;
  const suave = { bass: 0, mid: 0, high: 0 };
  const seguir = (actual, meta, dt, rapidez) => actual + (meta - actual) * (1 - Math.exp(-dt * rapidez));
  let fase = 0;
  let desdeOnda = PAUSA_ONDA_RITMO;

  // Se mide solo cuando cambia la ventana, no en cada cuadro.
  let medir = true;
  window.addEventListener("resize", () => { medir = true; }, { passive: true });

  function tamano() {
    if (!medir) return;
    medir = false;
    // A media resolución: el degradado es suave y el GPU lo agradece.
    const escala = window.innerWidth > 1400 ? 0.4 : 0.5;
    const w = Math.max(2, Math.floor(window.innerWidth * escala));
    const h = Math.max(2, Math.floor(window.innerHeight * escala));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
    gl.uniform2f(u.uRes, w, h);
  }

  let apagado = true;
  let cuadros = 0;

  // Suscripto al reloj común. Devuelve false cuando ya no hay nada que mostrar.
  function marco(dt, ahora) {
    const meta = vivo.sonando ? 1 : vivo.abierto ? 0.75 : 0;
    vivo.intensidad = seguir(vivo.intensidad, meta, dt, 2.2);

    const sonando = vivo.sonando && !reduce;
    suave.bass = seguir(suave.bass, sonando ? nivel.bass : 0, dt, 3);
    suave.mid = seguir(suave.mid, sonando ? nivel.mid : 0, dt, 1.5);
    suave.high = seguir(suave.high, sonando ? nivel.high : 0, dt, 3);
    // Los medios aceleran el movimiento apenas, y siempre de forma continua.
    fase += dt * (0.05 + suave.mid * 0.035);

    desdeOnda += dt;
    if (nivel.golpe && sonando && desdeOnda >= PAUSA_ONDA_RITMO) {
      desdeOnda = 0;
      lanzarOnda(0.5, 0.5, 0.22 + suave.bass * 0.2);
    }

    vivo.raton[0] = seguir(vivo.raton[0], vivo.ratonObjetivo[0], dt, 3);
    vivo.raton[1] = seguir(vivo.raton[1], vivo.ratonObjetivo[1], dt, 3);
    vivo.colores.forEach((color, i) => {
      for (let k = 0; k < 3; k += 1) color[k] = seguir(color[k], vivo.objetivo[i][k], dt, 1.6);
    });
    // Envejecen y se descartan sin crear un arreglo nuevo en cada cuadro.
    for (let i = vivo.ondas.length - 1; i >= 0; i -= 1) {
      vivo.ondas[i].edad += dt;
      if (vivo.ondas[i].edad >= VIDA_ONDA) vivo.ondas.splice(i, 1);
    }

    const quieto = meta === 0 && vivo.intensidad < 0.005;
    // Solo si cambió: cada escritura en :root invalida los estilos de toda la página.
    const ambiente = quieto ? "0" : vivo.intensidad.toFixed(2);
    if (ambiente !== ultimoAmbiente) {
      ultimoAmbiente = ambiente;
      raiz.style.setProperty("--kl-ambiente", ambiente);
    }

    // Con movimiento reducido alcanza con unos pocos cuadros por segundo.
    cuadros += 1;
    if (u && !(reduce && cuadros % 15)) {
      tamano();
      gl.uniform1f(u.uTime, reduce ? 12 : (ahora / 1000) % 1000);
      gl.uniform1f(u.uFase, reduce ? 0.6 : fase);
      gl.uniform1f(u.uBass, suave.bass);
      gl.uniform1f(u.uHigh, suave.high);
      gl.uniform1f(u.uFuerza, vivo.intensidad);
      gl.uniform2f(u.uRaton, vivo.raton[0], 1 - vivo.raton[1]);
      gl.uniform3fv(u.uC0, vivo.colores[0]);
      gl.uniform3fv(u.uC1, vivo.colores[1]);
      gl.uniform3fv(u.uC2, vivo.colores[2]);
      gl.uniform3fv(u.uC3, vivo.colores[3]);
      ondasPlanas.fill(0);
      vivo.ondas.forEach((onda, i) => {
        ondasPlanas[i * 4] = onda.x;
        ondasPlanas[i * 4 + 1] = 1 - onda.y;
        ondasPlanas[i * 4 + 2] = onda.edad;
        ondasPlanas[i * 4 + 3] = onda.fuerza * (1 - onda.edad / VIDA_ONDA);
      });
      gl.uniform4fv(u.uOndas, ondasPlanas);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    if (quieto) {
      if (u) gl.clear(gl.COLOR_BUFFER_BIT);
      apagado = true;
      return false;
    }
    return true;
  }

  function arrancar() {
    if (!apagado && window.KL.reloj.tiene("fondo-vivo")) return;
    apagado = false;
    window.KL.reloj.agregar("fondo-vivo", marco);
  }

  // -----------------------------------------------------------------------
  // Eventos
  // -----------------------------------------------------------------------
  document.addEventListener("kl:reproductor", (evento) => {
    const detalle = evento.detail || {};
    vivo.sonando = !!detalle.sonando;
    document.body.classList.toggle("kl-ambiente-vivo", vivo.sonando);
    if (detalle.pista) cargarPaleta(detalle.pista.portada, detalle.pista.titulo);
    arrancar();
  });

  document.addEventListener("kl:ahora", (evento) => {
    vivo.abierto = !!(evento.detail && evento.detail.abierto);
    arrancar();
  });

  window.addEventListener("pointermove", (evento) => {
    vivo.ratonObjetivo[0] = evento.clientX / window.innerWidth;
    vivo.ratonObjetivo[1] = evento.clientY / window.innerHeight;
  }, { passive: true });

  // Un clic en una zona vacía (no en un botón ni en un link) hace una onda.
  window.addEventListener("pointerdown", (evento) => {
    if (vivo.intensidad < 0.1) return;
    if (evento.target.closest("button, a, input, select, textarea, label, [role=button], .kl-flota")) return;
    lanzarOnda(evento.clientX / window.innerWidth, evento.clientY / window.innerHeight, 1);
  }, { passive: true });

  window.KLAmbiente = {
    onda: lanzarOnda,
  };
})();

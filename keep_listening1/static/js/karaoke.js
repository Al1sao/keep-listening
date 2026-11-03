/* ===========================================================================
 * Keep Listening - letra en vivo: el túnel del surco
 *
 * La letra no es una lista que se desplaza: es un espacio. Los versos que
 * vienen esperan al fondo, en perspectiva, con el punto de fuga en el disco
 * (la letra "sale" del vinilo). El que suena llega al frente, grande como un
 * afiche, y se llena palabra por palabra; el que pasó vuela hacia la cámara y
 * se desvanece. Detrás, una palabra fantasma gigante y los surcos del disco
 * que se abren desde el punto de fuga.
 *
 * Interacción: el puntero inclina el túnel; la rueda o el dedo viajan por la
 * letra (y vuelve sola); ↑ / ↓ saltan de verso; tocar un verso o una marca del
 * mapa lleva el audio ahí. Los estribillos se ven en el mapa.
 *
 * Los adelantos de Apple son 30 segundos de algún punto del tema y no dicen
 * de dónde. Para los temas de la selección ese punto ya se midió con Whisper
 * (manage.py calcular_desfases) y viaja como `pista.desfase`. Para el resto
 * no hay forma confiable de saberlo: la letra se muestra completa, como una
 * página, antes que marcar versos que no son.
 * =========================================================================== */
(function () {
  "use strict";

  const reduce = window.KL.util.reduce;

  const INTERLUDIO = 5.5; // segundos sin canto a partir de los cuales aparecen los puntos
  // El túnel, en píxeles de profundidad.
  const PASO_Z = 380;    // distancia entre un verso y el siguiente
  const SALIDA_Z = 560;  // cuánto avanza hacia la cámara un verso que ya pasó
  const ADELANTE = 7;    // versos que se ven hacia el fondo
  const ATRAS = 1.6;     // hasta dónde se sigue viendo uno que pasó
  const ANCLA = 0.42;    // altura del verso que suena (igual que el top del CSS)
  const HUECO = 0.45;    // aire entre versos de la pila (en alturas de renglón)

  function partirPalabras(texto) {
    return texto.split(/(\s+)/).filter((p) => p.length);
  }

  // -----------------------------------------------------------------------
  // Cada verso tiene su entrada. Referencias: el relleno sílaba por sílaba de
  // Apple Music Sing y la tipografía cinética de los lyric videos. Además, las
  // palabras "con imagen" (fuego, amor, cielo, lluvia, plata) sueltan partículas.
  // -----------------------------------------------------------------------
  const MOTIVOS = [
    { nombre: "fuego", re: /^(fire|fuego|burn\w*|flame\w*|lit|heat|hot|quema\w*|arde\w*|smoke\w*)$/i },
    { nombre: "corazon", re: /^(love\w*|lov\w*|heart\w*|amor|coraz[oó]n|kiss\w*|beso\w*|baby|babe|darlin)$/i },
    { nombre: "estrella", re: /^(stars?|starships?|sky|skies|fly|flyin|flying|high|moon|cielo|estrellas?|luna|shine|shinin|lights?|heaven)$/i },
    { nombre: "gota", re: /^(rain\w*|cry\w*|tears?|lluvia|llor\w*|l[aá]grimas?|water|ocean|sea|drown\w*|wet)$/i },
    { nombre: "dinero", re: /^(money|cash|bands|dollars?|rich|bank|racks|plata|dinero|gold|diamonds?|bag|paid)$/i },
  ];
  const ENTRADAS = ["sube", "tinta", "ola", "desliza"];

  function limpiar(palabra) {
    return palabra.replace(/[^\p{L}\p{N}]/gu, "");
  }

  function motivoDe(palabra) {
    const limpia = limpiar(palabra);
    const motivo = MOTIVOS.find((m) => m.re.test(limpia));
    return motivo ? motivo.nombre : "";
  }

  function entradaDe(texto, indice, repetida) {
    const palabras = texto.split(/\s+/).filter(Boolean);
    const gritada = /[A-Z]/.test(texto) && texto === texto.toUpperCase();
    if (/!/.test(texto) || gritada || (palabras.length <= 3 && texto.length <= 20)) return "impacto";
    if (repetida) return "eco";
    return ENTRADAS[indice % ENTRADAS.length];
  }

  // La palabra más larga del verso: la que queda gigante detrás.
  function fantasmaDe(texto) {
    const palabras = texto.split(/\s+/).map(limpiar).filter((p) => p.length >= 3);
    palabras.sort((a, b) => b.length - a.length);
    return (palabras[0] || "").toUpperCase();
  }

  function claveDe(texto) {
    return texto.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }

  // Partículas sobre la letra: un canvas liviano, que solo corre mientras se ve.
  class Chispas {
    constructor(raiz) {
      this.raiz = raiz;
      this.canvas = document.createElement("canvas");
      this.canvas.className = "kl-karaoke__chispas";
      this.canvas.setAttribute("aria-hidden", "true");
      this.ctx = this.canvas.getContext("2d");
      this.lista = [];
    }

    montar() {
      if (!this.canvas.isConnected) this.raiz.appendChild(this.canvas);
    }

    // Colores del tema con la caché del núcleo (se lee una vez por paleta, no por chispa).
    colores() {
      return [window.KL.util.rgb("--kl-c1"), window.KL.util.rgb("--kl-c2"), "255, 255, 255"];
    }

    soltar(x, y, ancho, motivo, cantidad, fuerza = 1) {
      if (reduce) return;
      const colores = this.colores();
      const paleta = {
        fuego: ["255, 138, 48", "255, 206, 84", "255, 84, 48"],
        corazon: ["255, 92, 138", "255, 160, 190", colores[0]],
        dinero: ["120, 230, 120", "255, 214, 90", colores[0]],
        gota: ["140, 200, 255", "200, 230, 255", colores[1]],
      }[motivo] || colores;
      for (let i = 0; i < cantidad; i += 1) {
        const angulo = motivo === "gota" ? Math.PI / 2 : -Math.PI / 2 + (Math.random() - 0.5) * 2.2;
        const velocidad = (motivo === "gota" ? 40 : 60 + Math.random() * 140) * fuerza;
        this.lista.push({
          x: x + Math.random() * ancho,
          y: y + (Math.random() - 0.5) * 10,
          vx: Math.cos(angulo) * velocidad * (motivo === "gota" ? 0.1 : 1),
          vy: Math.sin(angulo) * velocidad,
          vida: 0,
          max: 0.9 + Math.random() * 0.9,
          tam: (motivo ? 7 : 2.2) + Math.random() * (motivo ? 6 : 2.5),
          giro: Math.random() * Math.PI,
          color: paleta[i % paleta.length],
          tipo: motivo || "punto",
        });
      }
      if (this.lista.length > 220) this.lista.splice(0, this.lista.length - 220);
    }

    forma(p) {
      const c = this.ctx;
      const t = p.tam;
      c.beginPath();
      if (p.tipo === "corazon") {
        c.moveTo(0, t * 0.3);
        c.bezierCurveTo(-t, -t * 0.4, -t * 0.4, -t, 0, -t * 0.35);
        c.bezierCurveTo(t * 0.4, -t, t, -t * 0.4, 0, t * 0.3);
        c.fill();
      } else if (p.tipo === "estrella") {
        for (let i = 0; i < 8; i += 1) {
          const r = i % 2 ? t * 0.28 : t;
          const a = (i / 8) * Math.PI * 2;
          c.lineTo(Math.cos(a) * r, Math.sin(a) * r);
        }
        c.closePath();
        c.fill();
      } else if (p.tipo === "gota") {
        c.moveTo(0, -t);
        c.quadraticCurveTo(t * 0.7, 0, 0, t * 0.6);
        c.quadraticCurveTo(-t * 0.7, 0, 0, -t);
        c.fill();
      } else if (p.tipo === "dinero") {
        c.font = `800 ${Math.round(t * 1.8)}px Syne, sans-serif`;
        c.textAlign = "center";
        c.textBaseline = "middle";
        c.fillText("$", 0, 0);
      } else {
        c.arc(0, 0, p.tipo === "fuego" ? t * 0.45 : t, 0, Math.PI * 2);
        c.fill();
      }
    }

    cuadro(dt) {
      const ancho = this.raiz.clientWidth;
      const alto = this.raiz.clientHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (this.canvas.width !== Math.round(ancho * dpr) || this.canvas.height !== Math.round(alto * dpr)) {
        this.canvas.width = Math.round(ancho * dpr);
        this.canvas.height = Math.round(alto * dpr);
      }
      const c = this.ctx;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, ancho, alto);
      if (!this.lista.length) return;
      c.globalCompositeOperation = "lighter";
      this.lista = this.lista.filter((p) => {
        p.vida += dt;
        if (p.vida >= p.max) return false;
        const gravedad = p.tipo === "gota" ? 260 : p.tipo === "fuego" ? -40 : 60;
        p.vy += gravedad * dt;
        p.vx *= 0.985;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.giro += dt * 2;
        const resto = 1 - p.vida / p.max;
        c.save();
        c.translate(p.x, p.y);
        c.rotate(p.tipo === "estrella" ? p.giro : 0);
        c.globalAlpha = Math.min(1, resto * 1.6);
        c.fillStyle = `rgb(${p.color})`;
        if (p.tipo === "fuego") {
          c.shadowBlur = 12;
          c.shadowColor = `rgb(${p.color})`;
        }
        this.forma(p);
        c.restore();
        return true;
      });
      c.globalCompositeOperation = "source-over";
      c.globalAlpha = 1;
    }
  }

  function crear(etiqueta, clase, padre) {
    const nodo = document.createElement(etiqueta);
    nodo.className = clase;
    if (padre) padre.appendChild(nodo);
    return nodo;
  }

  class KLKaraoke {
    constructor(contenedor, opciones = {}) {
      this.raiz = contenedor;
      this.alTocar = opciones.alTocar || null;
      this.alCambiar = opciones.alCambiar || null;
      this.alAvanzar = opciones.alAvanzar || null;
      // Devuelve el rectángulo de donde "sale" la letra (el disco). Opcional.
      this.origen = opciones.origen || null;
      this.audio = opciones.audio || document.getElementById("kl-audio");
      this.versos = [];
      this.lineas = [];
      this.sincroniza = false;
      this.desfase = 0;
      this.activa = -2;
      this.visible = false;
      // Cámara del túnel: posición (en versos) y hacia dónde va.
      this.camara = -0.6;
      this.objetivo = -0.6;
      this.manual = 0;
      this.manualHasta = 0;
      this.puntero = { x: 0, y: 0, ox: 0, oy: 0 };
      this.fuga = { x: 0.5, y: 0.3, medido: 0 };

      this.raiz.classList.add("kl-karaoke");
      this.fondo = crear("div", "kl-karaoke__fondo");
      this.fondo.setAttribute("aria-hidden", "true");
      this.fantasma = crear("span", "kl-karaoke__fantasma", this.fondo);
      this.pista = crear("div", "kl-karaoke__pista");
      this.mapa = crear("div", "kl-karaoke__mapa");
      this.mapa.setAttribute("aria-hidden", "true");
      this.raiz.replaceChildren(this.fondo, this.pista, this.mapa);
      this.chispas = new Chispas(this.raiz);

      if ("ResizeObserver" in window) {
        new ResizeObserver(() => {
          this.fuga.medido = 0;
          this.pilaMedida = false;
          this.pintar(0, true);
        }).observe(this.raiz);
      }

      // Rueda o dedo: se viaja por la letra un rato y la cámara vuelve sola.
      this.raiz.addEventListener("wheel", (evento) => {
        if (!this.sincroniza) return;
        evento.preventDefault();
        this.viajar(evento.deltaY / 160);
      }, { passive: false });
      let toque = null;
      this.raiz.addEventListener("touchstart", (e) => { toque = e.touches[0].clientY; }, { passive: true });
      this.raiz.addEventListener("touchmove", (e) => {
        if (!this.sincroniza || toque === null) return;
        const y = e.touches[0].clientY;
        this.viajar((toque - y) / 90);
        toque = y;
      }, { passive: true });
      this.raiz.addEventListener("touchend", () => { toque = null; }, { passive: true });

      // El puntero inclina el túnel (parallax del punto de fuga).
      this.raiz.addEventListener("pointermove", (evento) => {
        if (evento.pointerType === "touch") return;
        const r = this.raiz.getBoundingClientRect();
        this.puntero.ox = (evento.clientX - r.left) / r.width - 0.5;
        this.puntero.oy = (evento.clientY - r.top) / r.height - 0.5;
      });
      this.raiz.addEventListener("pointerleave", () => { this.puntero.ox = 0; this.puntero.oy = 0; });

      this.raiz.addEventListener("keydown", (evento) => {
        if (!this.sincroniza) return;
        if (evento.key === "ArrowDown") { evento.preventDefault(); this.saltar(1); }
        if (evento.key === "ArrowUp") { evento.preventDefault(); this.saltar(-1); }
      });

      this.mapa.addEventListener("click", (evento) => {
        const marca = evento.target.closest("[data-i]");
        if (marca) this.irA(Number(marca.dataset.i));
      });
    }

    viajar(versos) {
      const n = this.lineas.length;
      if (!n) return;
      const base = Math.max(0, this.activa);
      this.manual = Math.max(-base - 1.1, Math.min(n - 1 - base, this.manual + versos));
      this.manualHasta = performance.now() + 3200;
      this.raiz.classList.add("viajando");
    }

    irA(indice) {
      const linea = this.lineas[indice];
      if (!linea || !this.alTocar) return;
      this.manual = 0;
      this.manualHasta = 0;
      this.alTocar(linea.t - this.desfase);
    }

    saltar(delta) {
      const n = this.lineas.length;
      if (!n) return;
      this.irA(Math.max(0, Math.min(n - 1, Math.max(0, this.activa) + delta)));
    }

    limpiarVista() {
      this.lineas = [];
      this.mapa.replaceChildren();
      this.fantasma.textContent = "";
      this.pista.style.transform = "";
    }

    aviso(mensaje) {
      this.versos = [];
      this.sincroniza = false;
      this.raiz.classList.remove("sincroniza", "tunel");
      this.raiz.classList.add("libre");
      this.limpiarVista();
      const p = crear("p", "kl-karaoke__aviso");
      p.textContent = mensaje;
      this.pista.replaceChildren(p);
    }

    mostrar(versos, { sincroniza, desfase = 0, nota = "" } = {}) {
      // Las marcas de instrumental de LRCLIB ("♪") no son versos.
      versos = versos.filter((verso) => /[\p{L}\p{N}]/u.test(verso.texto));
      this.versos = versos;
      this.sincroniza = !!sincroniza;
      this.desfase = desfase;
      this.activa = -2;
      this.manual = 0;
      this.camara = -1.1;
      this.objetivo = -1.1;
      this.raiz.classList.toggle("sincroniza", this.sincroniza);
      this.raiz.classList.toggle("tunel", this.sincroniza);
      this.raiz.classList.toggle("libre", !this.sincroniza);
      this.raiz.tabIndex = this.sincroniza ? 0 : -1;
      this.raiz.scrollTop = 0;
      this.limpiarVista();

      const nodos = [];
      if (nota) {
        const aviso = crear("p", "kl-karaoke__nota");
        aviso.textContent = nota;
        nodos.push(aviso);
      }
      // Un verso que ya apareció es estribillo: vuelve con eco y se marca en el mapa.
      const vistas = new Map();
      versos.forEach((verso) => {
        const clave = claveDe(verso.texto);
        vistas.set(clave, (vistas.get(clave) || 0) + 1);
      });
      const yaVistas = new Set();
      const marcas = [];

      this.lineas = versos.map((verso, indice) => {
        const p = crear("p", "kl-karaoke__linea");
        p.style.setProperty("--i", String(indice));
        p.style.setProperty("--largo", String(Math.min(verso.texto.length, 64)));
        const clave = claveDe(verso.texto);
        const repetida = yaVistas.has(clave);
        yaVistas.add(clave);
        const estribillo = vistas.get(clave) > 1;
        if (estribillo) p.classList.add("estribillo");
        // En la página, cada estrofa se separa de la anterior: por la línea en
        // blanco de la letra o, si vino con tiempos, por una pausa larga.
        const anterior = versos[indice - 1];
        if (!this.sincroniza && anterior && (verso.estrofa || verso.t - anterior.t > INTERLUDIO)) {
          p.classList.add("estrofa");
        }
        p.dataset.entrada = entradaDe(verso.texto, indice, repetida);
        const texto = crear("span", "kl-karaoke__texto", p);
        let motivoLinea = "";
        const palabras = [];
        partirPalabras(verso.texto).forEach((trozo) => {
          if (/^\s+$/.test(trozo)) {
            texto.appendChild(document.createTextNode(trozo));
            return;
          }
          const span = crear("span", "kl-karaoke__palabra", texto);
          span.textContent = trozo;
          span.style.setProperty("--k", String(palabras.length));
          const motivo = motivoDe(trozo);
          if (motivo) {
            span.classList.add("clave");
            span.dataset.motivo = motivo;
            motivoLinea = motivoLinea || motivo;
          }
          palabras.push({ nodo: span, peso: trozo.length + 2, motivo });
        });
        if (motivoLinea) p.dataset.motivo = motivoLinea;
        if (this.sincroniza) {
          p.addEventListener("click", () => this.irA(indice));
          const marca = crear("i", `kl-karaoke__marca${estribillo ? " estribillo" : ""}`);
          marca.dataset.i = String(indice);
          marca.title = verso.texto;
          marca.style.setProperty("--largo", String(Math.min(verso.texto.length, 48)));
          marcas.push(marca);
        }
        nodos.push(p);
        const siguiente = versos[indice + 1] ? versos[indice + 1].t : verso.t + 5;
        const hueco = siguiente - verso.t;
        // Duración estimada del canto: no más que el hueco ni que lo que tarda decirlo.
        const dura = Math.max(0.6, Math.min(hueco * 0.92, 0.7 + verso.texto.length * 0.075));
        const total = palabras.reduce((s, w) => s + w.peso, 0) || 1;
        let acumulado = 0;
        palabras.forEach((w) => {
          w.inicio = verso.t + (acumulado / total) * dura;
          acumulado += w.peso;
          w.fin = verso.t + (acumulado / total) * dura;
        });
        // "Semilla" del recorrido: cada verso se corre y gira un poco distinto.
        const semilla = Math.sin(indice * 1.7 + 0.4);
        return {
          nodo: p, palabras, t: verso.t, fin: verso.t + dura, hueco, texto: verso.texto,
          fantasma: fantasmaDe(verso.texto), semilla, marca: marcas[marcas.length - 1] || null,
          estado: {},
        };
      });

      this.puntos = crear("div", "kl-karaoke__puntos");
      this.puntos.setAttribute("aria-hidden", "true");
      for (let i = 0; i < 3; i += 1) crear("span", "", this.puntos);
      this.pista.replaceChildren(...nodos, this.puntos);
      this.mapa.replaceChildren(...marcas);
      if (this.sincroniza) this.chispas.montar();
      this.fuga.medido = 0;
      this.pilaMedida = false;
      this.pintar(0, true);
      this.arrancar();
    }

    // La pila: dónde queda cada verso si estuvieran uno debajo del otro, según
    // su altura real (un verso largo ocupa dos o tres renglones).
    medirPila() {
      if (this.pilaMedida || !this.lineas.length) return;
      let y = 0;
      let previo = 0;
      this.lineas.forEach((linea, i) => {
        const alto = linea.nodo.offsetHeight;
        const renglon = parseFloat(getComputedStyle(linea.nodo).fontSize) || 40;
        if (i > 0) y += (previo + alto) / 2 + renglon * HUECO;
        linea.y = y;
        previo = alto;
      });
      // Si todavía no hay layout (vista oculta), se vuelve a medir después.
      this.pilaMedida = previo > 0;
    }

    yDeCamara(c) {
      const n = this.lineas.length;
      const paso = n > 1 ? this.lineas[1].y - this.lineas[0].y : 80;
      if (c <= 0) return this.lineas[0].y + c * paso;
      if (c >= n - 1) return this.lineas[n - 1].y + (c - n + 1) * paso;
      const i = Math.floor(c);
      const f = c - i;
      return this.lineas[i].y + (this.lineas[i + 1].y - this.lineas[i].y) * f;
    }

    tiempo() {
      return (this.audio ? this.audio.currentTime : 0) + this.desfase;
    }

    indiceEn(t) {
      let indice = -1;
      for (let i = 0; i < this.lineas.length; i += 1) {
        if (this.lineas[i].t <= t + 0.08) indice = i;
        else break;
      }
      return indice;
    }

    // El punto de fuga es el centro del disco (si lo hay), relativo a la letra.
    medirFuga() {
      const ahora = performance.now();
      if (ahora - this.fuga.medido < 400) return;
      this.fuga.medido = ahora;
      const caja = this.raiz.getBoundingClientRect();
      const r = this.origen ? this.origen() : null;
      if (r && r.width && caja.width) {
        this.fuga.x = Math.max(-0.4, Math.min(1.4, (r.left + r.width / 2 - caja.left) / caja.width));
        this.fuga.y = Math.max(-0.4, Math.min(1.2, (r.top + r.height / 2 - caja.top) / caja.height));
      } else {
        this.fuga.x = 0.5;
        this.fuga.y = 0.28;
      }
      this.raiz.style.setProperty("--fx", `${(this.fuga.x * 100).toFixed(1)}%`);
      this.raiz.style.setProperty("--fy", `${(this.fuga.y * 100).toFixed(1)}%`);
    }

    // Ubica cada verso en el túnel según la cámara. Solo se tocan los que se ven.
    pintar(dt, inmediato) {
      if (!this.sincroniza || !this.lineas.length) return;
      this.medirFuga();
      const ahora = performance.now();
      if (this.manual && ahora > this.manualHasta) {
        this.manual = 0;
        this.raiz.classList.remove("viajando");
      }
      const destino = this.objetivo + this.manual;
      const suave = inmediato || reduce ? 1 : 1 - Math.exp(-dt * 5.5);
      this.camara += (destino - this.camara) * suave;

      const p = this.puntero;
      const k = reduce ? 1 : 1 - Math.exp(-dt * 4);
      p.x += (p.ox - p.x) * (inmediato ? 1 : k);
      p.y += (p.oy - p.y) * (inmediato ? 1 : k);
      const w = this.raiz.clientWidth || 1;
      const h = this.raiz.clientHeight || 1;
      // El túnel apunta hacia el disco en horizontal (sin sacar los versos de la
      // vista); en vertical la fuga queda a la altura del verso que suena, así
      // la pila baja siempre derecha. Los surcos del fondo sí nacen del disco.
      const fx = Math.max(0.22, Math.min(0.78, this.fuga.x)) + p.x * 0.35;
      const fy = ANCLA + p.y * 0.35;
      this.pista.style.perspectiveOrigin = `${(fx * w).toFixed(1)}px ${(fy * h).toFixed(1)}px`;
      const bajo = window.KL && window.KL.nivel ? window.KL.nivel.bass || 0 : 0;
      this.medirPila();
      const yCamara = this.yDeCamara(this.camara);

      this.lineas.forEach((linea, i) => {
        const d = i - this.camara;
        const estado = linea.estado;
        const visible = d > -ATRAS && d < ADELANTE;
        if (visible !== estado.visible) {
          estado.visible = visible;
          linea.nodo.style.visibility = visible ? "" : "hidden";
        }
        if (!visible) return;
        let x;
        let y;
        let z;
        let giro;
        let opacidad;
        let desenfoque;
        if (d >= 0) {
          // Lo que viene: la pila baja hacia el fondo, cada verso un poco
          // corrido y girado (un mazo abierto), más tenue cuanto más lejos.
          const lejos = Math.min(d, 1);
          x = linea.semilla * d * 30;
          // La perspectiva junta los versos lejanos: se compensa para que la
          // escalera siga respirando.
          y = ((linea.y || 0) - yCamara) * (1 + (d * PASO_Z) / 1000);
          z = -d * PASO_Z;
          giro = linea.semilla * lejos * 7;
          opacidad = d < 1 ? 1 - d * 0.6 : Math.max(0, 0.4 - (d - 1) * 0.07);
          desenfoque = Math.min(5, d * 1.2);
        } else {
          // Lo que pasó: sube y viene hacia la cámara, desvaneciéndose.
          const a = -d;
          x = 0;
          y = (linea.y || 0) - yCamara - a * 60;
          z = a * SALIDA_Z;
          giro = 0;
          opacidad = Math.max(0, 1 - a * 1.35);
          desenfoque = Math.min(8, a * 7);
        }
        if (Math.abs(d) < 0.5) z += bajo * 70;
        // Solo se escribe si cambió (con la cámara quieta, ningún verso se toca).
        const transform =
          `translate3d(${x.toFixed(1)}px, calc(-50% + ${y.toFixed(1)}px), ${z.toFixed(1)}px) rotateY(${giro.toFixed(2)}deg)`;
        if (transform !== estado.t) {
          estado.t = transform;
          linea.nodo.style.transform = transform;
        }
        const o = opacidad.toFixed(2);
        if (o !== estado.o) {
          estado.o = o;
          linea.nodo.style.opacity = o;
        }
        const f = reduce ? 0 : Math.round(desenfoque * 2) / 2;
        if (f !== estado.f) {
          estado.f = f;
          linea.nodo.style.filter = f ? `blur(${f}px)` : "";
        }
      });
    }

    marcar(indice) {
      this.lineas.forEach((linea, i) => {
        linea.nodo.classList.toggle("activa", i === indice);
        linea.nodo.classList.toggle("pasada", i < indice);
        if (linea.marca) {
          linea.marca.classList.toggle("activa", i === indice);
          linea.marca.classList.toggle("pasada", i < indice);
        }
      });
      const linea = this.lineas[indice];
      const palabra = linea ? linea.fantasma : "";
      if (this.fantasma.textContent !== palabra) {
        this.fantasma.textContent = palabra;
        this.fantasma.classList.remove("cambia");
        void this.fantasma.offsetWidth;
        this.fantasma.classList.add("cambia");
      }
    }

    cuadro(dt) {
      if (!this.sincroniza || !this.lineas.length) return;
      const t = this.tiempo();
      const indice = this.indiceEn(t);
      if (indice !== this.activa) {
        const avanzo = indice > this.activa;
        this.activa = indice;
        this.marcar(indice);
        if (avanzo && indice >= 0) {
          this.entrar(this.lineas[indice]);
          if (this.alCambiar) this.alCambiar(indice);
        }
      }
      // Relleno palabra por palabra de la línea activa.
      if (indice >= 0) {
        const linea = this.lineas[indice];
        if (this.alAvanzar) {
          this.alAvanzar(Math.max(0, Math.min(1, (t - linea.t) / Math.max(0.3, linea.fin - linea.t))));
        }
        linea.palabras.forEach((w) => {
          const p = Math.max(0, Math.min(1, (t - w.inicio) / Math.max(0.05, w.fin - w.inicio)));
          if (w.p !== p) {
            w.p = p;
            w.nodo.style.setProperty("--p", p.toFixed(3));
            const dicha = p >= 1;
            if (dicha && !w.dicha) this.chispaDePalabra(w);
            w.dicha = dicha;
            w.nodo.classList.toggle("dicha", dicha);
            w.nodo.classList.toggle("cantando", p > 0 && p < 1);
          }
        });
      }
      // Interludio: la cámara queda entre dos versos y los puntos esperan al frente.
      const actual = this.lineas[indice];
      const siguiente = this.lineas[indice + 1];
      let enPausa = false;
      let avance = 0;
      let objetivo = Math.max(indice, -1.1);
      if (indice < 0) {
        enPausa = this.lineas[0].t - t > 2;
        avance = Math.max(0, Math.min(1, t / Math.max(1, this.lineas[0].t)));
        objetivo = -1.1;
      } else if (actual && siguiente && actual.hueco > INTERLUDIO && t > actual.fin + 0.4) {
        enPausa = true;
        avance = Math.max(0, Math.min(1, (t - actual.fin) / Math.max(1, siguiente.t - actual.fin)));
        objetivo = indice + 0.7;
      }
      this.objetivo = objetivo;
      this.puntos.classList.toggle("visible", enPausa);
      this.puntos.style.setProperty("--avance", avance.toFixed(3));
      this.pintar(dt, false);
    }

    // Lo que pasa cuando entra un verso: su animación (CSS, según data-entrada),
    // partículas y, si es un golpe, un sacudón de la pantalla.
    entrar(linea) {
      if (reduce) return;
      const nodo = linea.nodo;
      nodo.classList.remove("entra");
      void nodo.offsetWidth;
      nodo.classList.add("entra");
      const caja = this.raiz.getBoundingClientRect();
      const r = nodo.getBoundingClientRect();
      const x = r.left - caja.left;
      const y = r.top - caja.top + r.height / 2;
      const motivo = nodo.dataset.motivo || "";
      if (nodo.dataset.entrada === "impacto") {
        this.raiz.classList.remove("sacudida");
        void this.raiz.offsetWidth;
        this.raiz.classList.add("sacudida");
        this.chispas.soltar(x + r.width / 2 - 30, y, Math.min(r.width, 60), motivo, motivo ? 16 : 26, 1.6);
      } else {
        this.chispas.soltar(x, y, r.width, motivo, motivo ? 10 : 6);
      }
      if (nodo.dataset.entrada === "eco") this.eco(nodo, linea.texto);
    }

    // Estribillo que vuelve: dos fantasmas del verso se alejan como un eco.
    eco(nodo, texto) {
      for (let i = 0; i < 2; i += 1) {
        const fantasma = crear("span", "kl-karaoke__eco");
        fantasma.textContent = texto;
        fantasma.style.animationDelay = `${i * 160}ms`;
        fantasma.setAttribute("aria-hidden", "true");
        nodo.appendChild(fantasma);
        setTimeout(() => fantasma.remove(), 1400);
      }
    }

    chispaDePalabra(w) {
      if (reduce) return;
      const caja = this.raiz.getBoundingClientRect();
      const r = w.nodo.getBoundingClientRect();
      if (!r.width) return;
      this.chispas.soltar(r.right - caja.left - 4, r.top - caja.top + r.height * 0.4, 6,
        w.motivo, w.motivo ? 5 : 2, w.motivo ? 1 : 0.6);
    }

    // Cada karaoke se suscribe al reloj común con su propio nombre.
    arrancar() {
      if (!this.nombre) this.nombre = `karaoke-${Math.random().toString(36).slice(2, 8)}`;
      window.KL.reloj.agregar(this.nombre, (dt) => {
        if (!this.visible || !this.raiz.isConnected) return false;
        if (!this.sincroniza) return false;
        this.cuadro(dt);
        this.chispas.cuadro(dt);
        return true;
      });
    }

    mostrarse(visible) {
      this.visible = visible;
      if (visible) {
        this.fuga.medido = 0;
        this.pintar(0, true);
        this.arrancar();
      }
    }
  }

  window.KLKaraoke = KLKaraoke;

  // Arma la letra de un tema en un karaoke: busca, ubica el adelanto y dibuja.
  window.KLMontarLetra = async function montarLetra(karaoke, pista, esVigente) {
    if (!pista) {
      karaoke.aviso("Reproducí un tema para ver la letra.");
      return;
    }
    if (!window.KLLetra) {
      karaoke.aviso("La letra no está disponible.");
      return;
    }
    karaoke.aviso("Buscando la letra…");
    let letra;
    try {
      letra = await window.KLLetra.obtener(pista);
    } catch (error) {
      if (esVigente()) karaoke.aviso("No pudimos traer la letra.");
      return;
    }
    if (!esVigente()) return;
    if (!letra.versos.length) {
      karaoke.aviso("No hay una letra publicada para este tema.");
      return;
    }
    const externa = pista.externo || !window.KL.util.esLocal(pista.id);
    if (!letra.sincroniza || !externa) {
      karaoke.mostrar(letra.versos, { sincroniza: letra.sincroniza });
      return;
    }
    // Adelanto: se sincroniza solo si ya se sabe dónde empieza dentro del tema.
    if (typeof pista.desfase === "number") {
      karaoke.mostrar(letra.versos, { sincroniza: true, desfase: pista.desfase });
    } else {
      karaoke.mostrar(letra.versos, { sincroniza: false, nota: "Letra completa · el adelanto es un fragmento" });
    }
  };
})();

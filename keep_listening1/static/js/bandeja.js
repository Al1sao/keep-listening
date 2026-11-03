/* ===========================================================================
 * Keep Listening - "La bandeja" (reproductor fijo)
 *
 *  1. Plato: el disco gira a la velocidad real del audio (frena y arranca con
 *     el tocadiscos). Agarrarlo y girarlo hace scratch: adelanta o retrocede
 *     y el tono sigue a la mano. Un toque sin girar abre "Ahora suena".
 *  2. Mapa del tema: la huella del audio (se decodifica una vez por tema),
 *     marcas donde empieza cada verso y los estribillos resaltados (versos que
 *     se repiten). Al pasar el puntero se ve el verso de ese momento. Cerca de
 *     la púa, la huella respira con los graves.
 *  3. Perilla de volumen: arrastrar, rueda o flechas. Doble clic silencia.
 *  4. Pila: las tapas de los próximos temas.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL;
  const audio = document.getElementById("kl-audio");
  const barra = document.getElementById("kl-player");
  if (!audio || !barra || !KL || !KL.reloj) return;

  const { limitar, formatear, reduce } = KL.util;
  const $ = (id) => document.getElementById(id);
  const el = {
    disco: $("kl-bandeja-disco"),
    vinilo: $("kl-bandeja-vinilo"),
    giro: $("kl-bandeja-giro"),
    mapa: $("kl-mapa"),
    lienzo: $("kl-mapa-lienzo"),
    rango: $("kl-player-barra"),
    globo: $("kl-mapa-globo"),
    estribillo: $("kl-mapa-estribillo"),
    volumenCaja: $("kl-volumen"),
    volumenValor: document.querySelector(".kl-volumen__valor"),
    volumen: $("kl-player-volumen"),
    silencio: $("kl-player-silencio"),
    pila: $("kl-bandeja-pila"),
  };

  let pista = null;

  // =========================================================================
  // 1. Plato
  // =========================================================================
  const GRADOS_POR_SEGUNDO = KL.GRADOS_POR_SEGUNDO || 90; // una vuelta cada 4 s
  const SEGUNDOS_POR_VUELTA = 2.4; // cuánto del tema recorre una vuelta de scratch
  const plato = { angulo: 0, rayando: false, recienRayado: false };

  function girarPlato(dt) {
    if (!plato.rayando && !audio.paused && !reduce) {
      plato.angulo = (plato.angulo + dt * GRADOS_POR_SEGUNDO * (audio.playbackRate || 1)) % 360;
    }
    el.giro.style.transform = `rotate(${plato.angulo.toFixed(2)}deg)`;
    return !audio.paused || plato.rayando;
  }

  function encenderPlato() {
    KL.reloj.agregar("bandeja-plato", girarPlato);
  }

  if (el.disco) {
    let toque = null;
    const angulo = (evento) => {
      const r = el.disco.getBoundingClientRect();
      return Math.atan2(evento.clientY - (r.top + r.height / 2), evento.clientX - (r.left + r.width / 2));
    };

    el.disco.addEventListener("pointerdown", (evento) => {
      if (!audio.getAttribute("src")) return;
      toque = { ultimo: angulo(evento), t: performance.now(), movido: 0, id: evento.pointerId };
    });

    el.disco.addEventListener("pointermove", (evento) => {
      if (!toque || evento.pointerId !== toque.id) return;
      const a = angulo(evento);
      let delta = a - toque.ultimo;
      if (delta > Math.PI) delta -= Math.PI * 2;
      if (delta < -Math.PI) delta += Math.PI * 2;
      toque.ultimo = a;
      toque.movido += Math.abs(delta);
      const ahora = performance.now();
      const dt = Math.max(0.008, (ahora - toque.t) / 1000);
      toque.t = ahora;
      if (!plato.rayando && toque.movido > 0.15) {
        plato.rayando = true;
        el.disco.setPointerCapture(evento.pointerId);
        barra.classList.add("rayando");
        ["preservesPitch", "mozPreservesPitch", "webkitPreservesPitch"].forEach((c) => { if (c in audio) audio[c] = false; });
        encenderPlato();
      }
      if (!plato.rayando) return;
      plato.angulo += (delta * 180) / Math.PI;
      const segundos = (delta / (Math.PI * 2)) * SEGUNDOS_POR_VUELTA;
      if (audio.duration) audio.currentTime = limitar(audio.currentTime + segundos, 0, audio.duration - 0.05);
      // El tono sigue a la mano: más rápido el giro, más agudo.
      const velocidad = Math.abs(delta / dt) / ((GRADOS_POR_SEGUNDO * Math.PI) / 180);
      audio.playbackRate = limitar(velocidad, 0.25, 3.5);
    });

    const soltar = (evento) => {
      if (!toque || evento.pointerId !== toque.id) return;
      toque = null;
      if (!plato.rayando) return;
      plato.rayando = false;
      plato.recienRayado = true;
      barra.classList.remove("rayando");
      audio.playbackRate = 1;
      ["preservesPitch", "mozPreservesPitch", "webkitPreservesPitch"].forEach((c) => { if (c in audio) audio[c] = true; });
      setTimeout(() => { plato.recienRayado = false; }, 60);
    };
    el.disco.addEventListener("pointerup", soltar);
    el.disco.addEventListener("pointercancel", soltar);

    // Después de rayar, el clic que llega no abre "Ahora suena" (se corta antes
    // de que lo vea el resto de la página).
    window.addEventListener("click", (evento) => {
      if (plato.recienRayado && evento.target.closest("#kl-bandeja-disco")) {
        evento.preventDefault();
        evento.stopImmediatePropagation();
      }
    }, true);
  }

  // =========================================================================
  // 2. Mapa del tema
  // =========================================================================
  const BARRAS = 160;
  const huellas = new Map();
  const mapa = { huella: null, marcas: [], estribillos: [], hover: -1, dibujado: "" };
  const ctx = el.lienzo ? el.lienzo.getContext("2d") : null;
  const SIN_VOZ = /^[\s♪♫…·.-]*$/;

  function duracion() {
    return audio.duration && isFinite(audio.duration) ? audio.duration : (pista && pista.duracion) || 30;
  }

  // La huella se calcula del audio real, una sola vez por tema.
  async function calcularHuella(tema) {
    const id = String(tema.id);
    if (huellas.has(id)) return huellas.get(id);
    const promesa = (async () => {
      const respuesta = await fetch(tema.audio, { credentials: "same-origin" });
      if (!respuesta.ok) throw new Error(String(respuesta.status));
      const largo = Number(respuesta.headers.get("Content-Length") || 0);
      if (largo > 15 * 1024 * 1024) throw new Error("demasiado grande");
      const crudo = await respuesta.arrayBuffer();
      const buffer = await new OfflineAudioContext(1, 1, 44100).decodeAudioData(crudo);
      const datos = buffer.getChannelData(0);
      const paso = Math.max(1, Math.floor(datos.length / BARRAS));
      const huella = new Float32Array(BARRAS);
      let maximo = 0.0001;
      for (let b = 0; b < BARRAS; b += 1) {
        let suma = 0;
        let pico = 0;
        for (let i = b * paso; i < Math.min(datos.length, (b + 1) * paso); i += 4) {
          const v = Math.abs(datos[i]);
          suma += v * v;
          if (v > pico) pico = v;
        }
        huella[b] = Math.sqrt(suma / (paso / 4)) * 0.7 + pico * 0.3;
        maximo = Math.max(maximo, huella[b]);
      }
      for (let b = 0; b < BARRAS; b += 1) huella[b] = Math.pow(huella[b] / maximo, 0.8);
      return huella;
    })();
    huellas.set(id, promesa);
    promesa.catch(() => huellas.delete(id));
    return promesa;
  }

  // Versos y estribillos ubicados en el tiempo del audio que suena.
  async function calcularMarcas(tema) {
    if (!window.KLLetra) return { marcas: [], estribillos: [] };
    const externa = tema.externo || !KL.util.esLocal(tema.id);
    const desfase = externa ? tema.desfase : 0;
    if (typeof desfase !== "number") return { marcas: [], estribillos: [] };
    const letra = await window.KLLetra.obtener(tema);
    if (!letra.sincroniza) return { marcas: [], estribillos: [] };
    const clave = (texto) => texto.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
    const veces = new Map();
    letra.versos.forEach((v) => {
      if (!SIN_VOZ.test(v.texto)) veces.set(clave(v.texto), (veces.get(clave(v.texto)) || 0) + 1);
    });
    const total = duracion();
    const marcas = [];
    letra.versos.forEach((v, i) => {
      const t = v.t - desfase;
      if (t < 0 || t > total || SIN_VOZ.test(v.texto)) return;
      const siguiente = letra.versos[i + 1] ? letra.versos[i + 1].t - desfase : t + 4;
      marcas.push({ t, fin: Math.min(siguiente, t + 8), texto: v.texto, estribillo: veces.get(clave(v.texto)) >= 2 });
    });
    // Estribillo = tramo de versos repetidos seguidos.
    const estribillos = [];
    marcas.forEach((m) => {
      if (!m.estribillo) return;
      const ultimo = estribillos[estribillos.length - 1];
      if (ultimo && m.t - ultimo.b < 1.5) ultimo.b = Math.max(ultimo.b, m.fin);
      else estribillos.push({ a: m.t, b: m.fin });
    });
    return { marcas, estribillos: estribillos.filter((e) => e.b - e.a > 3) };
  }

  async function prepararMapa(tema) {
    mapa.huella = null;
    mapa.marcas = [];
    mapa.estribillos = [];
    el.estribillo.hidden = true;
    dibujarMapa();
    if (!tema || !tema.audio) return;
    const id = String(tema.id);
    calcularHuella(tema).then((huella) => {
      if (pista && String(pista.id) === id) { mapa.huella = huella; dibujarMapa(); }
    }).catch(() => {});
    calcularMarcas(tema).then((datos) => {
      if (!pista || String(pista.id) !== id) return;
      mapa.marcas = datos.marcas;
      mapa.estribillos = datos.estribillos;
      el.estribillo.hidden = !datos.estribillos.length;
      dibujarMapa();
    }).catch(() => {});
  }

  const color = KL.util.color;

  let colores = null;
  // Tamaño del mapa (se mide al cambiar, no en cada cuadro) y qué barra cae en
  // un estribillo (se calcula una vez por tema y duración, no por barra y cuadro).
  const medida = { ancho: 0, alto: 0 };
  let barrasEstribillo = { total: -1, estribillos: null, marcas: new Uint8Array(BARRAS) };

  function estribilloPorBarra(total) {
    if (barrasEstribillo.total === total && barrasEstribillo.estribillos === mapa.estribillos) {
      return barrasEstribillo.marcas;
    }
    const marcas = new Uint8Array(BARRAS);
    for (let b = 0; b < BARRAS; b += 1) {
      const t = ((b + 0.5) / BARRAS) * total;
      marcas[b] = mapa.estribillos.some((e) => t >= e.a && t <= e.b) ? 1 : 0;
    }
    barrasEstribillo = { total, estribillos: mapa.estribillos, marcas };
    return marcas;
  }
  document.addEventListener("kl:paleta", () => { colores = null; dibujarMapa(); });

  function dibujarMapa() {
    if (!ctx) return;
    const ancho = medida.ancho || el.lienzo.clientWidth;
    const alto = medida.alto || el.lienzo.clientHeight;
    if (!ancho || !alto) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (el.lienzo.width !== Math.round(ancho * dpr) || el.lienzo.height !== Math.round(alto * dpr)) {
      el.lienzo.width = Math.round(ancho * dpr);
      el.lienzo.height = Math.round(alto * dpr);
    }
    if (!colores) {
      colores = {
        tocado: color("--kl-c1", 1),
        estribillo: color("--kl-c2", 0.9),
        banda: color("--kl-c2", 0.14),
        resto: "rgba(255, 255, 255, 0.24)",
      };
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, ancho, alto);
    const total = duracion();
    const progreso = total ? audio.currentTime / total : 0;
    const xPua = progreso * ancho;

    // Bandas de estribillo detrás de todo.
    mapa.estribillos.forEach((e) => {
      const x = (e.a / total) * ancho;
      const w = ((e.b - e.a) / total) * ancho;
      ctx.fillStyle = colores.banda;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, 0, w, alto, 4) : ctx.rect(x, 0, w, alto);
      ctx.fill();
    });

    // La huella: barras espejadas. Si todavía no está, un surco quieto.
    const ancho1 = ancho / BARRAS;
    const medio = alto * 0.56;
    const bajo = KL.nivel && KL.nivel.sonando ? KL.nivel.bass : 0;
    const enEstribillos = estribilloPorBarra(total);
    for (let b = 0; b < BARRAS; b += 1) {
      const x = b * ancho1;
      const base = mapa.huella ? mapa.huella[b] : 0.18 + 0.08 * Math.sin(b * 0.7) * Math.sin(b * 0.13);
      const cerca = Math.max(0, 1 - Math.abs(x - xPua) / (ancho * 0.07));
      const h = Math.max(1.5, (base * 0.82 + cerca * bajo * 0.45) * medio);
      const enEstribillo = enEstribillos[b] === 1;
      ctx.fillStyle = x <= xPua ? colores.tocado : enEstribillo ? colores.estribillo : colores.resto;
      ctx.globalAlpha = x <= xPua || !mapa.huella ? 1 : enEstribillo ? 0.55 : 1;
      const w = Math.max(1, ancho1 - 1.2);
      ctx.fillRect(x, medio - h, w, h);
      ctx.globalAlpha *= 0.45;
      ctx.fillRect(x, medio + 1, w, h * 0.45);
      ctx.globalAlpha = 1;
    }

    // Marcas de versos: puntitos abajo.
    mapa.marcas.forEach((m) => {
      const x = (m.t / total) * ancho;
      ctx.fillStyle = m.t <= audio.currentTime ? colores.tocado : "rgba(255, 255, 255, 0.45)";
      ctx.beginPath();
      ctx.arc(x, alto - 2, m.estribillo ? 2 : 1.3, 0, Math.PI * 2);
      ctx.fill();
    });

    // Púa y fantasma del puntero.
    if (mapa.hover >= 0) {
      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      ctx.fillRect(mapa.hover - 0.5, 0, 1, alto);
    }
    ctx.shadowColor = colores.tocado;
    ctx.shadowBlur = 8;
    ctx.fillStyle = "#fff";
    ctx.fillRect(xPua - 1, 0, 2, alto);
    ctx.shadowBlur = 0;
  }

  // Con el audio en pausa, mover el puntero redibuja a lo sumo una vez por cuadro.
  let dibujoPendiente = false;
  function pedirDibujo() {
    if (dibujoPendiente) return;
    dibujoPendiente = true;
    requestAnimationFrame(() => {
      dibujoPendiente = false;
      dibujarMapa();
    });
  }

  function versoEn(t) {
    let actual = null;
    for (const m of mapa.marcas) {
      if (m.t <= t) actual = m;
      else break;
    }
    return actual && t - actual.t < 9 ? actual : null;
  }

  if (el.mapa) {
    const pistaMapa = el.mapa.querySelector(".kl-mapa__pista");
    pistaMapa.addEventListener("pointermove", (evento) => {
      const r = pistaMapa.getBoundingClientRect();
      const x = limitar(evento.clientX - r.left, 0, r.width);
      mapa.hover = x;
      const t = (x / r.width) * duracion();
      const verso = versoEn(t);
      el.globo.querySelector("strong").textContent = formatear(t);
      el.globo.querySelector("span").textContent = verso ? verso.texto : "";
      el.globo.classList.toggle("con-verso", !!verso);
      el.globo.style.setProperty("--x", `${x}px`);
      el.globo.classList.add("visible");
      if (audio.paused) pedirDibujo();
    });
    pistaMapa.addEventListener("pointerleave", () => {
      mapa.hover = -1;
      el.globo.classList.remove("visible");
      if (audio.paused) pedirDibujo();
    });

    el.estribillo.addEventListener("click", () => {
      if (!mapa.estribillos.length) return;
      const ahora = audio.currentTime;
      const destino = mapa.estribillos.find((e) => e.a > ahora + 1) || mapa.estribillos[0];
      audio.currentTime = Math.max(0, destino.a - 0.3);
      if (window.KLAmbiente) {
        const r = el.lienzo.getBoundingClientRect();
        window.KLAmbiente.onda((r.left + (destino.a / duracion()) * r.width) / innerWidth, r.top / innerHeight, 1);
      }
      if (audio.paused && window.KLPlayer) window.KLPlayer.alternarPlay();
    });

    if ("ResizeObserver" in window) {
      new ResizeObserver(() => {
        medida.ancho = el.lienzo.clientWidth;
        medida.alto = el.lienzo.clientHeight;
        dibujarMapa();
      }).observe(pistaMapa);
    }
    audio.addEventListener("timeupdate", () => { if (audio.paused) dibujarMapa(); });
    audio.addEventListener("seeked", dibujarMapa);
    audio.addEventListener("loadedmetadata", () => { if (pista) prepararMapa(pista); });
  }

  // Mientras suena, el mapa (y el plato) se redibujan con el reloj común.
  function cuadroMapa() {
    dibujarMapa();
    return !audio.paused;
  }

  // =========================================================================
  // 3. Volumen: una barra horizontal (range nativo) con su animación
  // =========================================================================
  // La barra siempre marca el volumen real; en silencio solo se apaga (no
  // salta a cero), así al volver queda donde estaba. --vol lo usa el CSS para
  // el relleno, las barritas encendidas y el giro del mini vinilo.
  function pintarVolumen() {
    if (!el.volumenCaja || !el.volumen) return;
    const v = Number(el.volumen.value);
    const mudo = audio.muted || v === 0;
    el.volumenCaja.style.setProperty("--vol", v);
    el.volumenCaja.classList.toggle("muda", mudo);
    const porcentaje = Math.round(v * 100);
    el.volumen.setAttribute("aria-valuetext", mudo ? "Silenciado" : `${porcentaje} %`);
    if (el.volumenValor) el.volumenValor.textContent = mudo ? "Mudo" : `${porcentaje}%`;
  }

  // Mientras se mueve (y un ratito después) se ve el número arriba del tirador.
  let ocultarValor = 0;
  function mostrarValor() {
    el.volumenCaja.classList.add("mostrando");
    clearTimeout(ocultarValor);
    ocultarValor = setTimeout(() => el.volumenCaja.classList.remove("mostrando"), 900);
  }

  function ponerVolumen(v) {
    el.volumen.value = String(limitar(Math.round(v * 100) / 100, 0, 1));
    el.volumen.dispatchEvent(new Event("input", { bubbles: true }));
  }

  if (el.volumenCaja && el.volumen) {
    el.volumen.addEventListener("input", () => {
      pintarVolumen();
      mostrarValor();
    });
    // Las flechas mueven de a 5 % (el range solo, de a 1 %, apenas se nota).
    el.volumen.addEventListener("keydown", (evento) => {
      const pasos = { ArrowUp: 0.05, ArrowRight: 0.05, ArrowDown: -0.05, ArrowLeft: -0.05, PageUp: 0.2, PageDown: -0.2 };
      if (!(evento.key in pasos)) return;
      evento.preventDefault();
      ponerVolumen(Number(el.volumen.value) + pasos[evento.key]);
    });
    // La rueda se acumula: un touchpad manda pasos muy chicos que, de a uno,
    // se perderían al redondear. Un clic de rueda de mouse sube o baja 5 %.
    let rueda = 0;
    el.volumenCaja.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      const pixeles = evento.deltaMode === 1 ? evento.deltaY * 33 : evento.deltaY;
      rueda -= pixeles * 0.0005;
      if (Math.abs(rueda) < 0.01) return;
      ponerVolumen(Number(el.volumen.value) + rueda);
      rueda = 0;
    }, { passive: false });
    audio.addEventListener("volumechange", pintarVolumen);
    pintarVolumen();
  }

  // =========================================================================
  // 4. Pila de próximos
  // =========================================================================
  function pintarPila() {
    if (!el.pila || !window.KLPlayer) return;
    const { pistas, indice } = window.KLPlayer.estado;
    el.pila.replaceChildren();
    for (let paso = 3; paso >= 1; paso -= 1) {
      const tema = pistas[indice + paso];
      if (!tema || !tema.portada) continue;
      const img = document.createElement("img");
      img.src = tema.portada;
      img.alt = "";
      img.width = 28;
      img.height = 28;
      img.loading = "lazy";
      img.style.setProperty("--n", String(paso));
      el.pila.appendChild(img);
    }
  }

  // =========================================================================
  // Eventos del reproductor
  // =========================================================================
  document.addEventListener("kl:reproductor", (evento) => {
    const detalle = evento.detail || {};
    const cambio = detalle.pista && (!pista || String(detalle.pista.id) !== String(pista.id));
    if (detalle.pista) pista = detalle.pista;
    if (cambio) {
      if (window.KLDisco && el.vinilo) el.vinilo.dataset.estilo = String(window.KLDisco.diseno(pista).estilo);
      prepararMapa(pista);
    }
    pintarPila();
    if (detalle.sonando) {
      encenderPlato();
      KL.reloj.agregar("bandeja-mapa", cuadroMapa);
    } else {
      dibujarMapa();
    }
  });

  dibujarMapa();
})();

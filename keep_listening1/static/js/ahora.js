/* ===========================================================================
 * Keep Listening - "Ahora suena"
 * La hoja sube desde abajo y la portada chica vuela hasta su lugar. Adelante
 * está la tapa (se inclina con el puntero y respira con los graves); atrás,
 * la letra sincronizada. Deslizar la portada cambia de tema y arrastrar la
 * hoja hacia abajo la cierra.
 * =========================================================================== */
(function () {
  "use strict";

  const reduce = window.KL.util.reduce;
  const panel = document.getElementById("kl-estudio");
  const hoja = document.getElementById("kl-ahora-hoja");
  if (!panel || !hoja) return;

  const $ = (id) => document.getElementById(id);
  const el = {
    tarjeta: $("kl-ahora-tarjeta"),
    frente: $("kl-ahora-frente"),
    letras: $("kl-ahora-letras"),
    giro: $("kl-ahora-giro"),
    portada: $("kl-estudio-portada"),
    vacia: $("kl-ahora-vacia"),
    titulo: $("kl-estudio-titulo"),
    artista: $("kl-estudio-artista"),
    nota: $("kl-estudio-nota"),
    completa: $("kl-estudio-completa"),
    origen: $("kl-ahora-origen"),
    letra: $("kl-ahora-letra"),
    barra: $("kl-ahora-barra"),
    actual: $("kl-ahora-actual"),
    total: $("kl-ahora-total"),
    espectro: $("kl-ahora-espectro"),
    siguen: $("kl-ahora-siguen"),
    disco: $("kl-ahora-disco"),
    edicion: $("kl-ahora-edicion"),
  };

  let abierto = false;
  let ultimoFoco = null;
  let origenRect = null;
  let pista = null;
  let sonando = false;
  let volteada = false;
  let arrastrandoBarra = false;

  const player = () => window.KLPlayer;
  const audio = () => (window.KLPlayer ? window.KLPlayer.audio : document.getElementById("kl-audio"));
  const formatear = (s) => (window.KLPlayer ? window.KLPlayer.formatear(s) : "0:00");

  // -----------------------------------------------------------------------
  // Contenido
  // -----------------------------------------------------------------------
  function esExterna(tema) {
    return tema && (tema.externo || !window.KL.util.esLocal(tema.id));
  }

  function pintar() {
    el.titulo.textContent = pista ? pista.titulo : "Keep Listening";
    el.artista.textContent = pista ? pista.artista : "Elegí un tema o encendé la radio";
    if (pista && pista.portada) {
      if (el.portada.getAttribute("src") !== pista.portada) el.portada.src = pista.portada;
      el.portada.alt = `Portada de ${pista.titulo}`;
      el.portada.hidden = false;
      el.vacia.hidden = true;
    } else {
      el.portada.removeAttribute("src");
      el.portada.hidden = true;
      el.vacia.hidden = false;
    }
    const externa = esExterna(pista);
    el.nota.textContent = !externa ? "" : pista.compra
      ? "Muestra del disco que compraste."
      : "Adelanto de unos 30 segundos.";
    el.nota.hidden = !externa;
    const ficha = externa && pista.url && /^https:\/\//.test(pista.url) ? pista.url : "";
    el.completa.hidden = !ficha;
    if (ficha) el.completa.href = ficha;
    el.origen.textContent = pista ? (pista.fuente || pista.genero || "Keep Listening") : "Keep Listening";

    panel.querySelectorAll("[data-estudio-play]").forEach((boton) => {
      boton.querySelector("i").className = sonando ? "bi bi-pause-fill" : "bi bi-play-fill";
      boton.setAttribute("aria-label", sonando ? "Pausar" : "Reproducir");
    });
    panel.classList.toggle("sonando", sonando);
    pintarDisco();
    copiarCorazon();
  }

  // El corazón de la hoja copia al del reproductor (mismo tema, mismo estado):
  // así un solo lugar sabe si es favorito propio o me gusta de Apple.
  const gustaHoja = document.getElementById("kl-ahora-gusta");
  const gustaPlayer = document.getElementById("kl-player-fav");
  function copiarCorazon() {
    if (!gustaHoja || !gustaPlayer) return;
    const guardada = gustaPlayer.classList.contains("guardada");
    gustaHoja.classList.toggle("guardada", guardada);
    gustaHoja.setAttribute("aria-pressed", String(guardada));
    gustaHoja.querySelector("i").className = `bi ${guardada ? "bi-heart-fill" : "bi-heart"}`;
    gustaHoja.hidden = !pista || Boolean(pista.compra);
  }
  if (gustaHoja && gustaPlayer) {
    gustaHoja.addEventListener("click", () => gustaPlayer.click());
    new MutationObserver(copiarCorazon).observe(gustaPlayer, { attributes: true, attributeFilter: ["class"] });
  }

  function pintarDisco() {
    if (!el.disco || !window.KLDisco) return;
    const diseno = window.KLDisco.diseno(pista);
    el.disco.dataset.estilo = String(diseno.estilo);
    const portada = pista && pista.portada ? `url("${String(pista.portada).replace(/"/g, "")}")` : "none";
    el.disco.style.setProperty("--portada", portada);
    if (el.edicion) {
      el.edicion.querySelector("span").textContent = `Vinilo ${diseno.nombre.toLowerCase()}`;
      el.edicion.hidden = !pista;
    }
  }

  function pintarModos(detalle) {
    const aleatorio = panel.querySelector("[data-ahora-aleatorio]");
    const repetir = panel.querySelector("[data-ahora-repetir]");
    if (aleatorio) {
      aleatorio.classList.toggle("activo", !!detalle.aleatorio);
      aleatorio.setAttribute("aria-pressed", String(!!detalle.aleatorio));
    }
    if (repetir) {
      repetir.classList.toggle("activo", !!detalle.repetir);
      repetir.setAttribute("aria-pressed", String(!!detalle.repetir));
    }
  }

  function pintarSiguen() {
    const reproductor = player();
    el.siguen.replaceChildren();
    if (!reproductor) return;
    const { pistas, indice } = reproductor.estado;
    const proximas = [];
    for (let paso = 1; paso <= 3 && paso < pistas.length; paso += 1) {
      proximas.push({ pista: pistas[(indice + paso) % pistas.length], indice: (indice + paso) % pistas.length });
    }
    el.siguen.parentElement.hidden = !proximas.length;
    proximas.forEach((item) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "kl-ahora__sigue";
      boton.addEventListener("click", () => reproductor.cargar(item.indice));
      const img = document.createElement("img");
      img.alt = "";
      img.width = 44;
      img.height = 44;
      img.loading = "lazy";
      if (item.pista.portada) img.src = item.pista.portada;
      const texto = document.createElement("span");
      const titulo = document.createElement("strong");
      titulo.textContent = item.pista.titulo;
      const artista = document.createElement("small");
      artista.textContent = item.pista.artista;
      texto.append(titulo, artista);
      boton.append(img, texto);
      el.siguen.appendChild(boton);
    });
  }

  // -----------------------------------------------------------------------
  // Modo letra: la portada se achica hasta ser la etiqueta del disco, el disco
  // queda solo al costado y la letra ocupa el resto de la pantalla. Cada verso
  // nuevo sale del disco como una onda en el fondo vivo.
  // -----------------------------------------------------------------------
  function ondaDesdeElDisco(fuerza) {
    if (!window.KLAmbiente || !el.disco) return;
    const rect = el.disco.getBoundingClientRect();
    if (!rect.width) return;
    window.KLAmbiente.onda(
      (rect.left + rect.width / 2) / window.innerWidth,
      (rect.top + rect.height / 2) / window.innerHeight,
      fuerza
    );
  }

  const karaoke = window.KLKaraoke
    ? new window.KLKaraoke(el.letra, {
        alTocar: (segundos) => {
          const a = audio();
          if (a && segundos >= 0 && (!a.duration || segundos < a.duration)) a.currentTime = segundos;
        },
        alCambiar: () => { if (volteada && sonando && !reduce) ondaDesdeElDisco(0.9); },
        alAvanzar: (avance) => { if (el.disco) el.disco.style.setProperty("--verso", avance.toFixed(3)); },
        // La letra sale del disco: su centro es el punto de fuga del túnel.
        origen: () => (el.disco ? el.disco.getBoundingClientRect() : null),
      })
    : null;
  let pedidoLetra = 0;

  function cargarLetra() {
    if (!karaoke) return;
    const actual = ++pedidoLetra;
    // Vale el último pedido aunque la letra se haya cerrado mientras cargaba:
    // si no, al volver quedaría para siempre en "Buscando la letra…".
    window.KLMontarLetra(karaoke, pista, () => actual === pedidoLetra);
  }

  // "volteada" = modo letra activo (antes la portada se daba vuelta).
  function voltear(valor) {
    volteada = typeof valor === "boolean" ? valor : !volteada;
    panel.classList.toggle("modo-letra", volteada);
    if (el.letras) el.letras.setAttribute("aria-hidden", String(!volteada));
    el.frente.setAttribute("aria-label", volteada ? "Volver a la portada" : "Ver la letra");
    panel.querySelectorAll(".kl-ahora__letra-btn").forEach((b) => b.setAttribute("aria-pressed", String(volteada)));
    if (el.disco) el.disco.style.setProperty("--verso", "0");
    if (karaoke) karaoke.mostrarse(volteada && abierto);
    if (volteada && el.letra.dataset.pista !== String(pista && pista.id)) {
      el.letra.dataset.pista = String(pista && pista.id);
      cargarLetra();
    }
  }

  // -----------------------------------------------------------------------
  // Portada viva: inclinación con el puntero, respiración con los graves
  // -----------------------------------------------------------------------
  const tilt = { x: 0, y: 0, ox: 0, oy: 0, arrastre: 0 };

  el.frente.addEventListener("pointermove", (evento) => {
    if (evento.pointerType === "touch") return;
    const rect = el.frente.getBoundingClientRect();
    tilt.ox = ((evento.clientX - rect.left) / rect.width - 0.5) * 2;
    tilt.oy = ((evento.clientY - rect.top) / rect.height - 0.5) * 2;
  });
  el.frente.addEventListener("pointerleave", () => {
    tilt.ox = 0;
    tilt.oy = 0;
  });

  // Deslizar la portada a los costados cambia de tema; un toque la da vuelta.
  let gesto = null;
  el.frente.addEventListener("pointerdown", (evento) => {
    gesto = { x: evento.clientX, y: evento.clientY, t: performance.now(), id: evento.pointerId };
  });
  el.frente.addEventListener("pointermove", (evento) => {
    if (!gesto || evento.pointerId !== gesto.id) return;
    const dx = evento.clientX - gesto.x;
    if (Math.abs(dx) > 8) tilt.arrastre = dx;
  });
  function soltarGesto(evento) {
    if (!gesto || evento.pointerId !== gesto.id) return;
    const dx = evento.clientX - gesto.x;
    const dy = evento.clientY - gesto.y;
    gesto = null;
    tilt.arrastre = 0;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy)) {
      el.frente.dataset.deslizo = "1";
      const reproductor = player();
      if (!reproductor) return;
      el.tarjeta.classList.remove("sale-izq", "sale-der");
      void el.tarjeta.offsetWidth;
      el.tarjeta.classList.add(dx < 0 ? "sale-izq" : "sale-der");
      if (dx < 0) reproductor.siguiente();
      else reproductor.anterior();
    }
  }
  el.frente.addEventListener("pointerup", soltarGesto);
  el.frente.addEventListener("pointercancel", () => { gesto = null; tilt.arrastre = 0; });
  el.tarjeta.addEventListener("animationend", () => el.tarjeta.classList.remove("sale-izq", "sale-der"));

  el.frente.addEventListener("click", () => {
    if (el.frente.dataset.deslizo) {
      delete el.frente.dataset.deslizo;
      return;
    }
    voltear();
  });

  // -----------------------------------------------------------------------
  // Espectro circular alrededor de la barra y bucle de animación
  // -----------------------------------------------------------------------
  const ctx = el.espectro ? el.espectro.getContext("2d") : null;
  // El tamaño se mide cuando cambia, no en cada cuadro (leerlo forzaba un layout).
  const medida = { ancho: 0, alto: 0 };
  if (el.espectro && "ResizeObserver" in window) {
    new ResizeObserver((entradas) => {
      medida.ancho = entradas[0].contentRect.width;
      medida.alto = entradas[0].contentRect.height;
    }).observe(el.espectro);
  }

  function dibujarEspectro() {
    if (!ctx) return;
    const ancho = medida.ancho || el.espectro.clientWidth;
    const alto = medida.alto || el.espectro.clientHeight;
    if (!ancho || !alto) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (el.espectro.width !== Math.floor(ancho * dpr)) {
      el.espectro.width = Math.floor(ancho * dpr);
      el.espectro.height = Math.floor(alto * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, ancho, alto);
    const puente = window.KLAudio;
    const a = audio();
    const progreso = a && a.duration ? a.currentTime / a.duration : 0;
    const barras = Math.max(24, Math.floor(ancho / 6));
    const color = window.KL.util.rgb("--kl-c1");
    for (let i = 0; i < barras; i += 1) {
      let valor = 0.12 + Math.abs(Math.sin(i * 0.9)) * 0.1;
      if (puente && sonando) valor = Math.max(0.08, puente.bins[Math.floor((i / barras) * 90)] / 255);
      const h = Math.max(2, valor * alto);
      const x = (i / barras) * ancho;
      const pasada = i / barras <= progreso;
      ctx.fillStyle = pasada ? `rgba(${color}, .95)` : "rgba(255, 255, 255, .22)";
      ctx.fillRect(x, (alto - h) / 2, Math.max(2, ancho / barras - 2.5), h);
    }
  }

  let giroDisco = 0;

  // Suscripto al reloj común mientras la hoja está abierta.
  function marco(dt) {
    if (!abierto) return false;
    tilt.x += (tilt.ox - tilt.x) * 0.12;
    tilt.y += (tilt.oy - tilt.y) * 0.12;
    const bajo = sonando ? window.KL.nivel.bass : 0;
    const estilo = el.tarjeta.style;
    estilo.setProperty("--tx", (tilt.x * 9).toFixed(2) + "deg");
    estilo.setProperty("--ty", (-tilt.y * 9).toFixed(2) + "deg");
    estilo.setProperty("--gx", (50 + tilt.x * 40).toFixed(1) + "%");
    estilo.setProperty("--gy", (50 + tilt.y * 40).toFixed(1) + "%");
    estilo.setProperty("--arrastre", (tilt.arrastre * 0.6).toFixed(1) + "px");
    estilo.setProperty("--latido", reduce ? "1" : (1 + bajo * 0.045).toFixed(4));
    // La velocidad común de los discos y un empujón con cada golpe de bajo.
    const velocidad = window.KL.GRADOS_POR_SEGUNDO || 90;
    if (sonando && !reduce) giroDisco = (giroDisco + dt * velocidad * (1 + bajo * 1.2)) % 360;
    if (el.giro) el.giro.style.transform = `rotate(${giroDisco.toFixed(2)}deg)`;
    dibujarEspectro();
    return true;
  }

  // -----------------------------------------------------------------------
  // Progreso
  // -----------------------------------------------------------------------
  function sincronizarProgreso() {
    const a = audio();
    if (!a || !abierto) return;
    const duracion = a.duration || (pista && pista.duracion) || 0;
    if (!arrastrandoBarra && duracion) el.barra.value = String(Math.round((a.currentTime / duracion) * 1000));
    el.actual.textContent = formatear(a.currentTime);
    el.total.textContent = formatear(duracion);
    el.barra.setAttribute("aria-valuetext", `${formatear(a.currentTime)} de ${formatear(duracion)}`);
    el.barra.style.setProperty("--avance", `${(Number(el.barra.value) / 10).toFixed(1)}%`);
  }

  el.barra.addEventListener("pointerdown", () => { arrastrandoBarra = true; });
  window.addEventListener("pointerup", () => { arrastrandoBarra = false; });
  el.barra.addEventListener("input", () => {
    const a = audio();
    if (a && a.duration) a.currentTime = (Number(el.barra.value) / 1000) * a.duration;
    el.barra.style.setProperty("--avance", `${(Number(el.barra.value) / 10).toFixed(1)}%`);
  });

  // -----------------------------------------------------------------------
  // Abrir y cerrar: la hoja sube y la portada vuela desde donde se tocó
  // -----------------------------------------------------------------------
  function volar(desde, hacia, radioFinal, alTerminar) {
    if (reduce || !desde || !hacia || !pista || !pista.portada || !desde.width) {
      if (alTerminar) alTerminar();
      return;
    }
    const clon = document.createElement("img");
    clon.src = pista.portada;
    clon.alt = "";
    clon.className = "kl-ahora__vuelo";
    Object.assign(clon.style, {
      left: `${hacia.left}px`,
      top: `${hacia.top}px`,
      width: `${hacia.width}px`,
      height: `${hacia.height}px`,
    });
    document.body.appendChild(clon);
    const escala = desde.width / hacia.width;
    const dx = desde.left - hacia.left;
    const dy = desde.top - hacia.top;
    const animacion = clon.animate(
      [
        { transform: `translate(${dx}px, ${dy}px) scale(${escala})`, borderRadius: `${(radioFinal > 10 ? 6 : 22) / escala}px` },
        { transform: "translate(0, 0) scale(1)", borderRadius: `${radioFinal}px` },
      ],
      { duration: radioFinal > 10 ? 620 : 460, easing: "cubic-bezier(.2, .9, .15, 1)" }
    );
    animacion.onfinish = () => {
      clon.remove();
      if (alTerminar) alTerminar();
    };
  }

  function rectDe(nodo) {
    if (!nodo) return null;
    // Solo se vuela desde una portada de verdad, no desde un botón de texto.
    const img = nodo.matches("img") ? nodo : nodo.querySelector("img");
    if (!img) return null;
    const rect = img.getBoundingClientRect();
    return rect.width > 4 ? rect : null;
  }

  function abrir(disparador) {
    if (abierto) return;
    abierto = true;
    ultimoFoco = document.activeElement;
    origenRect = rectDe(disparador);
    document.querySelectorAll(".offcanvas.show").forEach((nodo) => {
      const instancia = window.bootstrap && window.bootstrap.Offcanvas.getInstance(nodo);
      if (instancia) instancia.hide();
    });
    const a = audio();
    if (a && !a.getAttribute("src")) {
      const radio = document.querySelector("[data-radio]");
      if (radio) radio.click();
    }
    pintar();
    pintarSiguen();
    voltear(false);
    panel.hidden = false;
    document.body.classList.add("kl-estudio-abierto");
    document.dispatchEvent(new CustomEvent("kl:ahora", { detail: { abierto: true } }));
    const shell = document.querySelector(".kl-shell");
    if (shell) shell.inert = true;
    const barra = document.getElementById("kl-player");
    if (barra) barra.inert = true;

    // La portada se mide ya en su lugar final (la hoja arranca corrida una pantalla).
    panel.classList.remove("saliendo");
    panel.classList.add("entrando");
    const final = el.portada.hidden ? null : el.portada.getBoundingClientRect();
    const destino = final ? new DOMRect(final.left, final.top - hoja.offsetHeight, final.width, final.height) : null;
    if (destino && origenRect) el.tarjeta.classList.add("en-vuelo");
    requestAnimationFrame(() => {
      panel.classList.remove("entrando");
      panel.classList.add("abierto");
      if (destino && origenRect) {
        volar(origenRect, destino, 22, () => el.tarjeta.classList.remove("en-vuelo"));
      } else {
        el.tarjeta.classList.remove("en-vuelo");
      }
    });
    sincronizarProgreso();
    window.KL.reloj.agregar("ahora-suena", marco);
    const cerrar = panel.querySelector("[data-cerrar-estudio]");
    if (cerrar) cerrar.focus({ preventScroll: true });
  }

  function cerrar() {
    if (!abierto) return;
    abierto = false;
    if (karaoke) karaoke.mostrarse(false);
    const desde = el.portada.hidden ? null : el.portada.getBoundingClientRect();
    const destino = rectDe(document.getElementById("kl-player-portada")) || origenRect;
    panel.classList.remove("abierto");
    panel.classList.add("saliendo");
    if (desde && destino && !reduce) {
      el.tarjeta.classList.add("en-vuelo");
      volar(desde, destino, 6, null);
    }
    const terminar = () => {
      if (abierto) return;
      panel.hidden = true;
      panel.classList.remove("saliendo");
      el.tarjeta.classList.remove("en-vuelo");
    };
    if (reduce) terminar();
    else setTimeout(terminar, 460);
    document.body.classList.remove("kl-estudio-abierto");
    document.dispatchEvent(new CustomEvent("kl:ahora", { detail: { abierto: false } }));
    const shell = document.querySelector(".kl-shell");
    if (shell) shell.inert = false;
    const barra = document.getElementById("kl-player");
    if (barra) barra.inert = false;
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus({ preventScroll: true });
  }

  // Arrastrar la cabecera hacia abajo cierra la hoja (como en el celular).
  const agarre = panel.querySelector("[data-ahora-arrastre]");
  let tiron = null;
  if (agarre) {
    agarre.addEventListener("pointerdown", (evento) => {
      if (evento.target.closest("button")) return;
      tiron = { y: evento.clientY, id: evento.pointerId };
      agarre.setPointerCapture(evento.pointerId);
      hoja.classList.add("tirando");
    });
    agarre.addEventListener("pointermove", (evento) => {
      if (!tiron || evento.pointerId !== tiron.id) return;
      const dy = Math.max(0, evento.clientY - tiron.y);
      hoja.style.transform = `translateY(${dy}px)`;
    });
    const soltar = (evento) => {
      if (!tiron || evento.pointerId !== tiron.id) return;
      const dy = Math.max(0, evento.clientY - tiron.y);
      tiron = null;
      hoja.classList.remove("tirando");
      hoja.style.transform = "";
      if (dy > 120) cerrar();
    };
    agarre.addEventListener("pointerup", soltar);
    agarre.addEventListener("pointercancel", soltar);
  }

  // -----------------------------------------------------------------------
  // Eventos
  // -----------------------------------------------------------------------
  document.addEventListener("click", (evento) => {
    // El botón de letra (bandeja, escenario) abre la hoja directo en el modo letra.
    const letra = evento.target.closest("[data-abrir-letra]");
    if (letra) {
      evento.preventDefault();
      if (abierto && volteada) {
        cerrar();
      } else {
        if (!abierto) abrir(document.getElementById("kl-player-portada"));
        voltear(true);
        if (el.letra) el.letra.focus({ preventScroll: true });
      }
      return;
    }
    const abre = evento.target.closest("[data-abrir-estudio]");
    if (abre) {
      evento.preventDefault();
      if (abierto) cerrar();
      else abrir(abre);
      return;
    }
    // Tocar la portada flotante del tema que ya suena abre la vista grande desde ahí.
    const flota = evento.target.closest(".kl-flota.is-sonando");
    if (flota && !abierto) {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      abrir(flota);
      return;
    }
    if (!panel.contains(evento.target)) return;
    if (evento.target.closest("[data-cerrar-estudio]")) cerrar();
    if (evento.target.closest("[data-ahora-voltear]")) voltear();
    const reproductor = player();
    if (!reproductor) return;
    if (evento.target.closest("[data-estudio-play]")) reproductor.alternarPlay();
    if (evento.target.closest("[data-estudio-anterior]")) reproductor.anterior();
    if (evento.target.closest("[data-estudio-siguiente]")) reproductor.siguiente();
    if (evento.target.closest("[data-ahora-aleatorio]")) document.getElementById("kl-player-aleatorio").click();
    if (evento.target.closest("[data-ahora-repetir]")) document.getElementById("kl-player-repetir").click();
  }, true);

  // Stage: su botón de play está fuera de la hoja.
  document.addEventListener("click", (evento) => {
    const play = evento.target.closest(".kl-stage [data-estudio-play]");
    if (play && player()) player().alternarPlay();
  });

  document.addEventListener("keydown", (evento) => {
    if (evento.ctrlKey || evento.metaKey || evento.altKey) return;
    const sesion = document.getElementById("kl-sesion");
    if (sesion && !sesion.hidden) return;
    if (evento.key === "Escape" && abierto) {
      if (document.querySelector(".offcanvas.show")) return;
      cerrar();
      return;
    }
    const foco = document.activeElement || document.body;
    if (foco.closest("input, textarea, select, [contenteditable]")) return;
    if (evento.key === "e" || evento.key === "E") {
      if (abierto) cerrar();
      else abrir(document.getElementById("kl-player-portada"));
    }
    if (!abierto) return;
    if (evento.key === "l" || evento.key === "L") voltear();
    if (evento.code === "Space" && !foco.closest("button, a")) {
      evento.preventDefault();
      if (player()) player().alternarPlay();
    }
    // Con la hoja abierta, los atajos de la bandeja no corren (ver reproductor.js): el silencio va acá.
    if ((evento.key === "m" || evento.key === "M") && player()) player().alternarSilencio();
    if (evento.key === "ArrowRight" && !foco.closest("input") && player()) player().siguiente();
    if (evento.key === "ArrowLeft" && !foco.closest("input") && player()) player().anterior();
  });

  // Foco atrapado dentro de la hoja mientras está abierta.
  panel.addEventListener("keydown", (evento) => {
    if (evento.key !== "Tab") return;
    const focos = Array.from(panel.querySelectorAll("button, a[href], input, [tabindex]:not([tabindex='-1'])"))
      .filter((n) => !n.hidden && n.offsetParent !== null && n.tabIndex !== -1 && !n.closest("[aria-hidden=true]"));
    if (!focos.length) return;
    const primero = focos[0];
    const ultimo = focos[focos.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  });

  document.addEventListener("kl:reproductor", (evento) => {
    const detalle = evento.detail || {};
    const cambio = detalle.pista && (!pista || String(detalle.pista.id) !== String(pista.id));
    sonando = !!detalle.sonando;
    if (detalle.pista) pista = detalle.pista;
    pintar();
    pintarModos(detalle);
    if (cambio) {
      pintarSiguen();
      el.letra.dataset.pista = "";
      if (volteada) voltear(true);
    }
  });

  const a = audio();
  if (a) {
    a.addEventListener("timeupdate", sincronizarProgreso);
    a.addEventListener("loadedmetadata", sincronizarProgreso);
  }
})();

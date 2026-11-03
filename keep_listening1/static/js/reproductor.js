/* ===========================================================================
 * Keep Listening - reproductor de musica (caso de uso 3)
 * Cola dinamica, persistencia de estado, registro de reproducciones y favoritos.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL || {};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  const audio = $("#kl-audio");
  const barraPlayer = $("#kl-player");
  if (!audio || !barraPlayer) return;

  const elementos = {
    portada: $("#kl-player-portada"),
    titulo: $("#kl-player-titulo"),
    artista: $("#kl-player-artista"),
    play: $("#kl-player-play"),
    anterior: $("#kl-player-anterior"),
    siguiente: $("#kl-player-siguiente"),
    aleatorio: $("#kl-player-aleatorio"),
    repetir: $("#kl-player-repetir"),
    barra: $("#kl-player-barra"),
    actual: $("#kl-player-actual"),
    total: $("#kl-player-total"),
    volumen: $("#kl-player-volumen"),
    silencio: $("#kl-player-silencio"),
    favorito: $("#kl-player-fav"),
    cola: $("#kl-cola-lista"),
  };

  // La cola llega en un <script type="application/json"> generado por
  // json_script, no como HTML interpolado.
  function pistasIniciales() {
    const datos = KL.util.json("kl-pistas", []);
    return Array.isArray(datos) ? datos : [];
  }

  const estado = {
    pistas: pistasIniciales(),
    indice: -1,
    aleatorio: false,
    repetir: false,
    duracionEnviada: new Set(),
  };

  // Quita duplicados manteniendo el orden de aparicion.
  estado.pistas = estado.pistas.filter(
    (pista, posicion, lista) => pista && lista.findIndex((otra) => otra.id === pista.id) === posicion
  );

  // ---------------------------------------------------------------------
  // Persistencia del volumen (memoria de sesion en variable + sessionStorage
  // no disponible en algunos entornos: se usa solo memoria y atributo)
  // ---------------------------------------------------------------------
  audio.volume = 0.8;
  try {
    const guardado = sessionStorage.getItem("kl-volumen");
    if (guardado !== null && isFinite(Number(guardado))) {
      audio.volume = Number(guardado);
      if (elementos.volumen) elementos.volumen.value = String(audio.volume);
    }
  } catch (error) {
    /* sessionStorage puede estar bloqueado: el volumen queda en 0.8 */
  }
  // El último volumen que se oía: quitar el silencio con la barra en 0 vuelve ahí.
  let volumenAudible = audio.volume > 0 ? audio.volume : 0.8;

  function asegurarAnalizador() {
    if (window.KLAudio) {
      if (window.KLAudio.ctx.state === "suspended") window.KLAudio.ctx.resume();
      return;
    }
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const fuente = ctx.createMediaElementSource(audio);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    fuente.connect(analyser);
    analyser.connect(ctx.destination);
    window.KLAudio = { ctx, analyser, bins: new Uint8Array(analyser.frequencyBinCount) };
  }

  function emitir() {
    const pista = estado.pistas[estado.indice] || null;
    const sonando = !!audio.src && !audio.paused;
    elementos.play.setAttribute("aria-label", sonando ? "Pausar" : "Reproducir");
    document.dispatchEvent(new CustomEvent("kl:reproductor", {
      detail: {
        sonando,
        pista,
        indice: estado.indice,
        aleatorio: estado.aleatorio,
        repetir: estado.repetir,
      },
    }));
  }

  function reproducirSeguro() {
    const promesa = audio.play();
    if (promesa && promesa.catch) {
      promesa.catch(() => avisar("Tu navegador bloqueó la reproducción. Tocá play de nuevo.", "warning"));
    }
  }

  // ---------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------
  // Utilidades compartidas (static/js/nucleo.js).
  const { escapar, formatear } = KL.util;
  const csrf = () => KL.util.csrf();

  function avisar(mensaje, tipo) {
    if (typeof window.klAviso === "function") window.klAviso(mensaje, tipo);
  }

  function marcarAleatorio(valor) {
    estado.aleatorio = valor;
    elementos.aleatorio.classList.toggle("activo", valor);
    elementos.aleatorio.setAttribute("aria-pressed", String(valor));
  }

  function pistaPorId(id) {
    return estado.pistas.find((pista) => String(pista.id) === String(id));
  }

  // ---------------------------------------------------------------------
  // Reproduccion
  // ---------------------------------------------------------------------
  let turno = 0;
  let cambiando = false;

  function cargar(indice, reproducir = true) {
    const pista = estado.pistas[indice];
    if (!pista || !pista.audio) return;
    // Escuchar es con cuenta: sin sesión se pide entrar y el tema arranca después.
    if (reproducir && !KL.autenticado) {
      if (window.KLSesion) window.KLSesion.pedir(pista, () => cargar(indice, true));
      else window.location.href = KL.urls.login;
      return;
    }
    const mio = ++turno;
    cambiando = true;
    rampaActiva += 1;
    barraPlayer.classList.remove("frenando");
    audio.playbackRate = 1;
    conservarTono(true);
    estado.indice = indice;
    audio.pause();
    audio.src = pista.audio;
    const externa = !KL.util.esLocal(pista.id);
    elementos.portada.src = pista.portada;
    elementos.portada.alt = `Portada de ${pista.titulo}`;
    elementos.titulo.textContent = pista.titulo;
    const etiqueta = pista.compra ? "Muestra" : "Adelanto";
    elementos.artista.textContent = externa ? `${pista.artista} · ${etiqueta}` : pista.artista;
    elementos.total.textContent = formatear(pista.duracion);
    barraPlayer.classList.add("activo");

    marcarSonando(pista.id);
    sincronizarFavorito(pista.id);
    pintarCola();

    emitir();
    if (!reproducir) {
      cambiando = false;
      return;
    }
    asegurarAnalizador();
    const promesa = audio.play();
    if (promesa && promesa.then) {
      promesa.then(() => {
        if (mio !== turno) audio.pause();
        else cambiando = false;
      }).catch(() => {
        if (mio === turno) {
          cambiando = false;
          avisar("Tu navegador bloqueo la reproduccion automatica.", "warning");
        }
      });
    } else {
      cambiando = false;
    }
    registrarReproduccion(pista.id);
  }

  // Arranque y frenado de tocadiscos: al pausar, la velocidad (y con ella el
  // tono) baja hasta frenar; al reanudar, sube. El disco de la bandeja gira a
  // la velocidad real del audio, así que se ve frenar y arrancar también.
  const TONO = ["preservesPitch", "mozPreservesPitch", "webkitPreservesPitch"];
  function conservarTono(valor) {
    TONO.forEach((clave) => { if (clave in audio) audio[clave] = valor; });
  }

  let rampaActiva = 0;
  function rampaVelocidad(desde, hasta, ms, alTerminar) {
    const mia = ++rampaActiva;
    // Con la pestaña oculta no hay cuadros de animación: la rampa no avanzaría
    // y la pausa nunca llegaría. Se aplica al instante.
    if (KL.util.reduce || !KL.reloj || document.hidden) {
      audio.playbackRate = 1;
      if (alTerminar) alTerminar();
      return;
    }
    let terminada = false;
    const terminar = () => {
      if (terminada) return;
      terminada = true;
      clearTimeout(respaldo);
      conservarTono(true);
      if (alTerminar) alTerminar();
    };
    // Si los cuadros se frenan a mitad de camino (se ocultó la pestaña), termina igual.
    const respaldo = setTimeout(() => { if (mia === rampaActiva) terminar(); }, ms + 250);
    conservarTono(false);
    const inicio = performance.now();
    audio.playbackRate = desde;
    KL.reloj.agregar("rampa-tocadiscos", (dt, ahora) => {
      if (mia !== rampaActiva || terminada) return false;
      const p = Math.min(1, (ahora - inicio) / ms);
      // Frenar decae rápido al principio; arrancar acelera como un plato con peso.
      const curva = hasta < desde ? 1 - Math.pow(1 - p, 2) : p * p * (3 - 2 * p);
      audio.playbackRate = Math.max(0.07, desde + (hasta - desde) * curva);
      if (p < 1) return true;
      terminar();
      return false;
    });
  }

  function alternarPlay() {
    if (!audio.src) {
      if (estado.pistas.length) cargar(0);
      return;
    }
    if (audio.paused) {
      // Reanudar en medio de un frenado: la rampa nueva lo cancela, y la clase también.
      barraPlayer.classList.remove("frenando");
      asegurarAnalizador();
      audio.playbackRate = 0.35;
      reproducirSeguro();
      rampaVelocidad(0.35, 1, 450);
    } else {
      barraPlayer.classList.add("frenando");
      rampaVelocidad(audio.playbackRate || 1, 0.12, 560, () => {
        audio.pause();
        audio.playbackRate = 1;
        barraPlayer.classList.remove("frenando");
      });
    }
  }

  function siguiente(automatico = false) {
    if (!estado.pistas.length) return;
    if (estado.repetir && automatico) {
      audio.currentTime = 0;
      reproducirSeguro();
      return;
    }
    let proximo;
    if (estado.aleatorio) {
      do {
        proximo = Math.floor(Math.random() * estado.pistas.length);
      } while (estado.pistas.length > 1 && proximo === estado.indice);
    } else {
      proximo = estado.indice + 1;
      if (proximo >= estado.pistas.length) proximo = 0;
    }
    cargar(proximo);
  }

  function anterior() {
    if (!estado.pistas.length) return;
    if (audio.currentTime > 4) {
      audio.currentTime = 0;
      return;
    }
    const previo = estado.indice - 1 < 0 ? estado.pistas.length - 1 : estado.indice - 1;
    cargar(previo);
  }

  // ---------------------------------------------------------------------
  // Estado visual
  // ---------------------------------------------------------------------
  function marcarSonando(id) {
    $$("[data-tema]").forEach((nodo) => {
      nodo.classList.toggle("sonando", String(nodo.dataset.tema) === String(id));
    });
  }

  // Temas de Apple con me gusta (los ids llegan en #kl-me-gusta-ids).
  let meGusta = new Set();
  function leerMeGusta() {
    const ids = KL.util.json("kl-me-gusta-ids", []);
    meGusta = new Set((Array.isArray(ids) ? ids : []).map(String));
  }
  leerMeGusta();

  function pintarCorazon(boton, guardada) {
    boton.classList.toggle("guardada", guardada);
    boton.setAttribute("aria-pressed", String(guardada));
    boton.setAttribute("aria-label", guardada ? "Quitar de me gusta" : "Me gusta");
    const icono = boton.querySelector("i");
    if (icono) icono.className = `bi ${guardada ? "bi-heart-fill" : "bi-heart"}`;
  }

  // El botón trae d-sm-grid (con !important): para ocultarlo hace falta otro !important.
  function mostrarCorazon(visible) {
    if (visible) elementos.favorito.style.removeProperty("display");
    else elementos.favorito.style.setProperty("display", "none", "important");
  }

  function sincronizarFavorito(id) {
    if (!elementos.favorito) return;
    // Lo comprado ya es tuyo: sus temas no se marcan con el corazón.
    const tema = pistaPorId(id);
    if (tema && tema.compra) {
      mostrarCorazon(false);
      return;
    }
    const local = KL.util.esLocal(id);
    // Los temas propios usan el favorito de siempre (app.js); los de Apple, "me gusta".
    if (local) {
      const boton = document.querySelector(`[data-favorito="${id}"]:not(#kl-player-fav)`);
      elementos.favorito.dataset.favorito = id;
      delete elementos.favorito.dataset.meGusta;
      pintarCorazon(elementos.favorito, boton ? boton.classList.contains("guardada") : false);
    } else {
      delete elementos.favorito.dataset.favorito;
      elementos.favorito.dataset.meGusta = id;
      pintarCorazon(elementos.favorito, meGusta.has(String(id)));
    }
    mostrarCorazon(KL.autenticado);
  }

  async function alternarMeGusta(id) {
    const pista = pistaPorId(id) || externas.get(String(id));
    if (!pista) return;
    const cuerpo = new FormData();
    ["id", "titulo", "artista", "portada", "audio", "url", "duracion", "genero"].forEach((campo) => {
      cuerpo.append(campo, pista[campo] == null ? "" : pista[campo]);
    });
    let datos = {};
    try {
      const respuesta = await fetch(KL.urls.meGusta, {
        method: "POST",
        headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
        body: cuerpo,
      });
      datos = await respuesta.json();
      if (!respuesta.ok || !datos.ok) throw new Error(datos.mensaje || "error");
    } catch (error) {
      avisar(datos.mensaje || "No pudimos guardar el me gusta.", "danger");
      return;
    }
    if (datos.guardada) meGusta.add(String(id));
    else meGusta.delete(String(id));
    document.querySelectorAll(`[data-me-gusta="${CSS.escape(String(id))}"]`).forEach((boton) => pintarCorazon(boton, datos.guardada));
    document.dispatchEvent(new CustomEvent("kl:me-gusta", { detail: { id, guardada: datos.guardada, pista } }));
    avisar(datos.mensaje, datos.guardada ? "success" : "info");
  }

  document.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-me-gusta]");
    if (!boton) return;
    evento.preventDefault();
    if (!KL.autenticado) {
      const pista = pistaPorId(boton.dataset.meGusta) || externas.get(String(boton.dataset.meGusta));
      if (window.KLSesion) window.KLSesion.pedir(pista, () => alternarMeGusta(boton.dataset.meGusta));
      return;
    }
    alternarMeGusta(boton.dataset.meGusta);
  });

  // Después de entrar desde el panel de sesión: se recargan los me gusta de la cuenta.
  document.addEventListener("kl:sesion", () => {
    leerMeGusta();
    const pista = estado.pistas[estado.indice];
    if (pista) sincronizarFavorito(pista.id);
  });

  function pintarCola() {
    if (!elementos.cola) return;
    if (!estado.pistas.length) {
      elementos.cola.innerHTML = '<p class="kl-texto-claro">La cola esta vacia.</p>';
      return;
    }
    elementos.cola.innerHTML = estado.pistas
      .map(
        (pista, posicion) => `
        <button type="button" class="kl-offcanvas__link kl-cola__item" data-cola-indice="${posicion}"
                ${posicion === estado.indice ? 'aria-current="true"' : ""}>
          <img src="${escapar(pista.portada)}" alt="" width="36" height="36" loading="lazy">
          <span class="kl-cola__texto">
            <strong>${escapar(pista.titulo)}</strong>
            <small>${escapar(pista.artista)}</small>
          </span>
          ${posicion === estado.indice ? '<span class="kl-ecualizador ms-auto" aria-hidden="true"><span></span><span></span><span></span><span></span></span>' : ""}
        </button>`
      )
      .join("");


  }

  // ---------------------------------------------------------------------
  // Comunicacion con el servidor
  // ---------------------------------------------------------------------
  // Tocar un tema de la cola (un listener para toda la lista).
  if (elementos.cola) {
    elementos.cola.addEventListener("click", (evento) => {
      const boton = evento.target.closest("[data-cola-indice]");
      if (boton) cargar(Number(boton.dataset.colaIndice));
    });
  }

  function registrarReproduccion(id) {
    if (!KL.util.esLocal(id)) return;
    fetch(`${KL.urls.reproducir}${id}/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
    }).catch(() => {});
  }

  function informarDuracion(id, segundos) {
    if (!KL.util.esLocal(id)) return;
    if (!KL.autenticado || estado.duracionEnviada.has(id) || !isFinite(segundos)) return;
    estado.duracionEnviada.add(id);
    const cuerpo = new FormData();
    cuerpo.append("duracion", Math.round(segundos));
    fetch(`${KL.urls.duracion}${id}/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
      body: cuerpo,
    }).catch(() => {});
  }

  let pedidoCola = 0;
  async function cargarCola(parametros, idPreferido) {
    const mio = (pedidoCola += 1);
    let datos;
    try {
      const respuesta = await fetch(`${KL.urls.cola}?${parametros}`, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!respuesta.ok) throw new Error(String(respuesta.status));
      datos = await respuesta.json();
    } catch (error) {
      avisar("No pudimos cargar la cola de reproducción.", "danger");
      return;
    }
    if (mio !== pedidoCola) return;
    if (!datos.pistas || !datos.pistas.length) {
      avisar("No encontramos ese tema.", "warning");
      return;
    }
    let indice = 0;
    if (idPreferido != null) {
      indice = datos.pistas.findIndex((pista) => String(pista.id) === String(idPreferido));
      // Si el tema pedido no vino, no se pone otro en su lugar.
      if (indice < 0) {
        avisar("Ese tema no está disponible para escuchar.", "warning");
        return;
      }
    }
    estado.pistas = datos.pistas;
    cargar(indice);
  }

  // ---------------------------------------------------------------------
  // Eventos del audio
  // ---------------------------------------------------------------------
  // Mientras el usuario arrastra la barra, el audio no se la pisa.
  let arrastrando = false;
  audio.addEventListener("timeupdate", () => {
    if (!audio.duration) return;
    if (!arrastrando) elementos.barra.value = (audio.currentTime / audio.duration) * 100;
    elementos.actual.textContent = formatear(audio.currentTime);
    elementos.barra.setAttribute(
      "aria-valuetext", `${formatear(audio.currentTime)} de ${formatear(audio.duration)}`
    );
  });

  audio.addEventListener("loadedmetadata", () => {
    elementos.total.textContent = formatear(audio.duration);
    const pista = estado.pistas[estado.indice];
    if (pista && !pista.duracion) informarDuracion(pista.id, audio.duration);
  });

  audio.addEventListener("play", () => {
    asegurarAnalizador();
    barraPlayer.classList.add("reproduciendo");
    elementos.play.querySelector("i").className = "bi bi-pause-fill";
    emitir();
  });

  audio.addEventListener("pause", () => {
    barraPlayer.classList.remove("reproduciendo");
    elementos.play.querySelector("i").className = "bi bi-play-fill";
    emitir();
  });

  audio.addEventListener("ended", () => {
    if (cambiando) return;
    const pista = estado.pistas[estado.indice];
    const externa = pista && !KL.util.esLocal(pista.id);
    const ultima = estado.indice + 1 >= estado.pistas.length;
    if (externa && ultima && !estado.repetir) {
      avisar("Se terminó el adelanto. Abrí la portada en grande para ir a la canción completa.", "info");
      emitir();
      return;
    }
    siguiente(true);
  });

  audio.addEventListener("error", () => {
    if (cambiando || !audio.getAttribute("src")) return;
    avisar("No pudimos reproducir el archivo de audio.", "danger");
  });

  // ---------------------------------------------------------------------
  // Controles
  // ---------------------------------------------------------------------
  elementos.play.addEventListener("click", alternarPlay);
  elementos.siguiente.addEventListener("click", () => siguiente());
  elementos.anterior.addEventListener("click", anterior);

  elementos.aleatorio.addEventListener("click", () => {
    marcarAleatorio(!estado.aleatorio);
    avisar(estado.aleatorio ? "Reproducción aleatoria activada" : "Reproducción en orden", "info");
    emitir();
  });

  elementos.repetir.addEventListener("click", () => {
    estado.repetir = !estado.repetir;
    elementos.repetir.classList.toggle("activo", estado.repetir);
    elementos.repetir.setAttribute("aria-pressed", String(estado.repetir));
    avisar(estado.repetir ? "Repetir canción activado" : "Repetir desactivado", "info");
    emitir();
  });

  elementos.barra.addEventListener("pointerdown", () => { arrastrando = true; });
  window.addEventListener("pointerup", () => { arrastrando = false; });
  elementos.barra.addEventListener("input", () => {
    if (audio.duration) audio.currentTime = (elementos.barra.value / 100) * audio.duration;
  });

  elementos.volumen.addEventListener("input", () => {
    audio.volume = Number(elementos.volumen.value);
    audio.muted = audio.volume === 0;
    if (audio.volume > 0) volumenAudible = audio.volume;
    try { sessionStorage.setItem("kl-volumen", String(audio.volume)); } catch (error) { /* sin almacenamiento */ }
    actualizarIconoVolumen();
  });

  // Un solo interruptor para el parlante y la tecla M.
  // Con la barra en 0 no alcanza con quitar el silencio: vuelve al último volumen que se oía.
  function alternarSilencio() {
    if (audio.volume === 0) {
      elementos.volumen.value = String(volumenAudible);
      elementos.volumen.dispatchEvent(new Event("input"));
      return;
    }
    audio.muted = !audio.muted;
    actualizarIconoVolumen();
  }

  elementos.silencio.addEventListener("click", alternarSilencio);

  function actualizarIconoVolumen() {
    const icono = elementos.silencio.querySelector("i");
    const mudo = audio.muted || audio.volume === 0;
    elementos.silencio.setAttribute("aria-pressed", String(mudo));
    elementos.silencio.setAttribute("aria-label", mudo ? "Quitar silencio" : "Silenciar");
    if (mudo) icono.className = "bi bi-volume-mute-fill";
    else if (audio.volume < 0.5) icono.className = "bi bi-volume-down-fill";
    else icono.className = "bi bi-volume-up-fill";
  }

  // ---------------------------------------------------------------------
  // Disparadores de la pagina
  // ---------------------------------------------------------------------
  document.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-reproducir]");
    if (!boton) return;
    evento.preventDefault();
    const id = boton.dataset.reproducir;
    let indice = estado.pistas.findIndex((pista) => String(pista.id) === String(id));

    if (indice === -1) {
      // Primero los temas de la página que se ve (así suena ese y no otro);
      // si no está ahí, se pide al servidor.
      const enPagina = pistasDePagina.findIndex((pista) => String(pista.id) === String(id));
      if (enPagina >= 0) {
        estado.pistas = pistasDePagina.slice();
        marcarAleatorio(false);
        cargar(enPagina);
        return;
      }
      cargarCola(`id=${encodeURIComponent(id)}`, id);
      return;
    }
    if (indice === estado.indice) {
      alternarPlay();
      return;
    }
    cargar(indice);
  });

  // Los temas de la página que se está viendo (json_script #kl-pistas). Es
  // distinto de la cola: navegar no cambia lo que suena.
  let pistasDePagina = estado.pistas.slice();

  const barajar = KL.util.barajar;

  function encenderLista(lista, aviso) {
    estado.pistas = barajar(lista.slice());
    marcarAleatorio(true);
    cargar(0);
    avisar(aviso, "success");
  }

  async function iniciarRadio() {
    if (ultimaLista.length) {
      encenderLista(ultimaLista, "Radio de adelantos encendida");
      return;
    }
    try {
      const respuesta = await fetch(KL.urls.cola, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      const datos = await respuesta.json();
      if (!datos.pistas || !datos.pistas.length) {
        avisar("La radio no tiene temas publicados.", "warning");
        return;
      }
      estado.pistas = barajar(datos.pistas);
      marcarAleatorio(true);
      cargar(0);
      avisar("Radio del catálogo encendida", "success");
    } catch (error) {
      avisar("No pudimos armar la radio.", "danger");
    }
  }

  const externas = new Map();
  let ultimaLista = [];

  function recordarExternas(lista) {
    (lista || []).forEach((pista) => {
      if (pista && pista.id != null) externas.set(String(pista.id), pista);
    });
  }

  function tomarLista(lista) {
    recordarExternas(lista);
    ultimaLista = (lista || []).filter((pista) => pista && pista.audio);
  }

  function encolarExterna(pista) {
    if (!pista) return;
    recordarExternas([pista]);
    if (!pista.audio) {
      if (pista.url) window.open(pista.url, "_blank", "noopener");
      avisar("Este tema no trae adelanto. Abrimos su ficha.", "info");
      return;
    }
    const cola = ultimaLista.length ? ultimaLista.slice() : [pista];
    const inicio = cola.findIndex((item) => String(item.id) === String(pista.id));
    estado.pistas = cola;
    marcarAleatorio(false);
    cargar(inicio >= 0 ? inicio : 0);
    const panel = document.getElementById("kl-buscador-resultados");
    if (panel) panel.classList.remove("visible");
  }

  // Botones de la página (delegados: siguen andando con la navegación continua).
  document.addEventListener("click", (evento) => {
    if (evento.target.closest("[data-reproducir-todo]")) {
      if (!pistasDePagina.length) {
        avisar("No hay canciones para reproducir.", "warning");
        return;
      }
      estado.pistas = pistasDePagina.slice();
      cargar(0);
    }

    // "Todo Hip hop": la cola es solo esa sección, en el orden en que se ve.
    const escena = evento.target.closest("[data-reproducir-escena]");
    if (escena) {
      const lista = (KL.util.json(escena.dataset.reproducirEscena, []) || []).filter((p) => p && p.audio);
      if (!lista.length) {
        avisar("Esta sección no tiene adelantos para reproducir.", "warning");
        return;
      }
      recordarExternas(lista);
      estado.pistas = lista;
      marcarAleatorio(false);
      cargar(0);
    }

    if (evento.target.closest("[data-reproducir-mapa]")) {
      if (!ultimaLista.length) {
        avisar("No hay adelantos para reproducir.", "warning");
        return;
      }
      estado.pistas = ultimaLista.slice();
      marcarAleatorio(false);
      cargar(0);
    }
  });

  // Al entrar a una página (la primera vez o por navegación continua) se leen
  // sus temas y su catálogo, sin tocar lo que está sonando.
  function leerPagina() {
    const propias = KL.util.json("kl-pistas", []);
    pistasDePagina = Array.isArray(propias) ? propias : [];
    if (!audio.getAttribute("src") && pistasDePagina.length) estado.pistas = pistasDePagina.slice();
    const catalogo = KL.util.json("kl-catalogo", null);
    if (Array.isArray(catalogo)) tomarLista(catalogo);
    const pista = estado.pistas[estado.indice];
    if (pista) {
      marcarSonando(pista.id);
      sincronizarFavorito(pista.id);
    }
  }
  leerPagina();
  document.addEventListener("kl:pagina", leerPagina);
  document.addEventListener("kl:catalogo", (evento) => tomarLista(evento.detail));

  document.addEventListener("click", (evento) => {
    const externo = evento.target.closest("[data-catalogo]");
    if (externo) {
      evento.preventDefault();
      // Una sección con data-lista arma su propia cola (Tus me gusta, Hip hop, Pop...).
      const seccion = externo.closest("[data-lista]");
      const nodoLista = seccion && document.getElementById(seccion.dataset.lista);
      if (nodoLista) {
        try { tomarLista(JSON.parse(nodoLista.textContent)); } catch (error) { /* se usa la cola anterior */ }
      }
      encolarExterna(externas.get(externo.dataset.catalogo));
      return;
    }
    if (evento.target.closest("[data-radio]")) iniciarRadio();
  });

  // Atajos de teclado: solo si el foco no está en algo que ya use esas teclas.
  document.addEventListener("keydown", (evento) => {
    if (evento.defaultPrevented || evento.ctrlKey || evento.metaKey || evento.altKey) return;
    const hoja = document.getElementById("kl-estudio");
    if (hoja && !hoja.hidden) return;
    const foco = document.activeElement || document.body;
    if (foco.closest("input, textarea, select, button, a, [contenteditable], [role=tab], .modal.show, .offcanvas.show")) {
      return;
    }
    if (evento.code === "Space") {
      evento.preventDefault();
      alternarPlay();
    }
    if (evento.code === "ArrowRight" && evento.shiftKey) siguiente();
    if (evento.code === "ArrowLeft" && evento.shiftKey) anterior();
    if (evento.key === "m" || evento.key === "M") alternarSilencio();
  });

  // La vista "Ahora suena" maneja el mismo reproductor desde otro lugar.
  // Pausa en el acto, sin el frenado del tocadiscos: para cuando otro audio
  // (el juego, la prueba de prensa, el corte) va a sonar.
  function pausar() {
    rampaActiva += 1;
    barraPlayer.classList.remove("frenando");
    audio.playbackRate = 1;
    conservarTono(true);
    if (!audio.paused) audio.pause();
  }

  window.KLPlayer = {
    audio,
    pausar,
    estado,
    cargar,
    alternarPlay,
    siguiente: () => siguiente(),
    anterior,
    formatear,
  };

  pintarCola();
})();

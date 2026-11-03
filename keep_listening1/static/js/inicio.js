/* ===========================================================================
 * Keep Listening - el inicio
 *
 * El disco del día: dar vuelta el disco cambia de lado (A hip hop, B pop), y
 * el botón de reproducir pone el lado que se ve.
 *
 * "Tres segundos": suena un pedacito de un tema con la tapa desenfocada y hay
 * que adivinar cuál es entre cuatro. Adivinar al primer intento vale 3 puntos;
 * con 3 segundos más, 1. La racha y el récord quedan en este navegador. Suena
 * con su propio <audio> (la bandeja se pausa) y, como todo, pide sesión.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL;

  // -------------------------------------------------------------------------
  // El disco del día
  // -------------------------------------------------------------------------
  const dia = document.getElementById("kl-dia");
  if (dia) {
    const vuelta = dia.querySelector("[data-dar-vuelta]");
    const play = document.getElementById("kl-dia-play");
    const lados = [...dia.querySelectorAll("[data-lado]")];
    if (vuelta && lados.length > 1) {
      vuelta.addEventListener("click", () => {
        const enB = !dia.classList.contains("lado-b");
        dia.classList.toggle("lado-b", enB);
        vuelta.setAttribute("aria-pressed", String(enB));
        const visible = lados[enB ? 1 : 0];
        lados.forEach((lado) => { lado.hidden = lado !== visible; });
        if (play) {
          play.dataset.reproducirEscena = visible.dataset.lista;
          play.querySelector("span").textContent = `Poner el lado ${visible.dataset.lado}`;
        }
      });
    }
  }

  // -------------------------------------------------------------------------
  // Tres segundos
  // -------------------------------------------------------------------------
  const juego = document.getElementById("kl-juego");
  if (!juego) return;

  KL.pagina(juego, (vida) => {
    const $ = KL.util.$;
    const el = {
      escuchar: $("kl-juego-escuchar"),
      tapa: $("kl-juego-tapa"),
      opciones: $("kl-juego-opciones"),
      estado: $("kl-juego-estado"),
      racha: $("kl-juego-racha"),
      mejor: $("kl-juego-mejor"),
      puntos: $("kl-juego-puntos"),
      mas: $("kl-juego-mas"),
      entero: $("kl-juego-entero"),
      otra: $("kl-juego-otra"),
    };
    const temas = (KL.util.json("kl-juego-datos", []) || []).filter((t) => t && t.audio && t.titulo);
    if (temas.length < 4) {
      juego.hidden = true;
      return;
    }

    const CORTE = 3;
    const audio = new Audio();
    audio.preload = "none";
    let ronda = null;
    let parar = 0;
    let alCargar = null; // el arranque pendiente de la ronda actual (si el audio todavía carga)
    const recientes = [];

    // El récord vive en este navegador; si el almacenamiento no anda, se juega igual.
    const guardado = KL.util.almacen.leer("kl-tres-segundos", {}) || {};
    const marcador = { racha: 0, mejor: Number(guardado.mejor) || 0, puntos: 0 };

    function guardar() {
      KL.util.almacen.guardar("kl-tres-segundos", { mejor: marcador.mejor });
    }

    function pintarMarcador() {
      el.racha.textContent = String(marcador.racha);
      el.mejor.textContent = String(marcador.mejor);
      el.puntos.textContent = String(marcador.puntos);
    }

    function azar(lista, cantidad, excepto) {
      return KL.util.barajar(lista.filter((t) => !excepto.includes(t))).slice(0, cantidad);
    }

    function detener() {
      clearTimeout(parar);
      // Un arranque que esperaba la carga ya no corre (si no, sonaba la ronda anterior).
      if (alCargar) audio.removeEventListener("loadedmetadata", alCargar);
      alCargar = null;
      audio.pause();
      juego.classList.remove("sonando");
    }

    function nuevaRonda() {
      detener();
      const candidatos = temas.filter((t) => !recientes.includes(t.id));
      const respuesta = azar(candidatos.length ? candidatos : temas, 1, [])[0];
      recientes.push(respuesta.id);
      if (recientes.length > Math.min(12, temas.length - 4)) recientes.shift();
      // Las otras tres opciones no repiten título (hay temas homónimos).
      const otras = azar(temas.filter((t) => t.titulo !== respuesta.titulo), 3, [respuesta]);
      const opciones = azar([respuesta, ...otras], 4, []);
      ronda = { respuesta, escuchado: 0, resuelta: false };

      el.tapa.src = respuesta.portada || "";
      juego.classList.remove("resuelta", "acierto", "error");
      el.mas.disabled = true;
      el.entero.hidden = true;
      el.estado.textContent = "Tocá el disco para escuchar.";
      el.opciones.replaceChildren(...opciones.map((tema) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "kl-juego__opcion";
        boton.dataset.id = String(tema.id);
        const titulo = document.createElement("strong");
        titulo.textContent = tema.titulo;
        const artista = document.createElement("small");
        artista.textContent = tema.artista;
        boton.append(titulo, artista);
        return boton;
      }));
    }

    function sonar(segundos) {
      if (!ronda) return;
      if (!KL.autenticado) {
        if (window.KLSesion) window.KLSesion.pedir(ronda.respuesta, () => sonar(segundos));
        return;
      }
      // La bandeja se pausa: no se pisan dos audios.
      if (window.KLPlayer) window.KLPlayer.pausar();
      const tema = ronda.respuesta;
      const arrancar = () => {
        // Un punto fijo por tema, lejos del arranque (suele ser silencio o intro).
        const inicio = Math.min(Math.max(4, (audio.duration || 30) * 0.4), (audio.duration || 30) - segundos - 0.5);
        audio.currentTime = Math.max(0, inicio);
        audio.play().then(() => {
          juego.classList.add("sonando");
          juego.style.setProperty("--dura", `${segundos}s`);
          clearTimeout(parar);
          parar = setTimeout(detener, segundos * 1000);
        }).catch(() => {
          el.estado.textContent = "No se pudo reproducir el adelanto. Probá con otra.";
        });
      };
      if (audio.dataset.id !== String(tema.id)) {
        if (alCargar) audio.removeEventListener("loadedmetadata", alCargar);
        alCargar = () => {
          alCargar = null;
          arrancar();
        };
        audio.dataset.id = String(tema.id);
        audio.src = tema.audio;
        audio.addEventListener("loadedmetadata", alCargar, { once: true });
        audio.load();
      } else {
        arrancar();
      }
      ronda.escuchado = Math.max(ronda.escuchado, segundos);
      if (!ronda.resuelta) {
        el.mas.disabled = segundos > CORTE;
        el.estado.textContent = segundos > CORTE ? "Seis segundos. Ahora sí." : "¿Qué tema es?";
      }
    }

    function responder(boton) {
      if (!ronda || ronda.resuelta) return;
      if (!ronda.escuchado) {
        el.estado.textContent = "Primero escuchalo: tocá el disco.";
        return;
      }
      ronda.resuelta = true;
      detener();
      const acierto = boton.dataset.id === String(ronda.respuesta.id);
      el.opciones.querySelectorAll(".kl-juego__opcion").forEach((opcion) => {
        opcion.disabled = true;
        if (opcion.dataset.id === String(ronda.respuesta.id)) opcion.classList.add("correcta");
      });
      if (!acierto) boton.classList.add("incorrecta");
      juego.classList.add("resuelta", acierto ? "acierto" : "error");
      if (acierto) {
        marcador.racha += 1;
        marcador.puntos += ronda.escuchado > CORTE ? 1 : 3;
        if (marcador.racha > marcador.mejor) {
          marcador.mejor = marcador.racha;
          guardar();
        }
        el.estado.textContent = `¡Sí! "${ronda.respuesta.titulo}" de ${ronda.respuesta.artista}.`;
      } else {
        marcador.racha = 0;
        el.estado.textContent = `Era "${ronda.respuesta.titulo}" de ${ronda.respuesta.artista}.`;
      }
      el.mas.disabled = true;
      el.entero.hidden = false;
      el.entero.dataset.catalogo = String(ronda.respuesta.id);
      pintarMarcador();
    }

    el.escuchar.addEventListener("click", () => sonar(ronda && ronda.escuchado > CORTE ? CORTE * 2 : CORTE));
    el.mas.addEventListener("click", () => sonar(CORTE * 2));
    el.otra.addEventListener("click", nuevaRonda);
    el.opciones.addEventListener("click", (evento) => {
      const boton = evento.target.closest(".kl-juego__opcion");
      if (boton) responder(boton);
    });
    // "Entero" usa data-catalogo: lo toma el reproductor con la cola del juego.
    el.entero.addEventListener("click", detener);

    // Al irse del inicio, el juego se calla y la descarga en curso se corta.
    vida.alSalir(() => {
      detener();
      audio.removeAttribute("src");
      audio.load();
    });

    pintarMarcador();
    nuevaRonda();
  });
})();

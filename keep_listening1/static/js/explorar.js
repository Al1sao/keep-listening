/* ===========================================================================
 * Keep Listening - el dial de Explorar
 *
 * Todo el catálogo es una banda de FM de 87.5 a 108 MHz (hip hop de un lado,
 * pop del otro). La aguja queda fija y la banda se mueve: se sintoniza
 * arrastrando la banda o la perilla, con la rueda o con las flechas. Entre dos
 * estaciones la pantalla se llena de estática; al soltar, la banda cae en la
 * estación más cercana. Con "Sintonía automática", parar en una estación la
 * pone a sonar (como todo, pide sesión).
 * =========================================================================== */
(function () {
  "use strict";

  const dial = document.getElementById("kl-dial");
  if (!dial) return;

  const KL = window.KL;
  const reduce = KL.util.reduce;
  const estaciones = (KL.util.json("kl-catalogo", []) || []).filter((t) => t && t.titulo);
  if (estaciones.length < 2) {
    dial.hidden = true;
    return;
  }

  KL.pagina(dial, (vida) => {
    const $ = KL.util.$;
    const el = {
      banda: $("kl-dial-banda"),
      escala: $("kl-dial-escala"),
      estatica: $("kl-dial-estatica"),
      tapa: $("kl-dial-tapa"),
      mhz: $("kl-dial-mhz"),
      genero: $("kl-dial-genero"),
      titulo: $("kl-dial-titulo"),
      artista: $("kl-dial-artista"),
      perilla: $("kl-dial-perilla"),
      play: $("kl-dial-play"),
      anterior: $("kl-dial-anterior"),
      siguiente: $("kl-dial-siguiente"),
      auto: $("kl-dial-auto"),
    };

    const PASO = 96;          // píxeles entre estación y estación
    const MIN = 87.5;
    const MAX = 108;
    const n = estaciones.length;
    const mhzDe = (i) => MIN + (i / (n - 1)) * (MAX - MIN);
    const pos = { actual: 0, objetivo: 0, arrastre: null, cercana: -1 };
    let esperaAuto = 0;
    let anchoBanda = 0;

    // ---- La escala: marcas cada 0,5 MHz, números cada 2, una muesca por estación ----
    function armarEscala() {
      const ancho = (n - 1) * PASO;
      const porMhz = ancho / (MAX - MIN);
      el.escala.style.width = `${ancho}px`;
      el.escala.style.setProperty("--por-mhz", `${porMhz}px`);
      const nodos = [];
      for (let f = 88; f <= MAX; f += 2) {
        const numero = document.createElement("span");
        numero.className = "kl-dial__numero";
        numero.style.left = `${(f - MIN) * porMhz}px`;
        numero.textContent = String(f);
        nodos.push(numero);
      }
      estaciones.forEach((tema, i) => {
        const muesca = document.createElement("span");
        muesca.className = "kl-dial__muesca";
        muesca.dataset.tema = String(tema.id); // el reproductor la marca "sonando"
        muesca.style.left = `${i * PASO}px`;
        if (i > 0 && tema.genero !== estaciones[i - 1].genero) {
          const corte = document.createElement("span");
          corte.className = "kl-dial__corte";
          corte.style.left = `${(i - 0.5) * PASO}px`;
          corte.textContent = tema.genero || "";
          nodos.push(corte);
        }
        nodos.push(muesca);
      });
      el.escala.replaceChildren(...nodos);
      el.banda.setAttribute("aria-valuemax", String(n - 1));
    }

    // ---- Lo que se ve en la pantalla ----
    function mostrar(i) {
      const tema = estaciones[i];
      pos.cercana = i;
      if (tema.portada && el.tapa.getAttribute("src") !== tema.portada) el.tapa.src = tema.portada;
      el.tapa.alt = `Portada de ${tema.titulo}`;
      el.mhz.textContent = mhzDe(i).toFixed(1);
      el.genero.textContent = tema.genero || "Keep Listening";
      el.titulo.textContent = tema.titulo;
      el.artista.textContent = tema.artista || "";
      el.play.dataset.catalogo = String(tema.id);
      el.play.dataset.tema = String(tema.id);
      el.play.disabled = !tema.audio;
      el.banda.setAttribute("aria-valuenow", String(i));
      el.banda.setAttribute("aria-valuetext", `${tema.titulo}, ${tema.artista || ""}, ${mhzDe(i).toFixed(1)} FM`);
      dial.classList.remove("cambia");
      void dial.offsetWidth;
      dial.classList.add("cambia");
    }

    // ---- Estática: ruido en un canvas chico, más fuerte cuanto más lejos de una estación ----
    const ctx = el.estatica.getContext("2d");
    const ruido = ctx.createImageData(el.estatica.width, el.estatica.height);
    function pintarEstatica(fuerza) {
      el.estatica.style.opacity = fuerza.toFixed(2);
      if (fuerza < 0.03 || reduce) return;
      const d = ruido.data;
      for (let i = 0; i < d.length; i += 4) {
        const v = Math.random() * 255;
        d[i] = d[i + 1] = d[i + 2] = v;
        d[i + 3] = 255;
      }
      ctx.putImageData(ruido, 0, 0);
    }

    // ---- El bucle: la banda sigue a la sintonía y cae en la estación más cercana ----
    function marco(dt) {
      if (!dial.isConnected) return false;
      if (!pos.arrastre) {
        const k = reduce ? 1 : 1 - Math.exp(-dt * 9);
        pos.actual += (pos.objetivo - pos.actual) * k;
        if (Math.abs(pos.objetivo - pos.actual) < 0.001) pos.actual = pos.objetivo;
      }
      const ancho = anchoBanda || (anchoBanda = el.banda.clientWidth);
      el.escala.style.transform = `translateX(${(ancho / 2 - pos.actual * PASO).toFixed(1)}px)`;
      el.perilla.style.setProperty("--giro", `${(pos.actual * 36).toFixed(1)}deg`);
      const cercana = Math.max(0, Math.min(n - 1, Math.round(pos.actual)));
      if (cercana !== pos.cercana) mostrar(cercana);
      pintarEstatica(Math.min(1, Math.abs(pos.actual - cercana) * 2.4));
      const quieto = !pos.arrastre && pos.actual === pos.objetivo;
      if (quieto) programarAuto();
      return !quieto;
    }

    function mover() {
      vida.reloj("dial", marco);
    }

    function sintonizar(indice) {
      pos.objetivo = Math.max(0, Math.min(n - 1, indice));
      clearTimeout(esperaAuto);
      // La pantalla (y lo que anuncia el lector) cambia ya; la banda llega animada.
      if (pos.objetivo !== pos.cercana) mostrar(pos.objetivo);
      mover();
    }

    // Sintonía automática: si la banda se quedó quieta en una estación, suena.
    function programarAuto() {
      clearTimeout(esperaAuto);
      if (!el.auto.checked) return;
      const tema = estaciones[pos.cercana];
      const bandeja = window.KLPlayer;
      const yaSuena = bandeja && bandeja.estado.pistas[bandeja.estado.indice];
      if (!tema || !tema.audio || (yaSuena && String(yaSuena.id) === String(tema.id))) return;
      esperaAuto = setTimeout(() => el.play.click(), 650);
    }

    // ---- Arrastrar la banda o la perilla ----
    function arrastrable(nodo, sensibilidad) {
      nodo.addEventListener("pointerdown", (evento) => {
        pos.arrastre = { x: evento.clientX, desde: pos.actual, id: evento.pointerId, movido: false };
        try { nodo.setPointerCapture(evento.pointerId); } catch (e) { /* puntero que ya se fue */ }
        dial.classList.add("sintonizando");
        clearTimeout(esperaAuto);
        mover();
      });
      nodo.addEventListener("pointermove", (evento) => {
        const a = pos.arrastre;
        if (!a || evento.pointerId !== a.id) return;
        const dx = evento.clientX - a.x;
        if (Math.abs(dx) > 3) a.movido = true;
        pos.actual = Math.max(-0.4, Math.min(n - 0.6, a.desde - dx * sensibilidad));
        pos.objetivo = pos.actual;
      });
      const soltar = (evento) => {
        const a = pos.arrastre;
        if (!a || evento.pointerId !== a.id) return;
        pos.arrastre = null;
        dial.classList.remove("sintonizando");
        sintonizar(Math.round(pos.actual));
      };
      nodo.addEventListener("pointerup", soltar);
      nodo.addEventListener("pointercancel", soltar);
    }

    arrastrable(el.banda, 1 / PASO);
    // La perilla es más fina: media estación por cada 60 px.
    arrastrable(el.perilla, 1 / 120);

    el.banda.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      const delta = Math.abs(evento.deltaX) > Math.abs(evento.deltaY) ? evento.deltaX : evento.deltaY;
      sintonizar(Math.round(pos.objetivo) + Math.sign(delta));
    }, { passive: false });

    el.banda.addEventListener("keydown", (evento) => {
      const pasos = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 5, PageDown: -5 };
      if (evento.key in pasos) {
        evento.preventDefault();
        sintonizar(Math.round(pos.objetivo) + pasos[evento.key]);
      } else if (evento.key === "Home") {
        evento.preventDefault();
        sintonizar(0);
      } else if (evento.key === "End") {
        evento.preventDefault();
        sintonizar(n - 1);
      } else if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        el.play.click();
      }
    });

    el.anterior.addEventListener("click", () => sintonizar(Math.round(pos.objetivo) - 1));
    el.siguiente.addEventListener("click", () => sintonizar(Math.round(pos.objetivo) + 1));
    el.auto.addEventListener("change", () => {
      KL.util.almacen.guardar("kl-dial-auto", el.auto.checked);
      if (el.auto.checked) programarAuto();
      else clearTimeout(esperaAuto);
    });
    el.auto.checked = Boolean(KL.util.almacen.leer("kl-dial-auto", false));

    // Arranca en una estación al azar: cada visita, otra sintonía.
    armarEscala();
    const inicio = Math.floor(Math.random() * n);
    pos.actual = inicio;
    pos.objetivo = inicio;
    mostrar(inicio);
    mover();

    // El ancho de la banda se mide al cambiar de tamaño, no en cada cuadro.
    if ("ResizeObserver" in window) {
      vida.observar(new ResizeObserver((entradas) => {
        anchoBanda = entradas[0].contentRect.width;
        mover();
      })).observe(el.banda);
    }
    vida.alSalir(() => clearTimeout(esperaAuto));
  });
})();

/* ===========================================================================
 * Keep Listening - núcleo
 *
 * Lo que usa todo el front, en un solo lugar:
 *
 *  - KL.reloj: un único requestAnimationFrame para toda la página. Cada módulo
 *    se suscribe (fondo vivo, vinilo, karaoke, sala, reproductor) y el reloj se
 *    duerme solo cuando no queda nadie o la pestaña está oculta.
 *  - KL.nivel: graves, medios, agudos y golpes del tema que suena, leídos una
 *    sola vez por cuadro del analizador compartido (window.KLAudio).
 *  - KL.util: csrf, escapar, formatear tiempo, leer JSON de un <script>,
 *    almacenamiento seguro, colores del tema y otras piezas chicas.
 *  - KL.pagina: el ciclo de vida de los scripts de cada página (navegación
 *    continua): todo lo que se engancha se suelta solo al salir.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = (window.KL = window.KL || {});
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const raiz = document.documentElement;

  // Velocidad de giro de los discos (bandeja, "Ahora suena"). Una vuelta cada
  // 4 s: más lento que 33⅓ rpm, se lee mejor la etiqueta. El CSS usa la misma
  // ($kl-vuelta-disco en abstracts/_variables.scss).
  KL.GRADOS_POR_SEGUNDO = 90;

  // -------------------------------------------------------------------------
  // Utilidades
  // -------------------------------------------------------------------------
  // Colores del tema que suena (--kl-c1/2/3): se leen una vez y se olvidan
  // cuando ambiente.js avisa que cambió la paleta. Leerlos en cada cuadro
  // obligaba al navegador a recalcular estilos.
  const colores = new Map();
  const COLORES_POR_DEFECTO = { "--kl-c1": "198, 245, 78", "--kl-c2": "61, 206, 160", "--kl-c3": "240, 195, 106" };
  document.addEventListener("kl:paleta", () => colores.clear());

  KL.util = {
    reduce,

    $: (id) => document.getElementById(id),

    csrf() {
      return KL.csrf || (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
    },

    escapar(texto) {
      return String(texto == null ? "" : texto)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    },

    formatear(segundos) {
      if (!isFinite(segundos) || segundos < 0) return "0:00";
      const minutos = Math.floor(segundos / 60);
      const resto = Math.floor(segundos % 60);
      return `${minutos}:${String(resto).padStart(2, "0")}`;
    },

    json(id, porDefecto = null) {
      const nodo = document.getElementById(id);
      if (!nodo) return porDefecto;
      try {
        return JSON.parse(nodo.textContent);
      } catch (error) {
        return porDefecto;
      }
    },

    limitar(valor, min, max) {
      return Math.max(min, Math.min(max, valor));
    },

    // Una copia mezclada (Fisher-Yates).
    barajar(lista) {
      const copia = lista.slice();
      for (let i = copia.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [copia[i], copia[j]] = [copia[j], copia[i]];
      }
      return copia;
    },

    // Un tema subido a Keep Listening tiene id numérico; los de Apple, "itunes-…".
    esLocal(id) {
      return /^\d+$/.test(String(id == null ? "" : id));
    },

    // "r, g, b" de una variable del tema (con caché).
    rgb(variable) {
      if (!colores.has(variable)) {
        const valor = getComputedStyle(raiz).getPropertyValue(variable).trim();
        colores.set(variable, valor || COLORES_POR_DEFECTO[variable] || "255, 255, 255");
      }
      return colores.get(variable);
    },

    color(variable, alfa = 1) {
      return `rgba(${KL.util.rgb(variable)}, ${alfa})`;
    },

    // localStorage que no rompe en modo privado o con el almacenamiento bloqueado.
    almacen: {
      leer(clave, porDefecto = null) {
        try {
          const valor = localStorage.getItem(clave);
          return valor === null ? porDefecto : JSON.parse(valor);
        } catch (error) {
          return porDefecto;
        }
      },
      guardar(clave, valor) {
        try {
          localStorage.setItem(clave, JSON.stringify(valor));
        } catch (error) {
          /* sin almacenamiento: se sigue sin recordar */
        }
      },
    },
  };

  // -------------------------------------------------------------------------
  // Nivel del audio: un solo getByteFrequencyData por cuadro para todos.
  // -------------------------------------------------------------------------
  const nivel = {
    sonando: false,
    bass: 0,
    mid: 0,
    high: 0,
    golpe: false,   // true solo en el cuadro en que hubo un golpe de bajo
    ultimoGolpe: 0,
    promedio: 0,
  };
  KL.nivel = nivel;

  function medir(ahora) {
    const puente = window.KLAudio;
    nivel.golpe = false;
    if (!puente || !nivel.sonando) {
      nivel.bass *= 0.9;
      nivel.mid *= 0.9;
      nivel.high *= 0.9;
      return;
    }
    puente.analyser.getByteFrequencyData(puente.bins);
    const bins = puente.bins;
    let bass = 0;
    let mid = 0;
    let high = 0;
    for (let i = 0; i < 8; i += 1) bass += bins[i];
    for (let i = 8; i < 40; i += 1) mid += bins[i];
    for (let i = 40; i < 96; i += 1) high += bins[i];
    bass /= 8 * 255;
    mid /= 32 * 255;
    high /= 56 * 255;
    nivel.bass += (bass - nivel.bass) * 0.3;
    nivel.mid += (mid - nivel.mid) * 0.2;
    nivel.high += (high - nivel.high) * 0.25;
    nivel.promedio += (bass - nivel.promedio) * 0.04;
    if (bass > 0.32 && bass > nivel.promedio * 1.28 && ahora - nivel.ultimoGolpe > 320) {
      nivel.ultimoGolpe = ahora;
      nivel.golpe = true;
    }
  }

  // Las variables CSS del pulso se escriben al FINAL del cuadro y solo si
  // cambiaron: así los módulos que leen tamaños o colores durante el cuadro no
  // obligan al navegador a recalcular el estilo de toda la página.
  const ultimoCss = { pulso: -1, medio: -1, agudo: -1 };
  function escribirPulso() {
    const valores = { pulso: nivel.bass, medio: nivel.mid, agudo: nivel.high };
    Object.keys(valores).forEach((clave) => {
      const v = nivel.sonando ? Math.round(valores[clave] * 200) / 200 : 0;
      if (v !== ultimoCss[clave]) {
        ultimoCss[clave] = v;
        raiz.style.setProperty(`--kl-${clave}`, String(v));
      }
    });
  }

  // -------------------------------------------------------------------------
  // Reloj
  // -------------------------------------------------------------------------
  const suscriptos = new Map();
  let ciclo = 0;
  let previo = 0;

  function cuadro(ahora) {
    ciclo = 0;
    if (document.hidden) {
      previo = 0;
      return;
    }
    const dt = previo ? Math.min(0.05, (ahora - previo) / 1000) : 1 / 60;
    previo = ahora;
    medir(ahora);
    suscriptos.forEach((funcion, nombre) => {
      try {
        // Devolver false = "ya terminé": se desuscribe solo.
        if (funcion(dt, ahora, nivel) === false && suscriptos.get(nombre) === funcion) suscriptos.delete(nombre);
      } catch (error) {
        suscriptos.delete(nombre);
        if (window.console) console.error(`[KL.reloj] ${nombre}`, error);
      }
    });
    escribirPulso();
    if (suscriptos.size || nivel.bass > 0.002) ciclo = requestAnimationFrame(cuadro);
    else previo = 0;
  }

  function despertar() {
    if (!ciclo && !document.hidden) ciclo = requestAnimationFrame(cuadro);
  }

  KL.reloj = {
    agregar(nombre, funcion) {
      suscriptos.set(nombre, funcion);
      despertar();
      // Solo quita esta suscripción (no una más nueva con el mismo nombre).
      return () => {
        if (suscriptos.get(nombre) === funcion) suscriptos.delete(nombre);
      };
    },
    quitar(nombre) {
      suscriptos.delete(nombre);
    },
    tiene(nombre) {
      return suscriptos.has(nombre);
    },
    despertar,
  };

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) despertar();
  });

  document.addEventListener("kl:reproductor", (evento) => {
    nivel.sonando = !!(evento.detail && evento.detail.sonando);
    despertar();
  });

  // -------------------------------------------------------------------------
  // Ciclo de vida de los scripts de página
  //
  //   KL.pagina(raiz, (vida) => {
  //     vida.escuchar(document, "kl:reproductor", alSonar);  // se suelta solo
  //     vida.reloj("dial", marco);                          // idem
  //     vida.temporizador(fn, 600);
  //     vida.observar(new ResizeObserver(fn)).observe(nodo);
  //     vida.alSalir(() => audio.pause());
  //     if (!vida.vigente()) return;                       // después de un await
  //   });
  //
  // navegar.js avisa "kl:salir" antes de cambiar la página: ahí se suelta todo
  // lo de la página que se va (listeners, observers, timers, animaciones).
  // -------------------------------------------------------------------------
  let paginas = 0;

  KL.pagina = function pagina(raizPagina, montar) {
    if (!raizPagina) return null;
    const control = new AbortController();
    const limpiezas = [];
    const prefijo = `pagina-${(paginas += 1)}`;
    let viva = true;

    const vida = {
      signal: control.signal,
      escuchar(objetivo, tipo, funcion, opciones = {}) {
        objetivo.addEventListener(tipo, funcion, { ...opciones, signal: control.signal });
      },
      observar(observador) {
        limpiezas.push(() => observador.disconnect());
        return observador;
      },
      reloj(nombre, funcion) {
        const clave = `${prefijo}-${nombre}`;
        KL.reloj.agregar(clave, (...args) => (viva ? funcion(...args) : false));
        limpiezas.push(() => KL.reloj.quitar(clave));
      },
      temporizador(funcion, ms) {
        const id = setTimeout(funcion, ms);
        limpiezas.push(() => clearTimeout(id));
        return id;
      },
      alSalir(funcion) {
        limpiezas.push(funcion);
      },
      vigente() {
        return viva && raizPagina.isConnected;
      },
    };

    function terminar() {
      if (!viva) return;
      viva = false;
      control.abort();
      limpiezas.forEach((funcion) => {
        try {
          funcion();
        } catch (error) {
          if (window.console) console.error("[KL.pagina]", error);
        }
      });
      document.removeEventListener("kl:salir", terminar);
      document.removeEventListener("kl:pagina", revisar);
    }

    // Por las dudas (una página que se cambió sin aviso): si la raíz ya no está, se termina.
    function revisar() {
      if (!raizPagina.isConnected) terminar();
    }

    document.addEventListener("kl:salir", terminar);
    document.addEventListener("kl:pagina", revisar);
    montar(vida);
    return vida;
  };
})();

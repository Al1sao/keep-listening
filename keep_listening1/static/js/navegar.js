/* ===========================================================================
 * Keep Listening - navegación continua ("la música no se corta")
 *
 * Los links internos y los formularios GET no recargan la página: se pide el
 * HTML nuevo, se cambian el contenido, el menú y la barra de arriba, y la
 * bandeja sigue sonando. Mientras carga, una línea recorre el borde de arriba
 * (la púa sobre el surco). Al pasar el puntero por un link, la página se pide
 * por adelantado.
 *
 * Ante cualquier duda (otro origen, admin, logout, archivo, error del
 * servidor, cambio de sesión) se deja que el navegador recargue como siempre.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL;
  if (!KL || !window.fetch || !window.DOMParser || !history.pushState) return;

  const reduce = KL.util.reduce;
  // /auth/: ir y volver de Google, Apple, ... siempre con la página entera.
  const EXCLUIDAS = /^\/(django-admin|media|static|api|auth|tienda\/portada|health)\b|\/logout\/?$/;
  const ARCHIVO = /\.(pdf|zip|svg|png|jpe?g|webp|mp3|wav|m4a|flac|ogg|json|txt|csv)$/i;
  const previas = new Map();
  // Una página pedida por adelantado sirve unos segundos: después pudo cambiar
  // (la bolsa, los me gusta), y se vuelve a pedir.
  const VIDA_PREVIA = 8000;
  let turno = 0;

  // -------------------------------------------------------------------------
  // ¿Esta URL se puede cambiar en el lugar?
  // -------------------------------------------------------------------------
  function navegable(url) {
    if (url.origin !== location.origin) return false;
    if (EXCLUIDAS.test(url.pathname) || ARCHIVO.test(url.pathname)) return false;
    return true;
  }

  function mismaPagina(url) {
    return url.pathname === location.pathname && url.search === location.search;
  }

  // -------------------------------------------------------------------------
  // Pedido (con prefetch)
  // -------------------------------------------------------------------------
  function pedir(href) {
    const guardado = previas.get(href);
    if (guardado && performance.now() - guardado.t < VIDA_PREVIA) return guardado.promesa;
    const promesa = fetch(href, {
      credentials: "same-origin",
      headers: { "X-KL-Navegacion": "1", Accept: "text/html" },
    }).then(async (respuesta) => {
      const tipo = respuesta.headers.get("Content-Type") || "";
      if (!respuesta.ok || !tipo.includes("text/html")) throw new Error(String(respuesta.status));
      return { html: await respuesta.text(), url: respuesta.url };
    });
    previas.set(href, { promesa, t: performance.now() });
    promesa.catch(() => previas.delete(href));
    if (previas.size > 12) previas.delete(previas.keys().next().value);
    return promesa;
  }

  // -------------------------------------------------------------------------
  // Indicador de carga: la púa que recorre el surco.
  // -------------------------------------------------------------------------
  const pua = document.createElement("div");
  pua.className = "kl-pua";
  pua.setAttribute("aria-hidden", "true");
  document.body.appendChild(pua);
  let esperaPua = 0;

  function cargando(si) {
    clearTimeout(esperaPua);
    if (si) esperaPua = setTimeout(() => pua.classList.add("activa"), 120);
    else {
      pua.classList.remove("activa");
      pua.classList.add("fin");
      setTimeout(() => pua.classList.remove("fin"), 400);
    }
  }

  // -------------------------------------------------------------------------
  // Cambio de página
  // -------------------------------------------------------------------------
  function reemplazar(selector, doc) {
    const nuevo = doc.querySelector(selector);
    const viejo = document.querySelector(selector);
    if (nuevo && viejo) viejo.replaceWith(document.importNode(nuevo, true));
    return !!(nuevo && viejo);
  }

  function copiarDatos(id, doc) {
    const nuevo = doc.getElementById(id);
    const viejo = document.getElementById(id);
    if (nuevo && viejo) viejo.textContent = nuevo.textContent;
    else if (nuevo && !viejo) document.body.appendChild(document.importNode(nuevo, true));
    else if (!nuevo && viejo) viejo.textContent = "[]";
  }

  // Scripts propios de cada página ({% block js_extra %}): se vuelven a correr.
  function scriptsDePagina(doc) {
    const base = new Set([...document.querySelectorAll("script[src]")]
      .filter((s) => !s.hasAttribute("data-pagina"))
      .map((s) => s.src.split("?")[0]));
    document.querySelectorAll("script[data-pagina]").forEach((s) => s.remove());
    const pendientes = [];
    doc.querySelectorAll("body script[src]").forEach((viejo) => {
      const src = new URL(viejo.getAttribute("src"), location.href).href;
      if (base.has(src.split("?")[0])) return;
      const nuevo = document.createElement("script");
      nuevo.src = src;
      nuevo.dataset.pagina = "1";
      pendientes.push(new Promise((listo) => {
        nuevo.onload = listo;
        nuevo.onerror = listo;
      }));
      document.body.appendChild(nuevo);
    });
    return Promise.all(pendientes);
  }

  function aplicar(doc, url, opciones) {
    // Si cambió la sesión (entró o salió alguien), mejor recargar todo.
    if (doc.body && doc.body.dataset.autenticado !== document.body.dataset.autenticado) {
      location.assign(url);
      return false;
    }
    if (!reemplazar(".kl-main", doc)) {
      location.assign(url);
      return false;
    }
    reemplazar("#kl-alertas", doc);
    reemplazar(".kl-rail", doc);
    reemplazar(".kl-top__acciones", doc);
    reemplazar("#klMenu .offcanvas-body", doc);
    copiarDatos("kl-pistas", doc);
    copiarDatos("kl-me-gusta-ids", doc);
    document.title = doc.title;
    const descripcion = doc.querySelector('meta[name="description"]');
    const actual = document.querySelector('meta[name="description"]');
    if (descripcion && actual) actual.setAttribute("content", descripcion.getAttribute("content"));
    document.documentElement.dataset.pagina = url.pathname.split("/")[1] || "inicio";

    const main = document.querySelector(".kl-main");
    if (opciones.scroll != null) main.scrollTop = opciones.scroll;
    else if (url.hash) {
      const ancla = document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (ancla) ancla.scrollIntoView();
    } else main.scrollTop = 0;
    return true;
  }

  async function navegar(href, opciones = {}) {
    const url = new URL(href, location.href);
    if (!navegable(url)) {
      location.assign(url.href);
      return;
    }
    const mio = ++turno;
    const main = document.querySelector(".kl-main");
    if (!opciones.desdeHistorial) {
      // Se guarda dónde estaba el scroll para volver con "atrás".
      history.replaceState({ ...(history.state || {}), scroll: main ? main.scrollTop : 0 }, "");
    }
    cargando(true);
    let respuesta;
    try {
      respuesta = await pedir(url.href);
    } catch (error) {
      // Si mientras tanto se pidió otra página, esta falla no la pisa.
      if (mio === turno) location.assign(url.href);
      return;
    } finally {
      if (mio === turno) cargando(false);
    }
    if (mio !== turno) return;
    previas.delete(url.href);

    const destino = new URL(respuesta.url || url.href);
    if (url.hash && !destino.hash) destino.hash = url.hash;
    const doc = new DOMParser().parseFromString(respuesta.html, "text/html");

    // Si se estaba escribiendo en el buscador, no se le saca el foco al terminar.
    const foco = document.activeElement;
    // La página que se va suelta lo suyo (audio de prueba, timers, listeners)
    // antes del cambio, no después de cargar la nueva.
    document.dispatchEvent(new CustomEvent("kl:salir", { detail: { url: destino.href } }));
    const cambiar = () => aplicar(doc, destino, opciones);
    let ok;
    if (document.startViewTransition && !reduce) {
      const transicion = document.startViewTransition(() => { ok = cambiar(); });
      await transicion.updateCallbackDone.catch(() => {});
    } else {
      ok = cambiar();
    }
    if (ok === false) return;

    if (!opciones.desdeHistorial) {
      if (opciones.reemplazar) history.replaceState({ scroll: 0 }, "", destino.href);
      else history.pushState({ scroll: 0 }, "", destino.href);
    }

    // Cerrar lo que quedó abierto (menú del celular, resultados del buscador).
    document.querySelectorAll(".offcanvas.show").forEach((nodo) => {
      const instancia = window.bootstrap && window.bootstrap.Offcanvas.getInstance(nodo);
      if (instancia) instancia.hide();
    });
    const resultados = document.getElementById("kl-buscador-resultados");
    if (resultados) resultados.classList.remove("visible");

    await scriptsDePagina(doc);
    if (mio !== turno) return;
    const nuevoMain = document.querySelector(".kl-main");
    if (KL.montar) KL.montar(nuevoMain);
    document.dispatchEvent(new CustomEvent("kl:pagina", { detail: { url: destino.href } }));
    if (!foco || !foco.matches || !foco.matches("[data-buscador]")) {
      nuevoMain.focus({ preventScroll: true });
    }
  }

  KL.navegar = navegar;

  // Lo pedido por adelantado queda viejo cuando cambia algo de la cuenta.
  ["kl:carrito", "kl:me-gusta", "kl:sesion"].forEach((tipo) => {
    document.addEventListener(tipo, () => previas.clear());
  });

  // -------------------------------------------------------------------------
  // Qué se intercepta
  // -------------------------------------------------------------------------
  function linkDe(evento) {
    if (evento.defaultPrevented || evento.button !== 0) return null;
    if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return null;
    const a = evento.target.closest("a[href]");
    if (!a || a.target || a.hasAttribute("download") || a.dataset.bsToggle || a.hasAttribute("data-sin-navegar")) return null;
    const url = new URL(a.href, location.href);
    if (!navegable(url)) return null;
    // Solo cambia el #: lo resuelve el navegador (pestañas, anclas).
    if (mismaPagina(url) && url.hash) return null;
    return url;
  }

  document.addEventListener("click", (evento) => {
    const url = linkDe(evento);
    if (!url) return;
    evento.preventDefault();
    if (mismaPagina(url) && !url.hash) {
      const main = document.querySelector(".kl-main");
      if (main) main.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
      return;
    }
    navegar(url.href);
  });

  // Formularios GET (buscar, filtrar, ordenar): misma idea.
  document.addEventListener("submit", (evento) => {
    const form = evento.target;
    if (evento.defaultPrevented || (form.method || "get").toLowerCase() !== "get" || form.target) return;
    const url = new URL(form.action || location.href, location.href);
    if (!navegable(url)) return;
    evento.preventDefault();
    // Igual que un envío normal: un parámetro vacío también significa algo
    // (en el panel, "estado=" es "todas" y no "pendientes").
    url.search = new URLSearchParams(new FormData(form)).toString();
    navegar(url.href);
  });

  // Prefetch: con el puntero encima un momento, la página ya se va pidiendo.
  let esperaPrevia = 0;
  document.addEventListener("pointerover", (evento) => {
    const a = evento.target.closest && evento.target.closest("a[href]");
    if (!a || evento.pointerType === "touch") return;
    clearTimeout(esperaPrevia);
    esperaPrevia = setTimeout(() => {
      const url = linkDe({ target: a, button: 0, defaultPrevented: false });
      if (url && !mismaPagina(url)) pedir(url.href).catch(() => {});
    }, 90);
  });

  window.addEventListener("popstate", (evento) => {
    navegar(location.href, { desdeHistorial: true, scroll: evento.state && evento.state.scroll });
  });

  history.replaceState({ ...(history.state || {}), scroll: 0 }, "");
  document.documentElement.dataset.pagina = location.pathname.split("/")[1] || "inicio";
})();

/* ===========================================================================
 * Keep Listening - "Iniciá sesión para escuchar"
 * Escuchar requiere cuenta. Al tocar un tema sin sesión aparece este panel; el
 * login se hace ahí mismo (sin recargar) y el tema que se tocó empieza a sonar.
 * La barra de arriba y el menú se actualizan con la página que devuelve el login.
 * =========================================================================== */
(function () {
  "use strict";

  const panel = document.getElementById("kl-sesion");
  const form = document.getElementById("kl-sesion-form");
  const KL = window.KL || {};

  let pendiente = null;
  let ultimoFoco = null;

  // El lado izquierdo muestra el tema que se quiso escuchar: portada como
  // funda, fondo desenfocado y el vinilo con su diseño (el mismo de siempre).
  function pintarTema(pista) {
    const titulo = document.getElementById("kl-sesion-tema-titulo");
    const artista = document.getElementById("kl-sesion-tema-artista");
    const funda = document.getElementById("kl-sesion-funda");
    const fondo = document.getElementById("kl-sesion-fondo");
    const vinilo = document.getElementById("kl-sesion-vinilo");
    if (!titulo) return;
    titulo.textContent = pista ? pista.titulo : "Keep Listening";
    artista.textContent = pista ? pista.artista : "Hip hop y pop, en adelantos";
    const url = pista && pista.portada ? `url("${String(pista.portada).replace(/"/g, "")}")` : "";
    funda.style.backgroundImage = url;
    funda.classList.toggle("con-portada", !!url);
    fondo.style.backgroundImage = url;
    vinilo.style.setProperty("--portada", url || "none");
    if (window.KLDisco) vinilo.dataset.estilo = String(window.KLDisco.diseno(pista).estilo);
  }

  function abrir(pista, reanudar) {
    if (!panel) {
      window.location.href = `${KL.urls.login}?next=${encodeURIComponent(location.pathname + location.search)}`;
      return;
    }
    pendiente = reanudar || null;
    ultimoFoco = document.activeElement;
    pintarTema(pista);
    panel.hidden = false;
    requestAnimationFrame(() => panel.classList.add("abierto"));
    document.body.classList.add("kl-sesion-abierta");
    const usuario = document.getElementById("kl-sesion-usuario");
    if (usuario) usuario.focus();
  }

  function cerrar() {
    if (!panel || panel.hidden) return;
    panel.classList.remove("abierto");
    document.body.classList.remove("kl-sesion-abierta");
    setTimeout(() => { panel.hidden = true; }, 260);
    if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
  }

  function error(mensaje) {
    const nodo = document.getElementById("kl-sesion-error");
    nodo.textContent = mensaje;
    nodo.hidden = !mensaje;
  }

  // La página que devuelve el login ya viene con la sesión: se toman de ahí
  // las partes que cambian (barra, menú, token) sin recargar ni cortar nada.
  function actualizarDesde(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    // El rail entero: la biblioteca y "Tu estante" también cambian con la sesión.
    [".kl-top__acciones", ".kl-rail", "#klMenu .offcanvas-body"].forEach((selector) => {
      const nuevo = doc.querySelector(selector);
      const viejo = document.querySelector(selector);
      if (nuevo && viejo) viejo.replaceWith(document.importNode(nuevo, true));
    });
    const script = [...doc.scripts].map((s) => s.textContent).find((t) => t.includes("window.KL"));
    const token = script && script.match(/csrf:\s*"([^"]+)"/);
    if (token) KL.csrf = token[1];
    KL.autenticado = true;
    document.body.dataset.autenticado = "1";
    const gustos = doc.getElementById("kl-me-gusta-ids");
    if (gustos) {
      const viejo = document.getElementById("kl-me-gusta-ids");
      if (viejo) viejo.textContent = gustos.textContent;
      document.dispatchEvent(new CustomEvent("kl:sesion"));
    }
    const aviso = doc.querySelector(".kl-alerta__texto");
    if (aviso && typeof window.klAviso === "function") window.klAviso(aviso.textContent.trim(), "success");
  }

  if (form) {
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      error("");
      const boton = form.querySelector("[type=submit]");
      boton.disabled = true;
      // Con la navegación continua la página cambió desde que se dibujó el form:
      // el login vuelve a la que se está viendo ahora.
      const siguiente = form.querySelector("[name=next]");
      if (siguiente) siguiente.value = location.pathname + location.search;
      try {
        const respuesta = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        const html = await respuesta.text();
        // Si el login falla, Django vuelve a mostrar el formulario (sin redirigir).
        if (!respuesta.redirected) {
          const doc = new DOMParser().parseFromString(html, "text/html");
          const texto = doc.querySelector(".kl-sesion__error, .kl-alerta__texto, .kl-form__error");
          error(texto ? texto.textContent.trim() : "Usuario o contraseña incorrectos.");
          return;
        }
        actualizarDesde(html);
        const reanudar = pendiente;
        pendiente = null;
        cerrar();
        if (reanudar) reanudar();
      } catch (fallo) {
        error("Sin conexión. Probá de nuevo.");
      } finally {
        boton.disabled = false;
      }
    });
  }

  if (panel) {
    panel.addEventListener("click", (evento) => {
      if (evento.target.closest("[data-cerrar-sesion]")) cerrar();
    });
    document.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape" && !panel.hidden) cerrar();
    });
  }

  // Cualquier botón con data-pedir-sesion abre este panel; al entrar, se recarga
  // la página (por ejemplo, para poder comprar).
  document.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-pedir-sesion]");
    if (!boton) return;
    evento.preventDefault();
    abrir(null, () => window.location.reload());
  });

  window.KLSesion = { pedir: abrir, cerrar };
})();

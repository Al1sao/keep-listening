/* ===========================================================================
 * Keep Listening - estante del menú lateral
 * Tus me gusta como lomos de discos. Marcar o desmarcar un tema lo pone o lo
 * saca del estante en el momento (sin recargar), con la cola al día.
 * =========================================================================== */
(function () {
  "use strict";

  const MAXIMO = 14;

  function fila() {
    return document.getElementById("kl-estante-fila");
  }

  function datos() {
    return window.KL.util.json("kl-estante", []) || [];
  }

  function guardarDatos(lista) {
    const nodo = document.getElementById("kl-estante");
    if (nodo) nodo.textContent = JSON.stringify(lista);
  }

  function lomo(pista) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "kl-estante__lomo entra";
    boton.dataset.catalogo = pista.id;
    boton.dataset.tema = pista.id;
    boton.setAttribute("aria-label", `Reproducir ${pista.titulo}, de ${pista.artista}`);
    if (pista.portada && /^(https:\/\/|\/)/.test(pista.portada)) {
      boton.style.setProperty("--portada", `url("${String(pista.portada).replace(/["\\]/g, "")}")`);
    }
    const nombre = document.createElement("span");
    nombre.className = "kl-estante__nombre";
    nombre.setAttribute("aria-hidden", "true");
    nombre.textContent = pista.titulo;
    const tapa = document.createElement("span");
    tapa.className = "kl-estante__tapa";
    tapa.setAttribute("aria-hidden", "true");
    boton.append(nombre, tapa);
    return boton;
  }

  document.addEventListener("kl:me-gusta", (evento) => {
    const contenedor = fila();
    const detalle = evento.detail || {};
    if (!contenedor || !detalle.id) return;
    let lista = datos().filter((p) => String(p.id) !== String(detalle.id));
    contenedor.querySelectorAll(`[data-catalogo="${CSS.escape(String(detalle.id))}"]`).forEach((n) => n.remove());
    if (detalle.guardada && detalle.pista) {
      lista = [detalle.pista, ...lista].slice(0, MAXIMO);
      const vacio = contenedor.querySelector(".kl-estante__vacio");
      if (vacio) vacio.remove();
      contenedor.prepend(lomo(detalle.pista));
      while (contenedor.querySelectorAll(".kl-estante__lomo").length > MAXIMO) contenedor.lastElementChild.remove();
    }
    guardarDatos(lista);
  });
})();

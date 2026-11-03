/* ===========================================================================
 * Keep Listening - "Grabá tu primer disco" (registro)
 * La etiqueta del vinilo muestra el usuario mientras se escribe, y la edición
 * del disco sube con la seguridad de la contraseña (la mide app.js: el
 * vúmetro guarda el nivel en data-nivel).
 * =========================================================================== */
(function () {
  "use strict";

  const etiqueta = document.getElementById("kl-registro-etiqueta");
  const vinilo = document.getElementById("kl-registro-vinilo");
  const edicion = document.getElementById("kl-registro-edicion");
  const medidor = document.querySelector("[data-medidor]");
  const usuario = document.getElementById("id_username");
  if (!etiqueta || !vinilo || !medidor) return;

  // Nivel de la contraseña (0 a 4) → edición: negro, color, marmolado, salpicado, neón.
  const EDICIONES = [[0, "negro clásico"], [1, "color translúcido"], [2, "marmolado"], [3, "salpicado"], [5, "neón"]];

  function pintarNombre() {
    const texto = (usuario && usuario.value.trim()) || "tu nombre";
    etiqueta.textContent = texto.slice(0, 18);
  }

  function pintarEdicion() {
    const nivel = Number(medidor.dataset.nivel || 0);
    const [estilo, nombre] = EDICIONES[Math.max(0, Math.min(4, nivel))];
    if (vinilo.dataset.estilo !== String(estilo)) {
      vinilo.dataset.estilo = String(estilo);
      vinilo.classList.remove("cambia");
      void vinilo.offsetWidth;
      vinilo.classList.add("cambia");
    }
    edicion.textContent = `Edición ${nombre}`;
  }

  if (usuario) usuario.addEventListener("input", pintarNombre);
  new MutationObserver(pintarEdicion).observe(medidor, { attributes: true, attributeFilter: ["data-nivel"] });
  pintarNombre();
  pintarEdicion();
})();

/* ===========================================================================
 * Keep Listening - letras
 * Trae la letra de LRCLIB (a través de /api/letra/) y la deja lista para el
 * karaoke y para el mapa del tema de la bandeja. Una sola consulta por tema.
 * La letra se ve en "Ahora suena" (modo letra, ahora.js): el botón de letra de
 * la bandeja abre esa vista en lugar de un panel aparte.
 * =========================================================================== */
(function () {
  "use strict";

  function parsear(sincronizada) {
    const resultado = [];
    String(sincronizada || "").split(/\r?\n/).forEach((fila) => {
      const marcas = [...fila.matchAll(/\[(\d+):(\d+(?:\.\d+)?)\]/g)];
      if (!marcas.length) return;
      const verso = fila.replace(/\[[^\]]+\]/g, "").trim();
      if (!verso) return;
      marcas.forEach((marca) => {
        resultado.push({
          t: Number(marca[1]) * 60 + Number(marca[2]),
          texto: verso,
        });
      });
    });
    resultado.sort((a, b) => a.t - b.t);
    return resultado;
  }

  const cache = new Map();

  function obtener(tema) {
    const clave = `${tema.artista || ""}|${tema.titulo || ""}`.toLowerCase();
    if (cache.has(clave)) return cache.get(clave);
    const params = new URLSearchParams({
      artista: tema.artista || "",
      titulo: tema.titulo || "",
      duracion: String(tema.duracion || 0),
    });
    const promesa = fetch(`${KL.urls.letra}?${params}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(String(respuesta.status));
        return respuesta.json();
      })
      .then((datos) => {
        if (datos.sincronizada) {
          const versos = parsear(datos.sincronizada);
          if (versos.length) return { versos, sincroniza: true };
        }
        if (datos.plana) {
          // Las líneas en blanco separan estrofas: se marca el verso que abre cada una.
          const versos = [];
          let corte = false;
          datos.plana.split(/\r?\n/).forEach((fila) => {
            const texto = fila.trim();
            if (!texto) {
              corte = versos.length > 0;
              return;
            }
            versos.push({ t: 0, texto, estrofa: corte });
            corte = false;
          });
          return { versos, sincroniza: false };
        }
        return { versos: [], sincroniza: false };
      })
      .catch((error) => {
        cache.delete(clave);
        throw error;
      });
    cache.set(clave, promesa);
    return promesa;
  }

  window.KLLetra = { obtener };
})();

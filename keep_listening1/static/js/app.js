/* ===========================================================================
 * Keep Listening - interacciones generales
 * Favoritos, carrito, buscador en vivo, pestanas, formularios y moderacion.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL || {};

  // ---------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------
  const $ = (selector, contexto = document) => contexto.querySelector(selector);
  const $$ = (selector, contexto = document) => Array.from(contexto.querySelectorAll(selector));

  const csrf = () => KL.util.csrf();

  async function postJSON(url, datos = {}) {
    const cuerpo = new FormData();
    Object.entries(datos).forEach(([clave, valor]) => cuerpo.append(clave, valor));
    let respuesta;
    try {
      respuesta = await fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
        body: cuerpo,
      });
    } catch (error) {
      return { ok: false, datos: { ok: false, mensaje: "Sin conexión. Probá de nuevo." } };
    }
    let json = {};
    try {
      json = await respuesta.json();
    } catch (error) {
      json = { ok: false, mensaje: "No pudimos completar la accion." };
    }
    return { ok: respuesta.ok && json.ok !== false, datos: json };
  }

  function debounce(funcion, espera = 280) {
    let temporizador;
    return (...args) => {
      clearTimeout(temporizador);
      temporizador = setTimeout(() => funcion(...args), espera);
    };
  }

  // ---------------------------------------------------------------------
  // Avisos flotantes
  // ---------------------------------------------------------------------
  // El contenedor se busca en cada aviso: la navegación continua lo reemplaza.
  function aviso(mensaje, tipo = "info") {
    const contenedorAlertas = $("#kl-alertas");
    if (!contenedorAlertas) return;
    const iconos = {
      success: "bi-check-circle",
      danger: "bi-exclamation-triangle",
      warning: "bi-exclamation-circle",
      info: "bi-info-circle",
    };
    const nodo = document.createElement("div");
    nodo.className = `kl-alerta kl-alerta--${tipo}`;
    nodo.innerHTML = `<i class="bi ${iconos[tipo] || iconos.info}" aria-hidden="true"></i>
      <div class="kl-alerta__texto"></div>
      <button type="button" class="kl-alerta__cerrar" aria-label="Cerrar">&times;</button>`;
    $(".kl-alerta__texto", nodo).textContent = mensaje;
    nodo.dataset.montada = "1";
    contenedorAlertas.appendChild(nodo);
    cerrarSolo(nodo);
  }

  // Se cierra solo, pero con el puntero encima se espera (y el aro se detiene).
  function cerrarSolo(nodo, demora = 4200) {
    nodo.style.setProperty("--dura", `${demora}ms`);
    let resto = demora;
    let inicio = performance.now();
    let espera = 0;
    const quitar = () => {
      clearTimeout(espera);
      nodo.classList.add("saliendo");
      setTimeout(() => nodo.remove(), 300);
    };
    const correr = () => {
      inicio = performance.now();
      espera = setTimeout(quitar, resto);
    };
    nodo.addEventListener("pointerenter", () => {
      clearTimeout(espera);
      resto -= performance.now() - inicio;
    });
    nodo.addEventListener("pointerleave", correr);
    correr();
    const boton = $(".kl-alerta__cerrar", nodo);
    if (boton) boton.addEventListener("click", quitar);
  }

  window.klAviso = aviso;

  // ---------------------------------------------------------------------
  // Favoritos (caso de uso 4) - AJAX
  // ---------------------------------------------------------------------
  document.addEventListener("click", async (evento) => {
    const boton = evento.target.closest("[data-favorito]");
    if (!boton || boton.tagName === "A") return;
    evento.preventDefault();

    if (!KL.autenticado) {
      if (window.KLSesion) window.KLSesion.pedir(null, () => window.location.reload());
      else window.location.href = KL.urls.login;
      return;
    }

    const id = boton.dataset.favorito;
    boton.disabled = true;
    const { ok, datos } = await postJSON(`${KL.urls.favorito}${id}/`);
    boton.disabled = false;
    if (!ok) {
      aviso(datos.mensaje || "No pudimos guardar la cancion.", "danger");
      return;
    }

    // Sincroniza todos los corazones de la misma cancion en la pagina.
    $$(`[data-favorito="${CSS.escape(id)}"]`).forEach((nodo) => {
      nodo.classList.toggle("guardada", datos.guardada);
      nodo.setAttribute("aria-pressed", String(datos.guardada));
      const icono = $("i", nodo);
      if (icono) icono.className = `bi ${datos.guardada ? "bi-heart-fill" : "bi-heart"}`;
    });
    const texto = $(`[data-favorito-texto="${CSS.escape(id)}"]`);
    if (texto) texto.textContent = datos.guardada ? "Guardada en tu lista" : "Guardar en mi lista";
    aviso(datos.mensaje, datos.guardada ? "success" : "info");
  });

  // ---------------------------------------------------------------------
  // Buscador en vivo: un cajón de discos. Lo de Apple va como tapas en fila
  // (se hojean), lo del sitio en filas. Flechas para recorrer, Enter elige.
  // ---------------------------------------------------------------------
  const campoBusqueda = $("[data-buscador]");
  const panelResultados = $("#kl-buscador-resultados");

  if (campoBusqueda && panelResultados) {
    campoBusqueda.setAttribute("role", "combobox");
    campoBusqueda.setAttribute("aria-autocomplete", "list");
    campoBusqueda.setAttribute("aria-expanded", "false");
    campoBusqueda.setAttribute("aria-controls", "kl-buscador-resultados");
    panelResultados.setAttribute("role", "listbox");
    panelResultados.setAttribute("aria-label", "Resultados de búsqueda");

    let ultimaConsulta = "";
    let pedidoBusqueda = null;

    const abrirPanel = (si) => {
      panelResultados.classList.toggle("visible", si);
      campoBusqueda.setAttribute("aria-expanded", String(si));
      if (!si) campoBusqueda.removeAttribute("aria-activedescendant");
    };

    const buscar = debounce(async (texto) => {
      ultimaConsulta = texto.trim();
      if (ultimaConsulta.length < 2) {
        abrirPanel(false);
        return;
      }
      panelResultados.innerHTML = '<p class="kl-buscador__vacio"><span class="kl-buscador__surco"></span>Buscando…</p>';
      abrirPanel(true);
      if (pedidoBusqueda) pedidoBusqueda.abort();
      const pedido = (pedidoBusqueda = new AbortController());
      try {
        const respuesta = await fetch(`${KL.urls.buscar}?q=${encodeURIComponent(ultimaConsulta)}`, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          signal: pedido.signal,
        });
        if (!respuesta.ok) throw new Error("buscar");
        const datos = await respuesta.json();
        if (pedido === pedidoBusqueda) pintarResultados(datos);
      } catch (error) {
        if (error.name === "AbortError" || pedido !== pedidoBusqueda) return;
        panelResultados.innerHTML = '<p class="kl-buscador__vacio">No pudimos buscar. Probá de nuevo.</p>';
      }
    });

    let opcion = 0;
    const item = (etiqueta, atributos, contenido, clase = "") =>
      `<${etiqueta} class="kl-buscador__item ${clase}" role="option" id="kl-opcion-${opcion += 1}" ${atributos}>${contenido}</${etiqueta}>`;

    function pintarResultados(datos) {
      opcion = 0;
      const partes = [];
      if (datos.catalogo && datos.catalogo.length) {
        document.dispatchEvent(new CustomEvent("kl:catalogo", { detail: datos.catalogo }));
        partes.push('<div role="group" aria-label="Temas"><p class="kl-buscador__grupo-titulo" aria-hidden="true">Temas</p><div class="kl-buscador__cajon">');
        datos.catalogo.forEach((pista) => {
          partes.push(item("button", `type="button" data-catalogo="${escapar(pista.id)}"`,
            `<span class="kl-buscador__tapa"><img src="${escapar(pista.portada)}" alt="" width="120" height="120" loading="lazy">
              <i class="bi ${pista.audio ? "bi-play-fill" : "bi-box-arrow-up-right"}" aria-hidden="true"></i></span>
             <strong>${escapar(pista.titulo)}</strong><small>${escapar(pista.artista)}</small>`, "kl-buscador__item--disco"));
        });
        partes.push("</div></div>");
      }
      if (datos.canciones && datos.canciones.length) {
        partes.push('<div role="group" aria-label="De la comunidad"><p class="kl-buscador__grupo-titulo" aria-hidden="true">De la comunidad</p>');
        datos.canciones.forEach((pista) => {
          partes.push(item("a", `href="${escapar(pista.url)}"`,
            `<img src="${escapar(pista.portada)}" alt="" width="40" height="40">
             <span><strong>${escapar(pista.titulo)}</strong><small>${escapar(pista.artista)}</small></span>`));
        });
        partes.push("</div>");
      }
      if (datos.albumes && datos.albumes.length) {
        partes.push('<div role="group" aria-label="En la disquería"><p class="kl-buscador__grupo-titulo" aria-hidden="true">En la disquería</p>');
        datos.albumes.forEach((album) => {
          partes.push(item("a", `href="${escapar(album.url)}"`,
            `<img src="${escapar(album.portada)}" alt="" width="40" height="40">
             <span><strong>${escapar(album.titulo)}</strong><small>Vinilo · ${escapar(album.artista)}</small></span>`));
        });
        partes.push("</div>");
      }
      if (datos.artistas && datos.artistas.length) {
        partes.push('<div role="group" aria-label="Artistas"><p class="kl-buscador__grupo-titulo" aria-hidden="true">Artistas</p>');
        datos.artistas.forEach((artista) => {
          partes.push(item("a", `href="${escapar(artista.url)}"`,
            `<span class="kl-header__avatar">${escapar(artista.iniciales)}</span>
             <span><strong>${escapar(artista.username)}</strong></span>`));
        });
        partes.push("</div>");
      }
      if (partes.length) {
        partes.push(item("a", `href="${KL.urls.explorar}?q=${encodeURIComponent(ultimaConsulta)}"`,
          `<i class="bi bi-arrow-right" aria-hidden="true"></i><span>Ver todo "${escapar(ultimaConsulta)}" en Explorar</span>`,
          "kl-buscador__todo"));
      }
      panelResultados.innerHTML = partes.length
        ? partes.join("")
        : '<p class="kl-buscador__vacio">Nada con ese nombre. Probá artista y tema, por ejemplo Daft Punk.</p>';
      abrirPanel(true);
    }

    function mover(paso) {
      const opciones = $$("[role=option]", panelResultados);
      if (!opciones.length) return;
      const actual = opciones.findIndex((o) => o.classList.contains("activo"));
      const siguiente = (actual + paso + opciones.length) % opciones.length;
      opciones.forEach((o, i) => o.classList.toggle("activo", i === siguiente));
      campoBusqueda.setAttribute("aria-activedescendant", opciones[siguiente].id);
      opciones[siguiente].scrollIntoView({ block: "nearest", inline: "nearest" });
    }

    campoBusqueda.addEventListener("input", (evento) => buscar(evento.target.value));
    campoBusqueda.addEventListener("keydown", (evento) => {
      const abierto = panelResultados.classList.contains("visible");
      if (evento.key === "ArrowDown" && abierto) { evento.preventDefault(); mover(1); return; }
      if (evento.key === "ArrowUp" && abierto) { evento.preventDefault(); mover(-1); return; }
      if (evento.key === "Escape") { abrirPanel(false); return; }
      if (evento.key !== "Enter") return;
      evento.preventDefault();
      const elegido = $("[role=option].activo", panelResultados);
      if (elegido && abierto) {
        elegido.click();
        abrirPanel(false);
        return;
      }
      const valor = campoBusqueda.value.trim();
      const destino = `${KL.urls.explorar}?q=${encodeURIComponent(valor)}`;
      if (valor) (KL.navegar ? KL.navegar(destino) : window.location.assign(destino));
      abrirPanel(false);
    });
    campoBusqueda.addEventListener("focus", () => {
      if (panelResultados.children.length && campoBusqueda.value.trim().length >= 2) abrirPanel(true);
    });
    document.addEventListener("click", (evento) => {
      if (!evento.target.closest("#kl-buscador")) abrirPanel(false);
      else if (evento.target.closest("[role=option]")) setTimeout(() => abrirPanel(false), 0);
    });
  }

  // Escapa también comillas: el resultado se usa dentro de atributos.
  const escapar = KL.util.escapar;

  // =====================================================================
  // De acá para abajo todo es por delegación (un listener en document):
  // funciona igual con el contenido que llega por la navegación continua
  // (navegar.js). Lo que hay que preparar al entrar a una página va en
  // KL.montar(raiz), que se llama al cargar y después de cada cambio.
  // =====================================================================

  // ---- Pestañas (Mi música) ---------------------------------------------
  function activarPestana(boton) {
    const grupo = boton.closest("[role=tablist]") || document;
    $$("[data-tab]", grupo).forEach((otro) => {
      otro.classList.toggle("activo", otro === boton);
      otro.setAttribute("aria-selected", String(otro === boton));
    });
    $$(".kl-tab-panel").forEach((panel) => panel.classList.remove("activo"));
    const panel = document.getElementById(`tab-${boton.dataset.tab}`);
    if (panel) panel.classList.add("activo");
    history.replaceState(history.state, "", `#${boton.dataset.tab}`);
  }

  document.addEventListener("click", (evento) => {
    const tab = evento.target.closest("[data-tab]");
    if (tab) activarPestana(tab);

    // Ver / ocultar contraseña
    const ver = evento.target.closest("[data-ver-password]");
    if (ver) {
      const campo = $("input", ver.parentElement);
      if (campo) {
        const visible = campo.type === "text";
        campo.type = visible ? "password" : "text";
        ver.setAttribute("aria-label", visible ? "Mostrar contraseña" : "Ocultar contraseña");
        ver.setAttribute("aria-pressed", String(!visible));
        const icono = $("i", ver);
        if (icono) icono.className = `bi ${visible ? "bi-eye" : "bi-eye-slash"}`;
      }
    }

    // Botones + / - en el detalle del álbum
    const mas = evento.target.closest("[data-cantidad]");
    if (mas) {
      const campo = $("input[name=cantidad]", mas.parentElement);
      if (campo) campo.value = Math.min(20, Math.max(1, Number(campo.value) + Number(mas.dataset.cantidad)));
    }

    // Carrito: + / - y quitar
    const delta = evento.target.closest("[data-item-cantidad]");
    if (delta) {
      const id = delta.dataset.itemCantidad;
      const campo = $(`[data-item-input="${CSS.escape(id)}"]`);
      if (campo) {
        const nuevo = Math.max(0, Number(campo.value) + Number(delta.dataset.delta));
        campo.value = Math.max(1, nuevo);
        actualizarItem(id, nuevo);
      }
    }
    const quitar = evento.target.closest("[data-item-eliminar]");
    if (quitar) eliminarItem(quitar);

    // Panel: aprobar y rechazar
    const aprobar = evento.target.closest("[data-aprobar]");
    if (aprobar) aprobarCancion(aprobar);
    const rechazar = evento.target.closest("[data-rechazar]");
    if (rechazar) abrirRechazo(rechazar);
  });

  document.addEventListener("change", (evento) => {
    const objetivo = evento.target;
    if (objetivo.matches("[data-enviar-al-cambiar]") && objetivo.form) {
      objetivo.form.requestSubmit ? objetivo.form.requestSubmit() : objetivo.form.submit();
    }
    if (objetivo.matches("[data-item-input]")) actualizarItem(objetivo.dataset.itemInput, objetivo.value);
    if (objetivo.matches("[data-preview]")) previsualizar(objetivo);
    if (objetivo.matches("[data-audio]")) mostrarArchivo(objetivo);
    if (objetivo.matches("#id_tipo_publicacion")) alternarBloqueAlbum();
  });

  document.addEventListener("input", (evento) => {
    const objetivo = evento.target;
    if (objetivo.matches("#id_password1")) medirClave(objetivo);
    if (objetivo.matches('[data-mask="tarjeta"]')) mascaraTarjeta(objetivo);
    if (objetivo.matches('[data-mask="vencimiento"]')) mascaraVencimiento(objetivo);
    if (objetivo.matches('[data-mask="cvv"]')) objetivo.value = objetivo.value.replace(/\D/g, "").slice(0, 4);
    if (objetivo.matches("#id_nombre_titular, #id_apellido_titular")) pintarTitular();
  });

  document.addEventListener("submit", (evento) => {
    const formulario = evento.target;
    if (formulario.matches("[data-confirmar]") && !window.confirm(formulario.dataset.confirmar)) {
      evento.preventDefault();
      return;
    }
    if (formulario.matches("[data-form-carrito]")) agregarAlCarrito(evento, formulario);
    if (formulario.matches("#form-rechazo")) enviarRechazo(evento, formulario);
  });

  // ---- Seguridad de la contraseña (vúmetro del registro) ------------------
  function medirClave(campo) {
    const medidor = $("[data-medidor]");
    if (!medidor) return;
    const valor = campo.value;
    let nivel = 0;
    if (valor.length >= 8) nivel += 1;
    if (valor.length >= 12) nivel += 0.5;
    if (/[A-Z]/.test(valor) && /[a-z]/.test(valor)) nivel += 1;
    if (/\d/.test(valor)) nivel += 1;
    if (/[^A-Za-z0-9]/.test(valor)) nivel += 0.5;
    nivel = Math.min(4, nivel);
    medidor.dataset.nivel = String(Math.floor(nivel));
    medidor.style.setProperty("--nivel", String(nivel / 4));
    const texto = $("[data-medidor-texto]", medidor);
    if (texto) texto.textContent = ["Muy débil", "Débil", "Aceptable", "Buena", "Excelente"][Math.floor(nivel)];
  }

  // ---- Subida: dropzone + vista previa ---------------------------------------
  function mostrarArchivo(campo) {
    const zona = campo.closest("[data-dropzone]");
    const etiqueta = zona && $("[data-dropzone-nombre]", zona);
    if (etiqueta && campo.files && campo.files.length) {
      const archivo = campo.files[0];
      etiqueta.textContent = `${archivo.name} (${(archivo.size / 1048576).toFixed(1)} MB)`;
    }
    document.dispatchEvent(new CustomEvent("kl:audio-elegido", { detail: campo }));
  }

  ["dragenter", "dragover"].forEach((tipo) =>
    document.addEventListener(tipo, (evento) => {
      const zona = evento.target.closest && evento.target.closest("[data-dropzone]");
      if (!zona) return;
      evento.preventDefault();
      zona.classList.add("arrastrando");
    })
  );
  ["dragleave", "drop"].forEach((tipo) =>
    document.addEventListener(tipo, (evento) => {
      const zona = evento.target.closest && evento.target.closest("[data-dropzone]");
      if (!zona) return;
      evento.preventDefault();
      zona.classList.remove("arrastrando");
      if (tipo === "drop" && evento.dataTransfer.files.length) {
        const campo = $("[data-audio]", zona);
        if (campo) {
          campo.files = evento.dataTransfer.files;
          mostrarArchivo(campo);
        }
      }
    })
  );

  function previsualizar(campo) {
    const destino = $(`[data-preview-destino="${CSS.escape(campo.dataset.preview)}"]`);
    if (!destino || !campo.files || !campo.files.length) return;
    const url = URL.createObjectURL(campo.files[0]);
    const img = $("img", destino);
    img.onload = () => URL.revokeObjectURL(url);
    img.src = url;
    img.hidden = false;
    destino.classList.add("visible");
  }

  function alternarBloqueAlbum() {
    const selectTipo = $("#id_tipo_publicacion");
    const bloqueAlbum = $("#kl-bloque-album");
    if (selectTipo && bloqueAlbum) bloqueAlbum.style.display = selectTipo.value === "ALBUM" ? "" : "none";
  }

  // ---- Carrito (caso de uso 6) --------------------------------------------------
  function actualizarResumenCarrito(datos) {
    $$("[data-carrito-contador]").forEach((nodo) => {
      nodo.textContent = datos.cantidad;
      nodo.dataset.cantidad = datos.cantidad;
    });
    $$("[data-carrito-cantidad]").forEach((nodo) => (nodo.textContent = datos.cantidad));
    $$("[data-carrito-total]").forEach((nodo) => (nodo.textContent = datos.total_formateado));
  }

  async function agregarAlCarrito(evento, formulario) {
    evento.preventDefault();
    const boton = $("button[type=submit]", formulario);
    if (boton) boton.disabled = true;
    let respuesta;
    let datos = {};
    try {
      respuesta = await fetch(formulario.action, {
        method: "POST",
        headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(formulario),
      });
      datos = await respuesta.json();
    } catch (error) {
      datos = { ok: false };
    } finally {
      if (boton) boton.disabled = false;
    }
    if (!respuesta || !respuesta.ok || datos.ok === false) {
      aviso(datos.mensaje || "No pudimos agregar el producto.", "danger");
      return;
    }
    actualizarResumenCarrito(datos);
    aviso(datos.mensaje, "success");
    document.dispatchEvent(new CustomEvent("kl:carrito", { detail: { formulario, datos } }));
  }

  async function actualizarItem(id, cantidad) {
    const { ok, datos } = await postJSON(`${KL.urls.carritoItem}${encodeURIComponent(id)}/`, { cantidad });
    if (!ok) {
      aviso("No pudimos actualizar el carrito.", "danger");
      return;
    }
    const subtotal = $(`[data-item-subtotal="${CSS.escape(String(id))}"]`);
    if (subtotal) subtotal.textContent = datos.subtotal_formateado;
    // El servidor puede ajustar la cantidad (stock, tope): el campo muestra la real.
    const campo = $(`[data-item-input="${CSS.escape(String(id))}"]`);
    if (campo) campo.value = datos.item_cantidad;
    if (Number(datos.item_cantidad) === 0) quitarFila(id);
    actualizarResumenCarrito(datos);
  }

  function quitarFila(id) {
    const fila = $(`[data-item="${CSS.escape(String(id))}"]`);
    if (!fila) return;
    fila.classList.add("eliminando");
    setTimeout(() => {
      fila.remove();
      if (!$$(".kl-item-carrito").length) window.location.reload();
    }, 260);
  }

  async function eliminarItem(boton) {
    const id = boton.dataset.itemEliminar;
    const { ok, datos } = await postJSON(`${KL.urls.carritoItem}${encodeURIComponent(id)}/eliminar/`);
    if (!ok) {
      aviso("No pudimos quitar el producto.", "danger");
      return;
    }
    quitarFila(id);
    actualizarResumenCarrito(datos);
    aviso(datos.mensaje, "info");
  }

  // ---- Checkout: máscaras y tarjeta visual ----------------------------------------
  function mascaraTarjeta(campo) {
    const digitos = campo.value.replace(/\D/g, "").slice(0, 19);
    campo.value = digitos.replace(/(.{4})/g, "$1 ").trim();
    const visual = $("[data-tarjeta-numero]");
    if (visual) visual.textContent = (campo.value || "#### #### #### ####").padEnd(19, "#");
    const marca = $("[data-tarjeta-marca]");
    if (marca) {
      const nombre = /^4/.test(digitos) ? "VISA" : /^5[1-5]|^2[2-7]/.test(digitos) ? "MASTERCARD" : /^3[47]/.test(digitos) ? "AMEX" : "";
      marca.textContent = nombre;
    }
  }

  function mascaraVencimiento(campo) {
    let valor = campo.value.replace(/\D/g, "").slice(0, 4);
    if (valor.length >= 3) valor = `${valor.slice(0, 2)}/${valor.slice(2)}`;
    campo.value = valor;
    const visual = $("[data-tarjeta-vencimiento]");
    if (visual) visual.textContent = valor || "MM/AA";
  }

  function pintarTitular() {
    const visual = $("[data-tarjeta-titular]");
    if (!visual) return;
    const nombre = $("#id_nombre_titular");
    const apellido = $("#id_apellido_titular");
    const texto = `${nombre ? nombre.value : ""} ${apellido ? apellido.value : ""}`.trim();
    visual.textContent = texto || "Nombre del titular";
  }

  // ---- Panel de administración: aprobar / rechazar sin recargar --------------------
  async function aprobarCancion(boton) {
    boton.disabled = true;
    const { ok, datos } = await postJSON(boton.dataset.aprobar);
    if (!ok) {
      boton.disabled = false;
      aviso(datos.mensaje || "No pudimos aprobar la canción.", "danger");
      return;
    }
    resolverTarjeta(boton, "Aprobado");
    actualizarPendientes(datos.pendientes);
    aviso(datos.mensaje, "success");
  }

  let modalRechazo = null;
  function abrirRechazo(boton) {
    const nodo = $("#modalRechazo");
    const formulario = $("#form-rechazo");
    if (!nodo || !formulario || !window.bootstrap) return;
    formulario.dataset.url = boton.dataset.rechazar;
    $("#modal-rechazo-texto").textContent = `Motivo del rechazo de "${boton.dataset.titulo || ""}"`;
    modalRechazo = window.bootstrap.Modal.getOrCreateInstance(nodo);
    modalRechazo.show();
  }

  async function enviarRechazo(evento, formulario) {
    evento.preventDefault();
    const motivo = $("#modal-rechazo-motivo").value.trim();
    if (!motivo) return;
    const { ok, datos } = await postJSON(formulario.dataset.url, { motivo });
    if (!ok) {
      aviso(datos.mensaje || "No pudimos rechazar la canción.", "danger");
      return;
    }
    if (modalRechazo) modalRechazo.hide();
    const boton = $(`[data-rechazar="${CSS.escape(formulario.dataset.url)}"]`);
    if (boton) resolverTarjeta(boton, "Rechazado");
    actualizarPendientes(datos.pendientes);
    aviso(datos.mensaje, "warning");
  }

  // El veredicto se estampa sobre la funda de la prueba y la tarjeta se va.
  function resolverTarjeta(boton, veredicto) {
    const tarjeta = boton.closest(".kl-revision");
    if (!tarjeta) return;
    const sello = $(".kl-revision__sello", tarjeta);
    if (sello) sello.textContent = veredicto;
    tarjeta.dataset.veredicto = veredicto === "Aprobado" ? "si" : "no";
    $$("button, a", tarjeta).forEach((nodo) => nodo.setAttribute("tabindex", "-1"));
    setTimeout(() => tarjeta.classList.add("resuelta"), KL.util.reduce ? 0 : 650);
    setTimeout(() => tarjeta.remove(), KL.util.reduce ? 260 : 950);
  }

  function actualizarPendientes(cantidad) {
    if (cantidad === undefined) return;
    $$(".kl-consola__canal .kl-badge--pendiente").forEach((nodo) => (nodo.textContent = cantidad));
  }

  // ---- Lo que se prepara al entrar a cada página ------------------------------------
  KL.montar = function montar(raiz = document) {
    // Los avisos del servidor viven fuera de .kl-main: se buscan en toda la página.
    $$(".kl-alerta", document).forEach((nodo) => {
      if (nodo.dataset.montada) return;
      nodo.dataset.montada = "1";
      cerrarSolo(nodo, 5200);
    });
    alternarBloqueAlbum();
    if (location.hash) {
      let tab = location.hash.slice(1);
      try { tab = decodeURIComponent(tab); } catch (error) { /* hash mal formado: se usa tal cual */ }
      const destino = $(`[data-tab="${CSS.escape(tab)}"]`);
      if (destino) activarPestana(destino);
    }
  };

  KL.montar(document);
})();

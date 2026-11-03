/* ===========================================================================
 * Keep Listening - visor del vinilo en la ficha de la tienda
 * 2D: tapa y disco planos (el disco gira). 3D: la funda es un objeto con tapa,
 * contratapa y lomo; se gira arrastrando y el disco entra y sale por el lado
 * abierto. Cuando nadie lo toca, gira solo despacito.
 * =========================================================================== */
(function () {
  "use strict";

  const visor = document.getElementById("kl-visor");
  const objeto = document.getElementById("kl-visor-objeto");
  if (!visor || !objeto) return;

  const reduce = window.KL.util.reduce;
  const sacar = document.getElementById("kl-visor-sacar");
  const estado = { rx: -12, ry: -28, vrx: 0, vry: 0, arrastre: null, quieto: 0 };

  function pintar() {
    objeto.style.setProperty("--rx", `${estado.rx.toFixed(2)}deg`);
    objeto.style.setProperty("--ry", `${estado.ry.toFixed(2)}deg`);
  }

  // Solo gira mientras se ve: con el visor fuera de pantalla, el reloj lo suelta.
  let visible = true;
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entradas) => {
      const antes = visible;
      visible = entradas.some((e) => e.isIntersecting);
      if (visible && !antes && visor.dataset.modo === "3d") arrancar();
    }).observe(visor);
  }

  // Suscripto al reloj común mientras el visor 3D está en la página, activo y a la vista.
  function marco(dt, ahora) {
    if (visor.dataset.modo !== "3d" || !visor.isConnected || !visible) return false;
    if (!estado.arrastre) {
      // Inercia después de soltar y, pasado un rato, giro automático.
      estado.ry += estado.vry;
      estado.rx += estado.vrx;
      estado.vry *= 0.94;
      estado.vrx *= 0.94;
      if (!reduce && ahora - estado.quieto > 1800) estado.ry += 0.18;
      estado.rx += (-12 - estado.rx) * 0.02;
    }
    estado.rx = Math.max(-60, Math.min(60, estado.rx));
    pintar();
    return true;
  }

  function arrancar() {
    window.KL.reloj.agregar("visor-3d", marco);
  }

  function modo(nuevo) {
    visor.dataset.modo = nuevo;
    visor.querySelectorAll("[data-visor-modo]").forEach((boton) => {
      boton.setAttribute("aria-selected", String(boton.dataset.visorModo === nuevo));
    });
    visor.querySelector(".kl-visor__plano").setAttribute("aria-hidden", String(nuevo !== "2d"));
    if (nuevo === "3d") {
      estado.quieto = performance.now();
      pintar();
      arrancar();
    }
  }

  visor.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-visor-modo]");
    if (boton) modo(boton.dataset.visorModo);
  });

  // Arrastrar para girar (mouse y dedo).
  const escena = visor.querySelector(".kl-visor__escena");
  escena.addEventListener("pointerdown", (evento) => {
    estado.arrastre = { x: evento.clientX, y: evento.clientY, t: performance.now() };
    escena.setPointerCapture(evento.pointerId);
    escena.classList.add("arrastrando");
  });
  escena.addEventListener("pointermove", (evento) => {
    if (!estado.arrastre) return;
    const dx = evento.clientX - estado.arrastre.x;
    const dy = evento.clientY - estado.arrastre.y;
    estado.ry += dx * 0.45;
    estado.rx -= dy * 0.35;
    estado.vry = dx * 0.25;
    estado.vrx = -dy * 0.2;
    estado.arrastre.x = evento.clientX;
    estado.arrastre.y = evento.clientY;
    pintar();
  });
  const soltar = () => {
    estado.arrastre = null;
    estado.quieto = performance.now();
    escena.classList.remove("arrastrando");
  };
  escena.addEventListener("pointerup", soltar);
  escena.addEventListener("pointercancel", soltar);

  // El disco entra y sale de la funda (en las dos vistas).
  if (sacar) {
    sacar.addEventListener("click", () => {
      const afuera = !visor.classList.toggle("guardado");
      sacar.setAttribute("aria-pressed", String(afuera));
      sacar.querySelector("span").textContent = afuera ? "Guardar el disco" : "Sacar el disco";
      sacar.querySelector("i").className = `bi ${afuera ? "bi-box-arrow-right" : "bi-box-arrow-left"}`;
    });
  }

  pintar();
})();

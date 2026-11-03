/* ===========================================================================
 * La sala del inicio. Cada portada flota en su propio tiempo y el pulso
 * de la canción la levanta, la agranda y la inclina.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL;
  const campo = document.getElementById("kl-campo");
  if (!campo) return;

  KL.pagina(campo, (vida) => {
    const piezas = Array.from(campo.querySelectorAll(".kl-flota")).map((pieza) => {
      const estilo = getComputedStyle(pieza);
      const numero = (nombre) => parseFloat(estilo.getPropertyValue(nombre)) || 0;
      return {
        pieza,
        dx: numero("--dx"),
        dy: numero("--dy"),
        z: numero("--z"),
        escala: numero("--escala") || 1,
        dur: numero("--dur") || 18,
        empuje: numero("--empuje") || 18,
        giro: numero("--giro") || 1,
        fase: numero("--i"),
      };
    });
    const motas = Array.from(document.querySelectorAll(".kl-espacio__motas span")).map((mota) => ({
      mota,
      fase: parseFloat(getComputedStyle(mota).getPropertyValue("--i")) || 0,
    }));

    // La portada que suena se marca (y al tocarla abre "Ahora suena").
    vida.escuchar(document, "kl:reproductor", (evento) => {
      const detalle = evento.detail || {};
      const id = detalle.pista && detalle.pista.id != null ? String(detalle.pista.id) : "";
      piezas.forEach(({ pieza }) => {
        const suyo = pieza.getAttribute("data-catalogo") || pieza.getAttribute("data-reproducir") || "";
        pieza.classList.toggle("is-sonando", Boolean(detalle.sonando) && suyo === id);
      });
    });

    if (!piezas.length || KL.util.reduce) {
      piezas.forEach((dato) => {
        dato.pieza.style.transform = `translate3d(0, 0, ${dato.z}px) scale(${dato.escala})`;
      });
      return;
    }

    // El nivel del audio lo mide el núcleo (una vez por cuadro para todos).
    const audio = KL.nivel;
    function marco(dt, ahora) {
      const bajo = audio.sonando ? audio.bass : 0;
      const medio = audio.sonando ? audio.mid : 0;
      const agudo = audio.sonando ? audio.high : 0;
      const segundos = ahora / 1000;
      piezas.forEach((dato) => {
        const vuelta = (segundos / dato.dur) * Math.PI * 2 + dato.fase;
        const onda = Math.sin(vuelta);
        const x = onda * dato.dx;
        const y = Math.cos(vuelta) * dato.dy - bajo * dato.empuje;
        const escala = dato.escala + bajo * 0.08 + medio * 0.035;
        const giro = agudo * dato.giro * 4 * onda;
        dato.pieza.style.transform =
          `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, ${dato.z}px) rotate(${giro.toFixed(2)}deg) scale(${escala.toFixed(3)})`;
      });
      motas.forEach((dato) => {
        const y = Math.sin(segundos * 0.7 + dato.fase) * 10 - agudo * (8 + dato.fase * 3);
        dato.mota.style.transform = `translateY(${y.toFixed(1)}px)`;
      });
    }

    // Solo se mueve mientras la sala se ve (al bajar con el scroll, se detiene;
    // devolver false la desuscribe del reloj y al volver se suscribe otra vez).
    let visible = true;
    const correr = (dt, ahora) => {
      if (!visible) return false;
      marco(dt, ahora);
      return true;
    };
    vida.observar(new IntersectionObserver((entradas) => {
      const antes = visible;
      visible = entradas.some((e) => e.isIntersecting);
      if (visible && !antes) vida.reloj("sala", correr);
    })).observe(campo);
    vida.reloj("sala", correr);
  });
})();

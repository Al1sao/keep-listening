/* ===========================================================================
 * Keep Listening - la batea de "Tu colección"
 * Los discos parados uno detrás del otro. Se hojean con la rueda, arrastrando
 * o con las flechas: los de adelante se vuelcan hacia vos, como cuando se
 * revuelve una batea. Tocar un disco de atrás lo trae; tocar el de adelante
 * (o "Escuchar") lo pone a sonar con la batea entera como cola.
 * =========================================================================== */
(function () {
  "use strict";

  const cajon = document.getElementById("kl-batea-cajon");
  if (!cajon) return;

  const discos = Array.from(cajon.querySelectorAll(".kl-batea__disco"));
  const lista = window.KL.util.json("kl-coleccion", []) || [];
  const titulo = document.getElementById("kl-batea-titulo");
  const artista = document.getElementById("kl-batea-artista");
  const numero = document.getElementById("kl-batea-numero");
  const play = document.getElementById("kl-batea-play");
  let actual = 0;

  function pintar() {
    discos.forEach((disco, i) => {
      const pos = i - actual;
      disco.style.setProperty("--pos", String(Math.max(-3, Math.min(pos, 8))));
      disco.classList.toggle("delante", pos === 0);
      disco.classList.toggle("volcado", pos < 0);
      disco.setAttribute("aria-selected", String(pos === 0));
      disco.hidden = pos > 8 || pos < -3;
    });
    cajon.setAttribute("aria-activedescendant", `kl-disco-${actual}`);
    const pista = lista[actual];
    if (pista) {
      titulo.textContent = pista.titulo;
      artista.textContent = pista.artista;
      numero.textContent = String(actual + 1);
    }
  }

  function ir(indice) {
    const nuevo = Math.max(0, Math.min(discos.length - 1, indice));
    if (nuevo === actual) return;
    actual = nuevo;
    pintar();
  }

  function escuchar() {
    const disco = discos[actual];
    // El reproductor escucha clics en [data-catalogo] (la sección trae data-lista).
    if (disco) disco.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }

  // Un disco de atrás se trae adelante; el de adelante suena.
  let hojeo = false;
  cajon.addEventListener("click", (evento) => {
    // Si fue un arrastre, el clic que sigue no elige ni reproduce.
    if (hojeo) {
      hojeo = false;
      evento.preventDefault();
      evento.stopPropagation();
      return;
    }
    const disco = evento.target.closest(".kl-batea__disco");
    if (!disco || evento.isTrusted === false) return;
    const indice = Number(disco.dataset.indice);
    if (indice !== actual) {
      evento.preventDefault();
      evento.stopPropagation();
      ir(indice);
    }
  }, true);

  // Rueda: un disco por "muesca", con un pequeño freno para que no se dispare.
  let bloqueo = 0;
  cajon.addEventListener("wheel", (evento) => {
    evento.preventDefault();
    const ahora = performance.now();
    if (ahora - bloqueo < 90) return;
    bloqueo = ahora;
    ir(actual + (evento.deltaY > 0 ? 1 : -1));
  }, { passive: false });

  // Arrastre vertical (dedo o mouse). Con setPointerCapture no hacen falta
  // listeners en window que queden colgados al cambiar de página.
  let arrastre = null;
  cajon.addEventListener("pointerdown", (evento) => {
    arrastre = { y: evento.clientY, desde: actual, id: evento.pointerId };
    hojeo = false;
  });
  cajon.addEventListener("pointermove", (evento) => {
    if (!arrastre || evento.pointerId !== arrastre.id) return;
    const pasos = Math.round((arrastre.y - evento.clientY) / 46);
    if (pasos && !hojeo) {
      hojeo = true;
      cajon.setPointerCapture(evento.pointerId);
      cajon.classList.add("hojeando");
    }
    if (hojeo) ir(arrastre.desde + pasos);
  });
  const soltar = () => {
    arrastre = null;
    cajon.classList.remove("hojeando");
  };
  cajon.addEventListener("pointerup", soltar);
  cajon.addEventListener("pointercancel", soltar);

  cajon.addEventListener("keydown", (evento) => {
    const teclas = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1, PageDown: 5, PageUp: -5 };
    if (evento.key in teclas) ir(actual + teclas[evento.key]);
    else if (evento.key === "Home") ir(0);
    else if (evento.key === "End") ir(discos.length - 1);
    else if (evento.key === "Enter" || evento.key === " ") escuchar();
    else return;
    evento.preventDefault();
  });

  if (play) play.addEventListener("click", escuchar);
  pintar();
})();

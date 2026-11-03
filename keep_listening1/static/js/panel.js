/* ===========================================================================
 * Keep Listening - sala de escucha del panel
 * La prueba de prensa gira en el plato solo mientras suena.
 * Mientras se revisa, la bandeja principal se pausa para no pisarse.
 * =========================================================================== */
(function () {
  "use strict";

  const audio = document.getElementById("kl-escucha-audio");
  const disco = document.getElementById("kl-escucha-disco");
  if (!audio || !disco) return;

  window.KL.pagina(audio, (vida) => {
    audio.addEventListener("play", () => {
      disco.classList.add("girando");
      if (window.KLPlayer) window.KLPlayer.pausar();
    });
    ["pause", "ended"].forEach((tipo) => audio.addEventListener(tipo, () => disco.classList.remove("girando")));

    // Al irse de la página, la prueba deja de sonar.
    vida.alSalir(() => audio.pause());
  });
})();

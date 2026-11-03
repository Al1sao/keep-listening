/* ===========================================================================
 * Keep Listening - el torno de corte (subir un tema)
 * Al elegir el archivo, se decodifica en el navegador y su huella real se
 * graba en espiral sobre el disco, de afuera hacia adentro, como el corte de
 * un máster. La portada elegida es la etiqueta y el título se escribe en ella.
 * Nada sale de la computadora hasta que se envía el formulario.
 * =========================================================================== */
(function () {
  "use strict";

  const KL = window.KL;
  const lienzo = document.getElementById("kl-torno-lienzo");
  if (!lienzo) return;

  KL.pagina(lienzo, (vida) => {
    const $ = KL.util.$;
    const ctx = lienzo.getContext("2d");
    const estado = $("kl-torno-estado");
    const datos = $("kl-torno-datos");
    const titulo = $("kl-torno-titulo");
    const escuchar = $("kl-torno-escuchar");
    const campoTitulo = $("id_titulo");
    const MUESTRAS = 1400;
    const VUELTAS = 26;
    const DURACION_CORTE = 2600;
    let huella = null;
    let url = "";
    let reproductor = null;
    let lectura = 0; // cada archivo nuevo invalida la lectura anterior

    // Disco vacío: surcos finos y el filo del borde.
    function base() {
      const t = lienzo.width;
      const c = t / 2;
      ctx.clearRect(0, 0, t, t);
      ctx.fillStyle = "#0d0f0e";
      ctx.beginPath();
      ctx.arc(c, c, c - 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.035)";
      ctx.lineWidth = 1;
      for (let r = c * 0.36; r < c - 10; r += 5) {
        ctx.beginPath();
        ctx.arc(c, c, r, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // Espiral: cada muestra de la huella desplaza el surco hacia afuera según su volumen.
    function dibujar(hasta, colores) {
      base();
      if (!huella) return;
      const t = lienzo.width;
      const c = t / 2;
      const afuera = c - 14;
      const adentro = c * 0.38;
      const tope = Math.floor(hasta * MUESTRAS);
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.strokeStyle = colores.surco;
      ctx.shadowColor = colores.brillo;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      for (let i = 0; i < tope; i += 1) {
        const p = i / MUESTRAS;
        const angulo = p * VUELTAS * Math.PI * 2 - Math.PI / 2;
        const radio = afuera - p * (afuera - adentro) + huella[i] * 5.5;
        const x = c + Math.cos(angulo) * radio;
        const y = c + Math.sin(angulo) * radio;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
      // El cabezal de corte, donde va la espiral.
      if (hasta < 1 && tope > 0) {
        const p = tope / MUESTRAS;
        const angulo = p * VUELTAS * Math.PI * 2 - Math.PI / 2;
        const radio = afuera - p * (afuera - adentro);
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(c + Math.cos(angulo) * radio, c + Math.sin(angulo) * radio, 5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function cortar() {
      const inicio = performance.now();
      const duracion = KL.util.reduce ? 1 : DURACION_CORTE;
      // Los colores se leen una vez por corte, no en cada cuadro.
      const colores = { surco: KL.util.color("--kl-c1", 0.85), brillo: KL.util.color("--kl-c1", 0.6) };
      lienzo.parentElement.classList.add("cortando");
      vida.reloj("corte", (dt, ahora) => {
        const avance = Math.min(1, (ahora - inicio) / duracion);
        dibujar(avance, colores);
        if (avance < 1) return true;
        lienzo.parentElement.classList.remove("cortando");
        estado.textContent = "Máster cortado";
        return false;
      });
    }

    async function leer(buffer, nombre, peso) {
      const mia = (lectura += 1);
      estado.textContent = "Leyendo el audio…";
      try {
        const audio = await new OfflineAudioContext(1, 1, 44100).decodeAudioData(buffer);
        // Si mientras tanto se eligió otro archivo (o se salió de la página), esta lectura no vale.
        if (mia !== lectura || !vida.vigente()) return;
        const canal = audio.getChannelData(0);
        const paso = Math.max(1, Math.floor(canal.length / MUESTRAS));
        huella = new Float32Array(MUESTRAS);
        let maximo = 0.0001;
        for (let i = 0; i < MUESTRAS; i += 1) {
          let pico = 0;
          for (let k = i * paso; k < Math.min(canal.length, (i + 1) * paso); k += 8) pico = Math.max(pico, Math.abs(canal[k]));
          huella[i] = pico;
          maximo = Math.max(maximo, pico);
        }
        for (let i = 0; i < MUESTRAS; i += 1) huella[i] /= maximo;
        datos.textContent = [nombre, KL.util.formatear(audio.duration), peso].filter(Boolean).join(" · ");
        estado.textContent = "Cortando el máster…";
        cortar();
      } catch (error) {
        if (mia !== lectura || !vida.vigente()) return;
        huella = null;
        base();
        estado.textContent = "No pudimos leer ese archivo";
        datos.textContent = "Probá con mp3, wav, ogg, m4a o flac.";
      }
    }

    function pintarBoton(sonando) {
      escuchar.querySelector("i").className = sonando ? "bi bi-pause-fill" : "bi bi-play-fill";
      escuchar.querySelector("span").textContent = sonando ? "Pausar" : "Escuchar el corte";
    }

    function soltarAudio() {
      if (reproductor) reproductor.pause();
      reproductor = null;
      if (url) URL.revokeObjectURL(url);
      url = "";
    }

    // Archivo nuevo elegido (app.js avisa con kl:audio-elegido).
    vida.escuchar(document, "kl:audio-elegido", (evento) => {
      const campo = evento.detail;
      if (!campo || !campo.files || !campo.files.length) return;
      const archivo = campo.files[0];
      soltarAudio();
      url = URL.createObjectURL(archivo);
      escuchar.hidden = false;
      pintarBoton(false);
      archivo.arrayBuffer().then((buffer) => leer(buffer, archivo.name, `${(archivo.size / 1048576).toFixed(1)} MB`));
    });

    // Escuchar el corte sin subirlo (la bandeja se pausa para no pisarse).
    escuchar.addEventListener("click", () => {
      if (!url) return;
      if (!reproductor) {
        reproductor = new Audio(url);
        reproductor.addEventListener("ended", () => pintarBoton(false));
      }
      if (reproductor.paused) {
        if (window.KLPlayer) window.KLPlayer.pausar();
        reproductor.play().catch(() => {});
        pintarBoton(true);
      } else {
        reproductor.pause();
        pintarBoton(false);
      }
    });

    // Al irse de la página, el corte deja de sonar y se libera el archivo.
    vida.alSalir(soltarAudio);

    if (campoTitulo) {
      campoTitulo.addEventListener("input", () => {
        titulo.textContent = campoTitulo.value.trim().slice(0, 28) || "tu tema";
      });
    }

    // Editando: se muestra el máster actual.
    const actual = $("kl-torno-actual");
    base();
    if (actual && actual.dataset.url) {
      fetch(actual.dataset.url, { credentials: "same-origin", signal: vida.signal })
        .then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status)))))
        .then((buffer) => leer(buffer, "", ""))
        .catch(() => {});
    }
  });
})();

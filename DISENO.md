# Keep Listening — sistema de diseño: "Surco"

Todo en Keep Listening se comporta como un disco: **gira, tiene peso, tiene
lados, se toca con la mano y deja huella.** Este documento es la regla para lo
que se agregue: si algo nuevo no cumple estos principios, no entra.

## 1. Principios

1. **Materia.** Lo que se mueve tiene física: inercia, giro, frenado. Un
   disco no "aparece": sale de la funda. Un tema no "se pausa": el plato frena.
2. **Color prestado.** La base es negro de vinilo, sin tinte. El color lo pone
   el tema que suena: `ambiente.js` extrae la paleta de la portada y la publica
   en `--kl-c1`, `--kl-c2`, `--kl-c3`. Los componentes usan esas variables (con
   la lima de marca como respaldo cuando no suena nada).
3. **La música manda.** El movimiento sale del análisis del audio (`KL.nivel`),
   no de temporizadores decorativos. En silencio todo se calma.
4. **Primero se lee.** El texto siempre es legible (contraste ≥ 4.5:1), nada
   importante depende solo de la animación, y `prefers-reduced-motion` apaga
   el movimiento no esencial.
5. **Un solo reloj.** Toda animación por cuadro pasa por `KL.reloj`. Nada corre
   con la pestaña oculta ni cuando el elemento no se ve.

## 2. Tokens (`static/scss/abstracts/_variables.scss`)

| Token | Uso |
|---|---|
| `$kl-sup-0` … `$kl-sup-4` | Superficies neutras, de más profunda a más cercana |
| `$kl-linea` | Bordes y divisores |
| `--kl-c1` / `--kl-c2` / `--kl-c3` | Color del tema que suena (acento, secundario, detalle) |
| `$kl-menta` | Marca, cuando no suena nada |
| `$kl-rosa` | Me gusta |
| `--kl-pulso` / `--kl-medio` / `--kl-agudo` | Nivel del audio (0 a 1) para CSS |

Nada de grises escritos a mano: se usa la escala `$kl-sup-*`.

## 3. Movimiento

- Curva base: `cubic-bezier(.22, 1, .36, 1)` (sale rápido, llega suave).
- Duraciones: 180 ms para hover, 450–600 ms para entradas, 800–1000 ms para
  objetos con peso (discos que salen de la funda).
- 33⅓ rpm = 200°/s: todos los vinilos giran a esa velocidad (multiplicada por
  la velocidad real del audio).

## 4. Piezas

| Pieza | Archivo | Qué hace |
|---|---|---|
| Núcleo | `static/js/nucleo.js` | `KL.reloj` (rAF único), `KL.nivel` (audio), `KL.util` |
| Fondo vivo | `static/js/ambiente.js` | Degradado WebGL con la paleta de la portada; ondas con los golpes |
| La bandeja | `static/js/bandeja.js`, `layout/_reproductor.scss` | Plato con scratch, mapa del tema (huella + versos + estribillos), perilla |
| Tocadiscos | `static/js/reproductor.js` | Frenado y arranque con tono al pausar / reanudar |
| Ahora suena | `static/js/ahora.js`, `pages/_ahora.scss` | Hoja que sube; la portada vuela; modo letra con el disco al costado |
| Letra (túnel) | `static/js/karaoke.js`, `pages/_letra.scss` | Los versos viven en profundidad con el punto de fuga en el disco: el que suena al frente como afiche, la pila bajando al fondo, palabra fantasma, surcos, mapa de la letra con estribillos. Sin sincronía, página en columnas |
| Explorar (dial) | `musica/explorar.html`, `static/js/explorar.js`, `pages/_explorar.scss` | El catálogo es una banda de FM: se sintoniza con la banda, la perilla, la rueda o las flechas; estática entre estaciones; sintonía automática |
| Inicio | `musica/home.html`, `static/js/inicio.js`, `pages/_inicio.scss` | Disco del día (lado A / B, se da vuelta), juego "Tres segundos", lista de la sala, artistas, disquería, comunidad |
| Vinilo | `components/_vinilo.scss` | 6 ediciones (`data-estilo` 0–5) con `--disco-a` / `--disco-b` / `--portada` |
| Disquería | `pages/_disqueria.scss`, `static/js/tienda.js`, `tienda/portadas.py` | Portadas generadas por nombre, visor 2D / 3D |
| Navegación continua | `static/js/navegar.js`, `layout/_shell.scss` | Cambia solo el contenido: la música sigue sonando; View Transitions |
| Cuenta | `usuarios/_base_cuenta.html`, `pages/_sesion.scss`, `static/js/cuenta.js` | Etiqueta de vinilo con tu nombre; la contraseña es un vúmetro |
| Tu colección | `musica/mi_musica.html`, `static/js/coleccion.js` | Batea para hojear discos (rueda, arrastre o flechas) |
| Compra | `tienda/_pasos.html`, `pages/_tienda.scss` | Pasos A1–A3, ticket, prensado con la matriz grabada; el pedido recorre un surco |
| Torno de corte | `musica/subir_cancion.html`, `static/js/torno.js` | La huella real del archivo se graba en espiral; se escucha antes de subir |
| Ficha de un tema | `musica/detalle_cancion.html` | La portada es la funda; el disco sale y gira mientras suena |
| Consola (panel) | `panel/*.html`, `pages/_panel.scss`, `static/js/panel.js` | Canales con LED, medidores que laten con el audio, bus master de 14 días, test pressings que se aprueban con un sello |
| Errores | `404.html`, `500.html`, `pages/_errores.scss` | 404: el disco rayado que salta; 500: autónoma, sin base ni sesión |

## 5. Reglas de código

- **JS**: un módulo por pieza, en una IIFE con `"use strict"`. Nada global
  salvo `window.KL*`. Animaciones por `KL.reloj.agregar(nombre, fn)`; `fn`
  devuelve `false` para terminar. Los datos del servidor llegan con
  `json_script`, nunca interpolados en JS.
- **Scripts de página** (`data-pagina`): todo va dentro de
  `KL.pagina(raiz, (vida) => { … })`. Con `vida.escuchar`, `vida.reloj`,
  `vida.observar`, `vida.temporizador` y `vida.alSalir`, lo que se engancha se
  suelta solo cuando navegar.js avisa `kl:salir`; `vida.vigente()` después de
  un `await`. Helpers comunes en `KL.util`: `$`, `json`, `almacen`, `barajar`,
  `esLocal`, `color`/`rgb` (con caché) y `KLPlayer.pausar()` para que otro audio
  suene sin pisarse con la bandeja.
- **HTML dinámico**: con `textContent` / `createElement`. Si hace falta
  `innerHTML`, todo pasa por `KL.util.escapar`.
- **Colores del tema**: `tema(1)` / `tema(2, .4)` (abstracts/_funciones) en lugar
  de escribir `rgba(var(--kl-c1, …))`; los valores por defecto están en `:root`
  (base/_reset).
- **SCSS**: BEM (`kl-bloque__elemento--variante`), `@use "../abstracts" as *`,
  mobile first con `desde()` / `hasta()`. La columna central cambia de ancho
  según los paneles abiertos: los layouts internos usan flex con wrap o
  container queries (la consola: `@container consola`), no el ancho de la
  ventana. Un contenedor encierra a los `position: fixed`: los modales van
  fuera de él (`{% block fuera_de_consola %}`).
- **Números en CSS**: `style="--nivel: {{ x|unlocalize }}"` (`{% load l10n %}`);
  en español el decimal saldría con coma y la variable no valdría.
- **Giro de los discos**: una sola velocidad, `KL.GRADOS_POR_SEGUNDO` (JS) y
  `$kl-vuelta-disco` (CSS), que tienen que coincidir (90°/s = 4 s por vuelta).
- **Tests**: `python manage.py test` corre sin internet (`keep_listening1/test_runner.py`),
  con la caché del catálogo en memoria y un hasher rápido; lo de afuera se simula con `patch`.
- **Estados como recorrido**: pedidos y publicaciones exponen `recorrido()`
  y se dibujan con `.kl-recorrido`, la misma pieza en todo el sitio.
- **Íconos**: después de usar uno nuevo, `npm run iconos` (solo se compilan
  los que aparecen en el código).
- **Estáticos**: en templates, `{% estatico 'ruta' %}`: la versión se renueva
  sola.

## 6. Seguridad

- CSP con nonce (`keep_listening1/seguridad.py`): solo corren scripts propios.
  Un `<script>` inline nuevo necesita `nonce="{{ csp_nonce }}"`.
- Escuchar requiere sesión (`/api/preview/` responde 401 sin cuenta).
- Límite de pedidos a las APIs de afuera y de intentos de login.
- Lo que llega del front (me gusta, duración) se valida en el servidor:
  dominios permitidos, largos, tipos.
- Moderación: canciones y álbumes de artistas entran ocultos y vuelven a
  revisión si se editan; lo publica el equipo desde la consola.
- Límites por IP (`KL_PROXIES` = cantidad de proxies propios delante, para leer
  la IP real de X-Forwarded-For) y, en los adelantos, por cuenta.

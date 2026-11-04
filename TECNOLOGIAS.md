# Tecnologías de Keep Listening

Acá contamos con qué armamos Keep Listening y por qué elegimos cada cosa. La idea desde el principio fue usar pocas herramientas y conocerlas bien, así que no hay ningún framework de frontend ni servicios en la nube. Todo corre en una sola máquina con un comando.

## Python y Django

El backend es Django 5.2 (en `requirements.txt` pedimos `>=5.2.17,<6`). Lo elegimos porque es la versión LTS y porque ya viene con casi todo lo que necesitábamos: usuarios, sesiones, formularios, panel de administración y protección CSRF. En el Dockerfile usamos Python 3.12, pero el proyecto está pensado para andar desde la 3.10 hasta la 3.14.

El proyecto está dividido en cuatro apps:

| App | Qué tiene |
|---|---|
| `usuarios` | registro, login (con usuario o con correo), perfil, bloqueo de cuentas |
| `musica` | géneros, álbumes, canciones, favoritos, reproducciones, búsqueda, letras |
| `tienda` | carrito, checkout, pedidos y pagos |
| `panel` | moderación de lo que suben los usuarios, usuarios y tienda |

Del ORM usamos casi todo lo básico, y donde más nos sirvió fue en las pantallas con muchas tarjetas: con `select_related` y `annotate` evitamos hacer una consulta por cada canción. Los templates son los de Django, con una carpeta por app y un `base.html` común. Los formularios (`RegistroForm`, `SubirCancionForm` y otros) hacen las validaciones, por ejemplo que la contraseña tenga mayúscula y número.

La autenticación es la de `django.contrib.auth`. Le cambiamos el modelo de usuario para agregarle el rol (usuario o administrador) y el bloqueo con motivo. Hay un middleware propio que cierra la sesión de alguien bloqueado aunque ya estuviera logueado.

El pago es una simulación. Valida la tarjeta con el algoritmo de Luhn, descuenta stock y guarda solo los últimos cuatro dígitos. No conectamos ninguna pasarela real y no lo vamos a hacer pasar por otra cosa en la entrega.

## SQLite

Usamos SQLite, la que viene por defecto. Para un proyecto que corre local en un contenedor no hacía falta un servidor de base de datos aparte, y así cualquiera lo levanta sin instalar nada. Una cosa que nos costó entender fue la concurrencia: dos compras al mismo tiempo del mismo carrito podían cobrarse dos veces. Lo resolvimos en `settings.py` con `transaction_mode: IMMEDIATE`, que toma el lock de escritura apenas empieza la transacción, y con un `timeout` de 20 segundos. Para trabajar en la compu y para la entrega en ZIP sigue siendo SQLite.

## PostgreSQL (la versión publicada)

Cuando publicamos la página en Render nos pasó algo que no esperábamos: la base SQLite vivía adentro del contenedor y se borraba cada vez que el servidor se reiniciaba o se publicaba una versión nueva, así que las compras y las cuentas desaparecían. Lo solucionamos con una base PostgreSQL gratuita de Render. En `settings.py`, si existe la variable `DATABASE_URL`, Django usa PostgreSQL; si no, sigue con SQLite. El código no tuvo que cambiar porque todo pasa por el ORM, pero aprendimos que PostgreSQL es más estricto: no deja guardar un texto más largo que el campo ni el carácter nulo, cosas que SQLite dejaba pasar. Para conectarse usa `psycopg`, que está en `requirements.txt` solo para las versiones de Python que lo necesitan.

## django-allauth

Para entrar con otras plataformas usamos django-allauth (`>=65,<66`, con el extra `socialaccount`). Están activados los proveedores de Spotify, Apple, Google (que es lo que usamos para YouTube Music) y SoundCloud: elegimos solo plataformas de música, porque entrar con GitHub o Microsoft a un sitio para escuchar temas no tenía mucho sentido. Escribir cada OAuth a mano nos parecía una receta para equivocarnos en algo de seguridad.

Cada botón aparece solo si cargás las claves de esa plataforma en el `.env` (`KL_<PLATAFORMA>_ID` y `KL_<PLATAFORMA>_SECRET`). Sin claves el botón no se muestra, o se ve apagado en desarrollo. Allauth se encarga de ir y volver de la plataforma; el alta del usuario y el enlace con una cuenta existente por correo lo resolvemos nosotros en `usuarios`.

## Pillow, WhiteNoise y Gunicorn

Pillow es lo que necesita Django para los campos de imagen, o sea las portadas de canciones y álbumes. Pedimos la versión 12 o más nueva porque ya trae paquetes listos para Python 3.14.

WhiteNoise sirve los archivos estáticos desde la propia aplicación, así que no hace falta un nginx para ver el CSS y el JS. Lo usamos con `CompressedManifestStaticFilesStorage`, que los comprime y les pone un hash en el nombre para que el navegador no use versiones viejas.

Gunicorn está en `requirements.txt` para servir fuera de desarrollo. En la compu, el `docker-compose.yml` levanta el sitio con `runserver`, el servidor de desarrollo de Django. En Render, en cambio, `render.yaml` pone `KL_SERVIDOR=gunicorn` y el `entrypoint.sh` arranca Gunicorn con dos procesos en el puerto que da la plataforma.

## JavaScript sin frameworks

El frontend es JavaScript común, sin React, jQuery ni nada parecido. Son unos veinte archivos en `static/js/`, cada uno con una responsabilidad: `reproductor.js` (el audio, la cola y los atajos), `navegar.js`, `karaoke.js` (la letra), `escena.js` (el vinilo 3D), `ambiente.js` (el fondo), `tienda.js` y varios más. Optamos por no usar un framework porque nos interesaba entender qué hace el navegador por debajo, y también porque así no hay build de JavaScript.

Lo que más nos gustó armar:

- **Navegación sin recargar.** `navegar.js` intercepta los links internos, pide el HTML con `fetch`, lo procesa con `DOMParser`, cambia el contenido y actualiza la URL con `history.pushState`. Hicimos esto para que la música no se corte al cambiar de página. Si algo sale raro (otro origen, el admin, un error del servidor) deja que el navegador recargue como siempre.
- **Web Audio API.** El reproductor engancha el elemento `<audio>` a un `AnalyserNode` para leer los graves, medios y agudos en cada cuadro. Con eso se mueve el "pulso" de la interfaz.
- **Canvas 2D.** Lo usamos para la huella del tema en la bandeja, el espectro, la estática del dial de Explorar, la letra y el torno de subida, donde el archivo se decodifica en el navegador y se dibuja su forma de onda en espiral sobre un disco.
- **WebGL.** El fondo que cambia con los colores de la portada (`ambiente.js`) y el estudio con el vinilo y las partículas (`escena.js`) usan WebGL a mano, sin Three.js. Nos costó bastante, sobre todo con los shaders. Los dos tienen una alternativa en CSS si el navegador no soporta WebGL, y respetan la preferencia de "reducir movimiento".

## SCSS, Dart Sass y Bootstrap

Los estilos están escritos en SCSS, en `static/scss/`, con la estructura 7-1 (abstracts, base, layout, components, pages). Se compilan con Dart Sass (`sass` `^1.83` en `package.json`; en nuestra carpeta quedó la 1.102). Usamos `@use` y `@forward` en lo nuestro y los parciales declaran de qué dependen. Hay una excepción que conviene decir: el archivo `_bootstrap-base.scss` importa los módulos de Bootstrap con `@import`, porque es como lo expone Bootstrap 5.3, y por eso se pasa `--quiet-deps` en los scripts para que Sass no llene la consola de avisos.

De Bootstrap 5 (`^5.3.8`) no usamos todo. Del SCSS importamos solo `root`, `reboot`, `type`, `transitions`, `dropdown`, `close`, `modal`, `offcanvas` y el helper `visually-hidden`. La grilla, los botones y las tarjetas son nuestros. Del JavaScript sí cargamos el bundle (`bootstrap.bundle.min.js`), que se usa, por ejemplo, para el modal del motivo de rechazo en el panel. Las variables de Bootstrap (colores, radios, tipografías) las configuramos con `@forward ... with` en un solo archivo, así el framework toma nuestra paleta verde y crema.

Bootstrap Icons (`^1.13.1`) los recortamos. El set completo son unos 2000 íconos y el sitio usa menos de cien. El script `tools/iconos.mjs` busca qué íconos aparecen en templates, JS y Python, genera `_iconos-usados.scss` y arma una fuente `bootstrap-icons-kl.woff2` solo con esos. Para recortar la fuente usa **fonttools** (con **brotli**), que se instalan con `pip install fonttools brotli`. Es la única parte del proyecto donde Python y Node se cruzan, y por eso el resultado queda commiteado en el repo: el build de Docker no ve los templates y no podría regenerarlo.

## Fuentes: Nunito y Syne

Nunito es la tipografía del texto y Syne la de los títulos. Las bajamos con los paquetes `@fontsource/nunito` y `@fontsource/syne` y copiamos solo los pesos que usamos (Nunito en 400, 600, 700 y 800, Syne en 600, 700 y 800, todos latin y woff2) a `static/fonts/`. No usamos Google Fonts ni ningún CDN, así que el sitio se ve igual sin conexión.

## Node y npm

Node está solo para compilar los estilos. No hay servidor Node ni bundler de JS. Los scripts de `package.json` son `npm run css`, `css:min`, `css:watch`, `vendor` (copia el JS de Bootstrap y las fuentes a `static/`), `iconos` y `build`, que los junta. El CSS compilado no se edita a mano y se regenera siempre desde el SCSS. Las dependencias de runtime son las de Bootstrap, los íconos y las fuentes; Sass es la única de desarrollo.

## Docker y docker-compose

Con `docker compose up --build` se arma todo. El Dockerfile tiene dos etapas: la primera usa `node:22-alpine`, hace `npm ci` y `npm run build` para generar el CSS; la segunda parte de `python:3.12-slim`, instala los requirements y copia el CSS ya compilado. De esa forma la imagen final no lleva Node. Corre con un usuario sin privilegios (`keep`) y no con root.

El `entrypoint.sh` aplica las migraciones, carga los datos de ejemplo si `CARGAR_DATOS` está en 1, recolecta los estáticos y arranca. El compose define dos volúmenes, uno para la base SQLite y otro para los archivos subidos, así los datos sobreviven a un `docker compose down`. También tiene un healthcheck que le pega a `/health/`. Un detalle que nos hizo perder un rato: el bit de ejecución del `entrypoint.sh` se pierde cuando se construye desde Windows, y por eso lo marcamos con `chmod +x` dentro del Dockerfile.

## APIs externas

Usamos dos y las dos son públicas, sin clave:

- **iTunes Search / Apple (itunes.apple.com).** La música que suena es una selección de hip hop y pop (`musica/seleccion.py`). Cada tema se busca en la API pública de Apple y se reproduce su adelanto oficial de 30 segundos. No guardamos audio en el proyecto. Como Apple limita las consultas por minuto, el resultado se cachea una semana en `.cache/catalogo/`.
- **LRCLIB (lrclib.net).** De ahí sale la letra de cada tema, incluida la versión sincronizada que se usa en el modo "túnel". Se pide en el momento y no se copia al repositorio. Si LRCLIB no la tiene, la pantalla queda en modo sin sincronía. Como el adelanto de Apple es un tramo de 30 segundos de algún punto del tema, hay un comando, `calcular_desfases`, que usa Whisper (reconocimiento de voz local, que se instala aparte y no es dependencia del proyecto) para ubicar ese tramo en la letra sincronizada y guardar el desfase en `musica/desfases.json`.

Los tests no dependen de estas APIs: `python manage.py test` corre sin internet.

## Git

Usamos Git para el control de versiones, todo sobre `main`, y un `.gitignore` que deja afuera `node_modules`, `media/`, el `.env` y la clave secreta de desarrollo. El CSS compilado sí lo subimos, para que el proyecto se pueda correr sin instalar Node.

## Render y GitHub Pages

La página está publicada en Render (plan gratuito) desde el mismo repositorio: lee `render.yaml`, construye la imagen con el `Dockerfile` y vuelve a publicar sola cada vez que subimos un cambio a GitHub. Ahí corre con `DJANGO_DEBUG=0`, una clave secreta que genera Render y los datos de ejemplo cargados al arrancar. La contraseña del administrador no está en el código: se carga en Render como `KL_ADMIN_PASSWORD`. La documentación (manual, informe y capturas) está en GitHub Pages, desde la carpeta `docs/`.

## Resumen

| Tecnología | Para qué la usamos |
|---|---|
| Python 3.12 y Django 5.2 | Backend: modelos, vistas, templates, formularios, autenticación y admin |
| SQLite | Base de datos, con transacciones `IMMEDIATE` para evitar cobros dobles |
| django-allauth | Entrar con Spotify, Apple, Google (YouTube Music) y SoundCloud |
| Pillow | Portadas e imágenes subidas |
| WhiteNoise | Servir los archivos estáticos desde la aplicación |
| Gunicorn | Servidor de la versión publicada en Render (en local corre `runserver`) |
| PostgreSQL + psycopg | Base de datos de la versión publicada |
| Render | Publicación de la página, con `render.yaml` |
| GitHub Pages | Publicación de la documentación |
| JavaScript nativo | Reproductor, navegación sin recargar, buscador, carrito y panel |
| Web Audio API | Analizar el audio para el pulso de la interfaz |
| Canvas 2D y WebGL | Bandeja, torno, letra, fondo vivo y vinilo 3D |
| SCSS y Dart Sass | Todos los estilos, compilados a CSS |
| Bootstrap 5.3 | Solo reboot, tipografía, modal, dropdown, offcanvas y su JS |
| Bootstrap Icons | Íconos, recortados a los que realmente usamos |
| Nunito y Syne | Tipografías de texto y de títulos, servidas desde `static/` |
| Node y npm | Solo para compilar los estilos y copiar Bootstrap y las fuentes |
| fonttools y brotli | Recortar la fuente de íconos (`tools/iconos.mjs`) |
| Docker y docker-compose | Levantar todo con un comando, con volúmenes para la base y los archivos |
| API de iTunes / Apple | Buscar los temas y reproducir el adelanto de 30 segundos |
| LRCLIB | Letras, con versión sincronizada |
| Git | Control de versiones |

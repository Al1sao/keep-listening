# Keep Listening

Plataforma web para **escuchar, guardar, publicar y comprar musica**, desarrollada con Django + SQLite (PostgreSQL en la versión publicada),
estilos en **SCSS modular sobre Bootstrap 5** y ejecucion local con **Docker**.

Proyecto: Keep listening · Empresa: TecnoPlus · Taller de Construcción de Software, 6.º año.

**Integrantes: Sophia Benitez y Alí Pérez.**

## Documentación de la entrega

| Documento | Dónde |
|---|---|
| Manual de usuario (PDF) | [docs/Manual_de_usuario_Keep_Listening.pdf](docs/Manual_de_usuario_Keep_Listening.pdf) |
| Informe final del proyecto (PDF) | [docs/Informe_Keep_Listening.pdf](docs/Informe_Keep_Listening.pdf) |
| Base de datos exportada (.sql) | [base_de_datos/keep_listening.sql](base_de_datos/keep_listening.sql) |
| Tecnologías usadas y por qué | [TECNOLOGIAS.md](TECNOLOGIAS.md) |
| Sistema de diseño | [DISENO.md](DISENO.md) |
| Versión web de la documentación | <https://al1sao.github.io/keep-listening/> |
| **Página funcionando en línea** | <https://keep-listening.onrender.com> (ver "Versión en línea" más abajo) |

---

## Tecnologías utilizadas

- **Backend:** Python 3 y Django 5.2 (vistas, formularios, modelos, autenticación y panel de administración).
- **Base de datos:** SQLite en local y PostgreSQL en la versión publicada en Render.
- **Frontend:** plantillas HTML de Django, SCSS compilado con Dart Sass sobre Bootstrap 5, y JavaScript nativo
  (sin React ni jQuery). Web Audio API para analizar el sonido y WebGL para el fondo animado.
- **Librerías de Python:** django-allauth (entrar con plataformas de música), Pillow (imágenes),
  WhiteNoise (archivos estáticos) y Gunicorn (servidor).
- **Servicios externos:** API pública de Apple Music (adelantos de 30 s) y LRCLIB (letras sincronizadas).
- **Herramientas:** Git y GitHub, Docker y Docker Compose, Node.js + npm (solo para recompilar los estilos).

El detalle de cada una está en [TECNOLOGIAS.md](TECNOLOGIAS.md).

## Herramientas necesarias para ejecutarlo

| Herramienta | Versión | ¿Obligatoria? |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.10 a 3.14 | Sí (si no se usa Docker) |
| [Git](https://git-scm.com/downloads) | cualquiera | Para clonar el repositorio (o descargar el ZIP) |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | reciente | Solo para la opción A |
| [Node.js](https://nodejs.org/) | 20 o superior | No: el CSS ya viene compilado. Solo hace falta para modificar los estilos |
| Conexión a internet | — | Para que suene la música y aparezcan las letras |

---

## 1. Como ejecutarlo

### Opcion A - Docker (recomendada)

```bash
docker compose up --build
```

Al terminar el build el contenedor:

1. aplica las migraciones sobre SQLite,
2. carga los datos de ejemplo (administrador, usuario, generos y albumes de la tienda),
3. compila el SCSS (se hace en la etapa de build con Dart Sass) y recolecta los estaticos,
4. levanta el servidor en <http://localhost:8000>.

Para arrancar **sin** datos de ejemplo: en `docker-compose.yml` poner `CARGAR_DATOS: "0"`.

La base y los archivos subidos viven en volumenes (`sqlite_datos`, `media_datos`), asi que sobreviven
a `docker compose down`. Para empezar de cero:

```bash
docker compose down -v && docker compose up --build
```

### Opcion B - Sin Docker (Windows, paso a paso)

En una terminal (PowerShell), dentro de la carpeta del proyecto:

```powershell
cd keep_listening1
python -m venv .venv
.venv\Scripts\activate
pip install -r ..\requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Y abrir <http://127.0.0.1:8000>. Si el puerto 8000 está ocupado: `python manage.py runserver 8001`.

En Linux o macOS es igual, cambiando la activación por `source .venv/bin/activate`.

El CSS compilado ya viene en el repositorio. Solo si se modifican los estilos (`static/scss/`):

```bash
npm install          # bootstrap, bootstrap-icons, las fuentes y el compilador sass
npm run build        # compila SCSS -> static/css/ y copia iconos + js de Bootstrap
```

Durante el desarrollo de los estilos: `npm run css:watch`.

### Base de datos

`python manage.py migrate` + `python manage.py seed` crean la base desde cero con los datos de ejemplo.
Para usar en cambio **la copia exportada** de la base con la que trabajamos
([base_de_datos/keep_listening.sql](base_de_datos/keep_listening.sql)), en lugar de esos dos comandos:

```powershell
cd keep_listening1
python -c "import sqlite3; c = sqlite3.connect('db.sqlite3'); c.executescript(open('../base_de_datos/keep_listening.sql', encoding='utf-8').read())"
python manage.py migrate   # no aplica nada nuevo: solo confirma que la base está al día
```

(Si ya existe un `db.sqlite3`, borrarlo antes.) Con la herramienta `sqlite3` instalada también sirve
`sqlite3 db.sqlite3 < ../base_de_datos/keep_listening.sql`.

### Cuentas creadas por `seed`

| Rol | Usuario | Contrasena |
|-----|---------|------------|
| Administrador | `admin` | `Admin1234` |
| Usuario | `sophia` | `Usuario1234` |
| Artistas extra | `ali`, `lunaverde`, `timbre` | `Usuario1234` |

Tarjeta de prueba para el pago: `4111 1111 1111 1111`, vencimiento `12/30`, CVV `123`.

Las cuentas de prueba se muestran en la pantalla de login **solo cuando `DJANGO_DEBUG=1`**.

### Variables de entorno

Copiar `.env.example` a `.env` y ajustarlo. Las que importan:

| Variable | Para que sirve |
|---|---|
| `DJANGO_SECRET_KEY` | Obligatoria con `DJANGO_DEBUG=0`: sin ella el proyecto no arranca, a proposito. En desarrollo se genera sola y se guarda en `.secret_key` para que los reinicios no cierren las sesiones abiertas. |
| `DJANGO_DEBUG` | `1` en desarrollo, `0` para publicar (activa HTTPS obligatorio, HSTS y cookies seguras). |
| `DJANGO_ALLOWED_HOSTS` | Dominios permitidos, separados por coma. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origenes con esquema, separados por coma. |
| `SQLITE_PATH` | Ruta del archivo de base de datos. |
| `CARGAR_DATOS` | `1` carga los datos de ejemplo al arrancar el contenedor; `0` no. |
| `DATABASE_URL` | Si está, se usa PostgreSQL (`postgresql://usuario:clave@host:puerto/base`) en lugar de SQLite. La pone Render. |
| `KL_DEMO` | `1` permite cargar los datos de ejemplo con `DJANGO_DEBUG=0` (sitio de demostración). |
| `KL_ADMIN_PASSWORD` | Contraseña del usuario `admin` en la demo publicada (reemplaza la de ejemplo). |
| `KL_SERVIDOR` | `gunicorn` arranca Gunicorn en el puerto `PORT` en lugar de `runserver`. |
| `KL_SERVIR_MEDIA` | `1` hace que Django sirva los archivos subidos fuera de desarrollo (cuando no hay nginx). |
| `KL_PROXIES` | Cuántos proxies de confianza hay delante, para leer la IP real en los límites de pedidos. |
| `KL_CACHE_DIR` | Carpeta de la caché de disco del catálogo (por defecto `.cache/catalogo`). |

Generar una clave:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

---

### Versión en línea (Render)

La página también está publicada en <https://keep-listening.onrender.com>, en el plan gratuito de
[Render](https://render.com). Render construye la imagen con el mismo `Dockerfile` y toma la configuración
de [render.yaml](render.yaml): `DJANGO_DEBUG=0`, clave secreta generada por Render, gunicorn como servidor y
los datos de ejemplo cargados al arrancar (`KL_DEMO=1`). La contraseña del usuario `admin` no está en el
repositorio: se carga en Render como `KL_ADMIN_PASSWORD`.

- La base es **PostgreSQL** (gratuita en Render, declarada en `render.yaml`): las cuentas y las compras
  se conservan aunque el servicio se reinicie o se publique una versión nueva. En local se sigue usando SQLite.
- Las bases gratuitas de Render vencen a los 30 días de creadas; después se puede crear otra desde el panel.
- En el plan gratuito el servicio se duerme tras unos minutos sin uso: la primera visita tarda cerca de un
  minuto.
- Para publicarlo en otra cuenta: <https://render.com/deploy?repo=https://github.com/Al1sao/keep-listening>.

### Entrar con Spotify, Apple Music, YouTube Music o SoundCloud

El login y el registro tienen botones para entrar con esas plataformas
(django-allauth). Cada una se activa al cargar sus claves:

1. Copiar `.env.example` a `.env` (en la carpeta del proyecto, junto a `docker-compose.yml`).
2. Crear la app en la consola de la plataforma (el `.env.example` dice dónde) y
   cargar como URL de retorno `http://localhost:8000/auth/<plataforma>/login/callback/`
   (`spotify`, `apple`, `google`, `soundcloud`).
3. Completar `KL_<PLATAFORMA>_ID` y `KL_<PLATAFORMA>_SECRET` y reiniciar el servidor.

Sin claves, los botones no aparecen (en desarrollo se ven apagados). Quien entra
por primera vez queda registrado solo; si el correo ya tenía cuenta, entra a esa.

## 2. Casos de uso implementados

| Caso de uso | Donde vive | Pantallas |
|-------------|-----------|-----------|
| 1. Registro de usuario | `usuarios/forms.py` (`RegistroForm`), `usuarios/views.registro` | `/cuenta/registro/` |
| 2. Inicio de sesion | `usuarios/forms.LoginForm` (acepta usuario **o** correo) | `/cuenta/login/` |
| 3. Reproduccion de musica | `musica/views.registrar_reproduccion` + `static/js/reproductor.js` | reproductor fijo en todo el sitio |
| 4. Guardar canciones | `musica/views.toggle_favorito` (AJAX), modelo `Favorito` | `/mi-musica/` |
| 5. Publicar canciones | `musica/forms.SubirCancionForm`, estado `PENDIENTE` | `/subir/`, `/mis-publicaciones/` |
| 6. Compra de albumes | app `tienda`: carrito, checkout, pago y pedido | `/tienda/`, `/tienda/carrito/`, `/tienda/checkout/` |
| 7. Administracion de contenido | app `panel` (aprobar / modificar / eliminar) | `/panel/` |

### Requisitos de usuario (1 a 13 del informe)

1. Registrarse · 2. Iniciar sesion · 3. Cargar correo al registrarse — formulario de registro con
   validacion de mayuscula y numero en la contrasena (mockup de REGISTRO).
4. Reproducir musica publicada — reproductor con cola, aleatorio, repetir, volumen y barra de progreso.
5. Guardar favoritas · 6. Ver nombre y genero de cada guardada — `/mi-musica/`, pestana "Canciones guardadas".
7. Publicar canciones · 8. Cargar nombre, genero, album/sencillo y portada — formulario de subida con
   vista previa de portada y arrastrar-y-soltar del audio.
9. Ver albumes disponibles · 10. Comprarlos en fisico o digital — tienda con filtros por formato y genero.
11. Agregar al carrito · 12. Completar la compra con datos de tarjeta — carrito AJAX y checkout con
   validacion de tarjeta (algoritmo de Luhn, vencimiento y CVV).
13. Control del administrador sobre lo que publica — cola de aprobacion con motivo de rechazo visible
   para el autor en "Mis publicaciones".

### Requisitos no funcionales

- **Facil de usar**: navegacion identica al mapa de navegacion del informe (Inicio, Explorar, Mi musica,
  Subir, Tienda, Carrito, Panel).
- **Proteccion de datos**: contrasenas con hash de Django, CSRF en todos los formularios, permisos por
  rol, y del pago **solo se guardan los ultimos 4 digitos** de la tarjeta.
- **Rendimiento**: consultas con `select_related` / `annotate`, paginacion, imagenes con `loading="lazy"`
  y CSS minificado (`styles.min.css`).
- **Compatible con computadora y celular**: layout responsivo (grillas fluidas, menu lateral y
  reproductor adaptado a pantallas chicas).

---

## 3. Estructura del proyecto

```
Keep_listening/
├── docker-compose.yml          # servicio web + volumenes para SQLite y media
├── Dockerfile                  # etapa 1: SCSS con Node · etapa 2: Django
├── entrypoint.sh               # migrate + seed + collectstatic + runserver
├── requirements.txt
└── keep_listening1/
    ├── manage.py
    ├── package.json            # bootstrap, bootstrap-icons y sass
    ├── keep_listening1/        # settings, urls, wsgi, asgi
    ├── usuarios/               # modelo Usuario (rol), registro, login, perfiles
    ├── musica/                 # Genero, Album, Cancion, Favorito, Reproduccion
    ├── tienda/                 # Carrito, CarritoItem, Pedido, PedidoItem, Pago
    ├── panel/                  # panel de administracion (moderacion, usuarios, tienda)
    ├── templates/              # base + partials + una carpeta por app
    └── static/
        ├── scss/               # arquitectura 7-1 (ver abajo)
        ├── css/                # CSS compilado (no se edita a mano)
        ├── js/app.js           # AJAX: favoritos, carrito, buscador, moderacion
        └── js/reproductor.js   # reproductor de audio
```

### Modelo de datos (segun el diagrama entidad-relacion)

- `Usuario` (rol USUARIO/ADMIN, correo unico, bloqueo con motivo)
- `Genero`, `Album` (tipo, formato de disco, precios digital y fisico, stock)
- `Cancion` (genero, tipo album/sencillo, portada, audio, **estado** pendiente/aprobada/rechazada)
- `Favorito` (usuario + cancion, unico), `Reproduccion` (historial)
- `Carrito` → `CarritoItem` (album + formato + cantidad + precio unitario)
- `Pedido` → `PedidoItem` y `Pago` (titular, ultimos 4 digitos, vencimiento, estado)

---

## 4. Los estilos (SCSS)

Arquitectura **7-1** sobre Bootstrap 5, en `static/scss/`:

```
abstracts/   _variables.scss   paleta verde/crema de los mockups
             _bootstrap.scss   Bootstrap 5 configurado con esa paleta (@forward ... with)
             _iconos.scss      Bootstrap Icons apuntando a static/fonts/
             _index.scss       fachada: lo que importan los parciales
             _funciones.scss   tema(), fluido()
             _mixins.scss      desde()/hasta(), tarjeta(), grilla(), fila-scroll(), boton()...
base/        reset, tipografia fluida y utilidades generadas con @each / @for
layout/      contenedores, header, reproductor, footer
components/  botones, tarjetas, formularios, buscador, badges/tablas/alertas/paginacion
pages/       auth, musica, tienda, panel, perfil
styles.scss  orquesta todo (variables -> bootstrap -> el resto)
```

Se usa el sistema de modulos de Dart Sass (`@use` / `@forward`), no `@import`, que quedo obsoleto
y desaparece en Dart Sass 3. Cada parcial declara de que depende con `@use "../abstracts" as *;` en
lugar de confiar en el orden de los imports, y Bootstrap se configura en un unico lugar
(`abstracts/_bootstrap.scss`). Las utilidades `.kl-bg-*`, `.kl-mt-*` y `.kl-radio-*` se generan con
bucles, y los breakpoints se manejan con los mixins `desde()` / `hasta()`.

Comandos: `npm run css` (desarrollo), `npm run css:min` (minificado), `npm run css:watch`.

El CSS de `static/css/` es **generado** por `npm run build` y no se edita a mano (el fuente es
`static/scss/`). Se incluye compilado en el repositorio para que el proyecto se pueda ejecutar sin
instalar Node.

---

## 5. Lo dinamico (sin recargar la pagina)

- **Reproductor** fijo con cola, siguiente/anterior, aleatorio, repetir, volumen, barra de progreso
  arrastrable, atajos de teclado (espacio, shift+flechas) y registro de reproducciones por AJAX.
- **Favoritos**: el corazon se sincroniza en todas las tarjetas de la pagina y en el reproductor.
- **Buscador en vivo** en la barra superior (canciones, albumes y artistas mientras escribis).
- **Carrito**: agregar, cambiar cantidades y eliminar por AJAX; el total y el contador del header se
  actualizan solos.
- **Checkout**: mascaras de tarjeta, vencimiento y CVV con tarjeta visual que se completa al escribir.
- **Panel**: aprobar o rechazar (con modal de motivo) sin recargar; las tarjetas desaparecen al resolverse.
- **Formulario de subida**: arrastrar y soltar el audio, vista previa de la portada y campos de album
  que aparecen solo si la cancion pertenece a un album.

---

## 6. Verificacion

```bash
cd keep_listening1
python manage.py test                    # registro, login, favoritos, publicación,
                                         # compra, panel, seguridad y un recorrido de
                                         # todas las páginas; corre sin internet

# Revision de configuracion para publicar el sitio (debe salir sin avisos)
DJANGO_DEBUG=0 DJANGO_SECRET_KEY=una-clave-larga python manage.py check --deploy
```

Con Docker: `docker compose exec web python manage.py test`.

---

## 7. Notas

- El pago es una **simulacion** local (no hay pasarela real): valida la tarjeta, crea el pedido,
  descuenta stock y marca el pago como aprobado, tal cual el diagrama de secuencia.
- **La música que suena es una selección de hip hop y pop famoso** (`musica/seleccion.py`): cada tema
  se busca en la API pública de Apple y suena su **adelanto oficial de 30 segundos**. No se guarda
  audio en el proyecto. El resultado se guarda una semana en `.cache/catalogo/` porque Apple limita
  las consultas por minuto. Para cambiar los temas, editar la lista `ESCENAS`.
- El seed crea usuarios, géneros y los álbumes de la tienda. Los temas de prueba en WAV solo se
  generan con `python manage.py seed --con-canciones`.
- `python manage.py limpiar_media` borra los archivos de `media/` que ningún registro usa
  (`--dry-run` para ver la lista antes).
- **No se usan CDNs**: Bootstrap 5, sus iconos y la tipografia Nunito estan servidos desde
  `static/`, asi que el sitio funciona igual sin conexion a internet.
- El frontend es unicamente **Bootstrap 5 + SCSS propio + JavaScript nativo**: no hay React, jQuery
  ni ninguna otra libreria.

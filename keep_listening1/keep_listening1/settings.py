"""
Configuración de Django para el proyecto Keep Listening.

Proyecto: Keep listening  -  Empresa: TecnoPlus
Base de datos: SQLite  -  Ejecución: Docker (ver docker-compose.yml) o runserver

La configuración sensible se toma del entorno; ver .env.example y README.md.
"""

import os
from pathlib import Path

from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _leer_env(ruta):
    """Carga un .env simple (CLAVE=valor por línea) sin pisar lo que ya está en el
    entorno: así las claves de Google, Apple, ... se configuran en un archivo."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valor = valor.split(" #", 1)[0].strip().strip('"').strip("'")
        if valor:
            os.environ.setdefault(clave.strip(), valor)


_leer_env(BASE_DIR.parent / ".env")

# Después de leer el .env: arma las plataformas de inicio de sesión con sus claves.
from usuarios import sociales  # noqa: E402

# --------------------------------------------------------------------------
# Seguridad
# --------------------------------------------------------------------------
# Sin la variable, apagado: un despliegue que la olvide no queda en modo debug.
# `manage.py` la enciende para el desarrollo local (runserver, tests, seed).
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

# La clave nunca viaja en el codigo: se toma del entorno (ver .env.example).
# En desarrollo, si no esta definida se genera una al vuelo; en producción
# faltar la variable es un error, no un valor por defecto adivinable.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # En desarrollo la clave se genera sola, pero se guarda en disco: si se
        # generara en cada arranque, cada reinicio invalidaria las sesiones
        # abiertas y el navegador mostraria "Session data corrupted".
        from django.core.management.utils import get_random_secret_key

        archivo_clave = BASE_DIR / ".secret_key"
        if archivo_clave.exists():
            SECRET_KEY = archivo_clave.read_text(encoding="utf-8").strip()
        if not SECRET_KEY:
            SECRET_KEY = get_random_secret_key()
            archivo_clave.write_text(SECRET_KEY, encoding="utf-8")
    else:
        raise ImproperlyConfigured(
            "Falta DJANGO_SECRET_KEY. Generala con: python -c "
            '"from django.core.management.utils import get_random_secret_key as k; print(k())"'
        )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,[::1]"
    ).split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origen.strip()
    for origen in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origen.strip()
]

# Publicado en Render (render.yaml): el dominio público llega en esta variable.
if host_render := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(host_render)
    CSRF_TRUSTED_ORIGINS.append(f"https://{host_render}")

# Cabeceras y cookies endurecidas: solo se activan fuera de desarrollo,
# porque exigen HTTPS y romperian el entorno local sobre http://.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 anio
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # El chequeo de salud del hosting entra por http interno: no se redirige.
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]

# Cuántos proxies de confianza hay delante (nginx, balanceador). Con 0 se usa
# REMOTE_ADDR; con 1 o más, la IP del cliente sale de X-Forwarded-For contando
# desde la derecha (lo que agregó el último proxy propio, no lo que mandó el cliente).
PROXIES_DE_CONFIANZA = int(os.environ.get("KL_PROXIES", "0"))

# Sin nginx delante (por ejemplo, gunicorn solo en un contenedor), Django sirve
# los archivos subidos (audios, portadas, avatares). Con un proxy que los sirva,
# dejarlo en 0. En DEBUG se sirven siempre.
SERVIR_MEDIA = DEBUG or os.environ.get("KL_SERVIR_MEDIA", "0") == "1"

# --------------------------------------------------------------------------
# Aplicaciones
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Entrar con plataformas de música (Spotify, Apple Music, ...): usuarios/sociales.py
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.spotify",
    "allauth.socialaccount.providers.apple",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.soundcloud",
    # Apps del proyecto
    "usuarios",
    "musica",
    "tienda",
    "panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "keep_listening1.seguridad.LimiteDeSubida",
    "keep_listening1.seguridad.EncabezadosSeguridad",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "usuarios.middleware.CerrarSesionBloqueados",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "keep_listening1.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Context processors propios: carrito y géneros siempre disponibles
                "tienda.context_processors.carrito_resumen",
                "musica.context_processors.navegacion",
                "keep_listening1.seguridad.nonce",
                "usuarios.context_processors.plataformas",
            ],
        },
    },
]

WSGI_APPLICATION = "keep_listening1.wsgi.application"
ASGI_APPLICATION = "keep_listening1.asgi.application"

# --------------------------------------------------------------------------
# Base de datos: SQLite
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "timeout": 20,
            # IMMEDIATE toma el lock de escritura al abrir la transacción: dos
            # checkouts simultáneos del mismo carrito no pueden cobrarse dos veces.
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;",
        },
    }
}

# Caché en memoria del proceso. Los adelantos (~1 MB cada uno) van aparte y con
# tope, para que no desplacen las búsquedas ni las letras.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "kl-general",
        "OPTIONS": {"MAX_ENTRIES": 2000},
    },
    # En disco: la selección curada sobrevive a los reinicios del servidor.
    "catalogo": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("KL_CACHE_DIR", str(BASE_DIR / ".cache" / "catalogo")),
        "TIMEOUT": 60 * 60 * 24 * 7,
        "OPTIONS": {"MAX_ENTRIES": 500},
    },
    "previews": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "kl-previews",
        "TIMEOUT": 3600,
        "OPTIONS": {"MAX_ENTRIES": 60},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEST_RUNNER = "keep_listening1.test_runner.RunnerSinArchivos"

# --------------------------------------------------------------------------
# Validacion de contraseñas
# (el requisito del mockup pide mayuscula + numero: ver usuarios/validators.py)
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "usuarios.validators.ComplejidadValidator"},
]

AUTH_USER_MODEL = "usuarios.Usuario"

# --------------------------------------------------------------------------
# Inicio de sesión con plataformas (django-allauth)
# --------------------------------------------------------------------------
# El login y el registro con usuario y contraseña siguen siendo los de la app
# (usuarios/views.py); allauth solo se encarga de ir y volver de cada plataforma.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_PROVIDERS = sociales.configuracion()
# Quien entra por primera vez con una plataforma queda registrado sin otro
# formulario (usuario y correo salen de la plataforma).
SOCIALACCOUNT_AUTO_SIGNUP = True
# Si el correo (verificado por la plataforma) ya tiene cuenta acá, entra a esa
# cuenta y la deja conectada: no se duplican usuarios.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_STORE_TOKENS = False      # no se guardan tokens de las plataformas
SOCIALACCOUNT_LOGIN_ON_GET = False      # se entra con POST (con CSRF), no con un link
SOCIALACCOUNT_ADAPTER = "usuarios.adaptadores.AdaptadorSocial"
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*"]
ACCOUNT_EMAIL_VERIFICATION = "none"     # la verificación la hace la plataforma
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "musica:home"
LOGOUT_REDIRECT_URL = "musica:home"

# --------------------------------------------------------------------------
# Internacionalizacion
# --------------------------------------------------------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Archivos estáticos y media
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Manifest agrega un hash al nombre de cada archivo (styles.a1b2c3.css).
        # Sin eso, al publicar una version nueva los navegadores siguen usando
        # el CSS y el JS viejos hasta que alguien vacie la cache a mano.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Limite de subida de audio (25 MB) y portada (5 MB)
MAX_AUDIO_MB = 25
MAX_IMAGEN_MB = 5

# Extensiones y tipos MIME aceptados (se validan contra el contenido real).
AUDIO_EXTENSIONES = (".mp3", ".wav", ".ogg", ".m4a", ".flac")

# Tope del cuerpo de un pedido sin contar archivos (formularios, JSON). El tope
# de los archivos subidos lo pone el middleware LimiteDeSubida (seguridad.py),
# que corta antes de leer nada si el pedido entero pasa de MAX_AUDIO_MB + 2.
DATA_UPLOAD_MAX_MEMORY_SIZE = (MAX_AUDIO_MB + 1) * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --------------------------------------------------------------------------
# Email (consola en local)
# --------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-responder@keeplistening.local"

# --------------------------------------------------------------------------
# Mensajes -> clases de Bootstrap
# --------------------------------------------------------------------------
MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# =============================================================================
# Keep Listening - imagen para ejecucion local (Django + SQLite)
# Etapa 1: compila el SCSS con Dart Sass (Node)
# Etapa 2: aplicacion Django con el CSS ya compilado
# =============================================================================

# ---------- Etapa 1: estilos ----------
FROM node:22-alpine AS estilos

WORKDIR /estilos

# `npm ci` en lugar de `npm install`: instala exactamente lo que fija el
# package-lock, sin volver a resolver versiones en cada build.
COPY keep_listening1/package.json keep_listening1/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY keep_listening1/static/scss ./static/scss
COPY keep_listening1/tools ./tools

# `npm run build` compila el CSS y copia Bootstrap, sus iconos y las fuentes.
# El script es de Node, asi que funciona igual en Windows, Linux y macOS.
RUN npm run build

# ---------- Etapa 2: aplicacion ----------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=keep_listening1.settings

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY keep_listening1/ /app/

# CSS, fuentes y JS de Bootstrap generados en la etapa anterior
COPY --from=estilos /estilos/static/css /app/static/css
COPY --from=estilos /estilos/static/js/vendor /app/static/js/vendor
COPY --from=estilos /estilos/static/fonts /app/static/fonts

COPY entrypoint.sh /app/entrypoint.sh

# El bit de ejecucion se marca aca: no sobrevive cuando la imagen se construye
# desde un filesystem de Windows, y sin el el contenedor no arranca.
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/media /app/datos /app/staticfiles

# Servir el sitio no necesita privilegios de root.
RUN useradd --create-home --uid 1000 keep \
    && chown -R keep:keep /app
USER keep

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

# Servidor de desarrollo, que es para lo que esta pensado este compose.
# Para servir en produccion esta gunicorn (incluido en requirements.txt):
#   docker compose run --rm -p 8000:8000 web \
#       gunicorn keep_listening1.wsgi:application --bind 0.0.0.0:8000 --workers 3
#   con DJANGO_DEBUG=0 y, si no hay nginx delante que sirva /media/,
#   KL_SERVIR_MEDIA=1 (si no, los audios y portadas subidas dan 404).
#   Detrás de nginx: KL_PROXIES=1, para que los límites vean la IP real.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

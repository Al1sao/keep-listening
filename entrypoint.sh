#!/bin/sh
# =============================================================================
# Arranque del contenedor: migraciones + datos de ejemplo + servidor
# =============================================================================
set -e

echo "==> Aplicando migraciones (SQLite)"
python manage.py migrate --noinput

# Los datos de ejemplo traen contraseñas conocidas: solo en desarrollo, o en
# el sitio de demostración publicado (KL_DEMO=1, ver render.yaml). En la demo
# la contraseña del administrador se reemplaza por KL_ADMIN_PASSWORD.
SEMBRAR=0
if [ "${CARGAR_DATOS:-0}" = "1" ] && { [ "${DJANGO_DEBUG:-0}" = "1" ] || [ "${KL_DEMO:-0}" = "1" ]; }; then
    SEMBRAR=1
    echo "==> Cargando datos de ejemplo (administrador y usuario)"
    python manage.py seed
    if [ -n "${KL_ADMIN_PASSWORD:-}" ]; then
        echo "==> Contraseña del administrador tomada de KL_ADMIN_PASSWORD"
        python manage.py shell -c "import os; from django.contrib.auth import get_user_model as m; u = m().objects.get(username='admin'); u.set_password(os.environ['KL_ADMIN_PASSWORD']); u.save()"
    fi
elif [ "${CARGAR_DATOS:-0}" = "1" ]; then
    echo "==> CARGAR_DATOS=1 ignorado: con DJANGO_DEBUG=0 no se crean cuentas de prueba"
fi

echo "==> Recolectando archivos estaticos"
# Los .scss son el fuente de los estilos: ya se compilaron en la etapa de
# build y no tienen por que publicarse junto al CSS.
python manage.py collectstatic --noinput --clear --ignore=scss >/dev/null

echo ""
echo "  Keep Listening esta listo en http://localhost:8000"
if [ "$SEMBRAR" = "1" ]; then
    echo "  Administrador : admin / Admin1234"
    echo "  Usuario       : sophia / Usuario1234"
fi
echo ""

# En el hosting (KL_SERVIDOR=gunicorn) se sirve con gunicorn en el puerto que
# indica la plataforma; en local sigue el comando del Dockerfile (runserver).
if [ "${KL_SERVIDOR:-}" = "gunicorn" ]; then
    exec gunicorn keep_listening1.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60
fi

exec "$@"

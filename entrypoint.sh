#!/bin/sh
# =============================================================================
# Arranque del contenedor: migraciones + datos de ejemplo + servidor
# =============================================================================
set -e

echo "==> Aplicando migraciones (SQLite)"
python manage.py migrate --noinput

# Los datos de ejemplo traen contraseñas conocidas: solo en desarrollo.
SEMBRAR=0
if [ "${CARGAR_DATOS:-0}" = "1" ] && [ "${DJANGO_DEBUG:-0}" = "1" ]; then
    SEMBRAR=1
    echo "==> Cargando datos de ejemplo (administrador y usuario)"
    python manage.py seed
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

exec "$@"

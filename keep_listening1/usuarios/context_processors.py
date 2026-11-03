"""Las plataformas para entrar (Google, Apple, ...) en el login, el registro y el panel de entrar."""

from django.conf import settings

from . import sociales

# Se calcula una vez: las claves salen del entorno al arrancar.
PLATAFORMAS = sociales.disponibles(getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}))
HAY_ACTIVAS = any(p["activo"] for p in PLATAFORMAS)


def plataformas(request):
    return {"plataformas": PLATAFORMAS, "plataformas_activas": HAY_ACTIVAS}

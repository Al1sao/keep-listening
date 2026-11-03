"""Límite de pedidos por IP, con la caché: sin tablas ni dependencias.

No reemplaza a un límite en el proxy de producción, pero evita que un script
use los endpoints públicos (adelantos, letras, búsqueda) como servicio propio.
"""

from django.conf import settings
from django.core.cache import cache

# (máximo, ventana en segundos) de cada contador. Un solo lugar para ajustarlos.
LIMITES = {
    "buscar": (90, 60),
    "letra": (60, 60),
    "me-gusta": (120, 60),
    "reproducir": (120, 60 * 60),
    "preview": (480, 60 * 60),   # por cuenta: cada tema pide el audio y la huella
    "registro": (10, 60 * 60),
}


def ip_de(request):
    """IP del cliente. Detrás de proxies propios (settings.PROXIES_DE_CONFIANZA)
    se toma de X-Forwarded-For contando desde la derecha: las entradas de la
    izquierda las puede escribir cualquiera."""
    proxies = getattr(settings, "PROXIES_DE_CONFIANZA", 0)
    if proxies:
        cadena = [ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()]
        if len(cadena) >= proxies:
            return cadena[-proxies]
    return request.META.get("REMOTE_ADDR", "") or "desconocida"


def excedido(request, nombre, maximo, ventana):
    """True si esta IP ya hizo `maximo` pedidos de `nombre` en `ventana` segundos."""
    clave = f"kl-limite-{nombre}-{ip_de(request)}"
    if cache.add(clave, 1, ventana):
        return False
    try:
        cuenta = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, ventana)
        return False
    return cuenta > maximo

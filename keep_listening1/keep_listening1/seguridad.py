"""Encabezados de seguridad que Django 5.2 no pone solo.

- Content-Security-Policy con nonce: solo corren los scripts propios y el
  script inline de configuración (que lleva el nonce). Un <script> inyectado
  no se ejecuta aunque llegue al HTML.
- Permissions-Policy: la página no usa cámara, micrófono ni ubicación.
- Cross-Origin-Opener-Policy: otra pestaña no puede manejar esta ventana.

El admin de Django queda afuera de la CSP (usa sus propios scripts).
Django 6 trae CSP incluida: al actualizar, esto se reemplaza por
django.middleware.csp.ContentSecurityPolicyMiddleware.
"""

import secrets

from django.conf import settings
from django.http import HttpResponse

# Portadas de Apple Music y Spotify (se muestran como <img> y se leen con CORS).
IMAGENES_EXTERNAS = ("https://*.mzstatic.com", "https://i.scdn.co")


# Donde se autoriza cada plataforma de inicio de sesión (usuarios/sociales.py).
PLATAFORMAS_DE_LOGIN = (
    "https://accounts.spotify.com",
    "https://appleid.apple.com",
    "https://accounts.google.com",
    "https://secure.soundcloud.com",
    "https://soundcloud.com",
)


def politica(nonce):
    directivas = {
        "default-src": ["'self'"],
        "script-src": ["'self'", f"'nonce-{nonce}'"],
        # Los estilos en línea (style="--disco-a: …") son variables de color
        # que vienen del servidor; no ejecutan código.
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "blob:", *IMAGENES_EXTERNAS],
        "media-src": ["'self'", "blob:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "worker-src": ["'self'", "blob:"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        # Los botones de "Entrar con Google, Apple, ..." envían un formulario
        # que termina en la página de la plataforma.
        "form-action": ["'self'", *PLATAFORMAS_DE_LOGIN],
        "frame-ancestors": ["'none'"],
    }
    texto = "; ".join(f"{clave} {' '.join(valores)}" for clave, valores in directivas.items())
    if not settings.DEBUG:
        texto += "; upgrade-insecure-requests"
    return texto


class EncabezadosSeguridad:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        respuesta = self.get_response(request)
        if not request.path.startswith("/django-admin/"):
            respuesta.setdefault("Content-Security-Policy", politica(request.csp_nonce))
        respuesta.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        respuesta.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return respuesta


class LimiteDeSubida:
    """Corta un pedido demasiado grande antes de leerlo.

    DATA_UPLOAD_MAX_MEMORY_SIZE no cuenta los archivos: sin esto, una subida de
    varios GB se escribiría entera en el disco temporal antes de que el
    formulario la rechace. El tope es el audio permitido más un margen para la
    portada y el resto del formulario.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.maximo = (settings.MAX_AUDIO_MB + settings.MAX_IMAGEN_MB + 1) * 1024 * 1024

    def __call__(self, request):
        try:
            largo = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            largo = 0
        if largo > self.maximo:
            return HttpResponse("El archivo es demasiado grande.", status=413, content_type="text/plain; charset=utf-8")
        return self.get_response(request)


def nonce(request):
    """Context processor: {{ csp_nonce }} en los templates."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}

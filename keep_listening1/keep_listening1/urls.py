"""URLs raiz del proyecto Keep Listening."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import RedirectView


def media_con_rango(request, ruta):
    import mimetypes
    from pathlib import Path

    from django.http import Http404

    from musica.views import responder_archivo

    raiz = Path(settings.MEDIA_ROOT).resolve()
    archivo = (raiz / ruta).resolve()
    if raiz not in archivo.parents or not archivo.is_file():
        raise Http404
    tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    # Solo se lee del disco el pedazo pedido (los audios pesan hasta 25 MB).
    return responder_archivo(request, archivo, tipo)


def health(request):
    """Chequeo liviano para Docker: responde sin tocar las APIs de afuera."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"ok": False}, status=503)
    return JsonResponse({"ok": True})


urlpatterns = [
    path("health/", health, name="health"),
    path("django-admin/", admin.site.urls),
    path("cuenta/", include("usuarios.urls")),
    # Inicio de sesión con plataformas (allauth). Sus páginas de login y registro
    # con contraseña no se usan: llevan a las del sitio.
    path("auth/login/", RedirectView.as_view(pattern_name="usuarios:login", query_string=True)),
    path("auth/signup/", RedirectView.as_view(pattern_name="usuarios:registro", query_string=True)),
    path("auth/", include("allauth.urls")),
    path("tienda/", include("tienda.urls")),
    path("panel/", include("panel.urls")),
    path("", include("musica.urls")),
]

if settings.SERVIR_MEDIA:
    # Los archivos subidos, con pedidos parciales (sin eso un audio no se puede
    # adelantar). Con nginx delante se apaga (KL_SERVIR_MEDIA=0) y los sirve él.
    urlpatterns += [path("media/<path:ruta>", media_con_rango)]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
    # Con DEBUG Django muestra su propia página de error: estas rutas dejan ver
    # las de Keep Listening mientras se diseñan.
    from musica.views import error_404, error_500

    urlpatterns += [
        path("_error/404/", error_404),
        path("_error/500/", error_500),
    ]

handler404 = "musica.views.error_404"
handler500 = "musica.views.error_500"

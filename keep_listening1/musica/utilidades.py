"""Pequeñas piezas que comparten las vistas y los formularios de todas las apps."""

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.forms import ValidationError
from django.utils.text import slugify


def es_ajax(request):
    """El front pide JSON con este encabezado (fetch de app.js y compañía)."""
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def validar_imagen(archivo, nombre="La imagen"):
    """Un archivo recién subido no puede pasar de MAX_IMAGEN_MB. Devuelve el archivo."""
    if archivo and isinstance(archivo, UploadedFile):
        if archivo.size > settings.MAX_IMAGEN_MB * 1024 * 1024:
            raise ValidationError(f"{nombre} supera el límite de {settings.MAX_IMAGEN_MB} MB.")
    return archivo


def slug_unico(instancia, texto, respaldo):
    """Slug libre para la instancia ("titulo-7", "titulo-7-2", ...)."""
    modelo = type(instancia)
    base = slugify(texto)[:200] or respaldo
    slug, i = base, 2
    while modelo.objects.filter(slug=slug).exclude(pk=instancia.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug

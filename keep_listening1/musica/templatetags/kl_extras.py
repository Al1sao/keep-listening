"""Filtros y tags propios de Keep Listening."""

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def query_sin_pagina(context):
    """Devuelve la query string actual sin el parametro `page` (para paginar)."""
    request = context.get("request")
    if request is None:
        return ""
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


@register.filter
def moneda(valor):
    """Formatea un número como precio en pesos: $35.000,00"""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return valor
    entero, decimal = f"{numero:,.2f}".split(".")
    entero = entero.replace(",", ".")
    return f"${entero},{decimal}"


@register.filter
def duracion(segundos):
    """Convierte segundos en m:ss."""
    try:
        segundos = int(segundos)
    except (TypeError, ValueError):
        return "0:00"
    minutos, resto = divmod(segundos, 60)
    return f"{minutos}:{resto:02d}"


@register.filter
def clase_estado(estado):
    return {
        "PENDIENTE": "pendiente",
        "APROBADA": "aprobada",
        "RECHAZADA": "rechazada",
        "PAGADO": "aprobada",
        "CANCELADO": "rechazada",
    }.get(estado, "neutro")


@register.simple_tag
def estatico(ruta):
    """URL de un estático que se renueva sola cuando el archivo cambia.

    En producción el almacenamiento con manifiesto ya pone un hash en el nombre;
    en desarrollo se agrega la fecha de modificación (?v=...), así el navegador
    no se queda con una versión vieja del CSS o del JS.
    """
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static

    url = static(ruta)
    if not settings.DEBUG:
        return url
    archivo = finders.find(ruta)
    if not archivo:
        return url
    import os

    return f"{url}?v={int(os.path.getmtime(archivo))}"


@register.filter
def flotante(campo):
    """Dibuja un campo de formulario para una etiqueta flotante (.kl-flotante).

    La etiqueta sube con :placeholder-shown, así que el placeholder tiene que
    ser un espacio; los atributos de accesibilidad y validación se conservan.
    """
    attrs = {"placeholder": " "}
    if campo.errors:
        attrs["aria-invalid"] = "true"
        attrs["aria-describedby"] = f"{campo.auto_id}-error"
    return campo.as_widget(attrs=attrs)

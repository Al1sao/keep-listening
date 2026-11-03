"""Cantidad de discos en la bolsa, para el contador de la barra y del menú."""

from django.db.models import Sum

from .models import CarritoItem


def carrito_resumen(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {"carrito_cantidad": 0}
    # Una sola consulta (suma en la base), sin cargar el carrito ni sus ítems.
    cantidad = CarritoItem.objects.filter(carrito__usuario=usuario).aggregate(n=Sum("cantidad"))["n"]
    return {"carrito_cantidad": cantidad or 0}

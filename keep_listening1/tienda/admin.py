from django.contrib import admin

from .models import Carrito, CarritoItem, Pago, Pedido, PedidoItem


class CarritoItemInline(admin.TabularInline):
    model = CarritoItem
    extra = 0


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cantidad_items", "total", "actualizado")
    inlines = [CarritoItemInline]


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("numero", "usuario", "total", "estado", "fecha")
    list_filter = ("estado", "fecha")
    search_fields = ("numero", "usuario__username")
    inlines = [PedidoItemInline]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "nombre_titular", "tarjeta_enmascarada", "monto_total", "estado")
    list_filter = ("estado", "marca")

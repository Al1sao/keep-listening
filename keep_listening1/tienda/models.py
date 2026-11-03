"""Modelos de la tienda: carrito, pedidos y pagos.

Del diagrama entidad-relacion:
    CARRITO (id_carrito, id_usuario, fecha_creacion, total)
    CARRITO_ALBUM (id_carrito, id_album, nombre_album, precio_unitario, formato, tipo,
                   cantidad, subtotal)
    PAGO (id_pago, id_carrito, numero_tarjeta, nombre_titular, vencimiento,
          codigo_seguridad, fecha_pago, monto_total, estado)
"""

import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F
from django.db.models.functions import Least
from django.utils import timezone

from musica.models import Album


class Formato(models.TextChoices):
    DIGITAL = "DIGITAL", "Digital"
    FISICO = "FISICO", "Físico"


class Carrito(models.Model):
    """Carrito activo del usuario. Uno por usuario."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carrito"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "carrito"
        verbose_name_plural = "carritos"

    def __str__(self):
        return f"Carrito de {self.usuario.username}"

    # -- Operaciones del diagrama de clases -------------------------------
    def agregar_producto(self, album, formato, cantidad=1):
        cantidad = min(cantidad, CarritoItem.MAXIMO)
        item, creado = self.items.get_or_create(
            album=album,
            formato=formato,
            defaults={
                "cantidad": cantidad,
                "precio_unitario": album.precio_por_formato(formato),
                "nombre_album": album.titulo,
            },
        )
        if not creado:
            # En la base y con tope: dos "agregar" simultáneos no se pisan.
            CarritoItem.objects.filter(pk=item.pk).update(
                cantidad=Least(F("cantidad") + cantidad, CarritoItem.MAXIMO)
            )
            item.refresh_from_db(fields=["cantidad"])
        return item

    @staticmethod
    def resumen(items):
        """Cantidad y total de una lista de ítems ya cargada (sin otra consulta)."""
        return (
            sum(item.cantidad for item in items),
            sum((item.subtotal() for item in items), Decimal("0.00")),
        )

    def calcular_total(self):
        return self.resumen(self.items.all())[1]

    @property
    def total(self):
        return self.calcular_total()

    @property
    def cantidad_items(self):
        return self.resumen(self.items.all())[0]

    def vaciar(self):
        self.items.all().delete()


class CarritoItem(models.Model):
    """Linea del carrito: álbum + formato + cantidad."""

    MAXIMO = 20  # unidades por línea (el mismo tope que el campo del carrito)

    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="en_carritos")
    nombre_album = models.CharField(max_length=200, blank=True)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.DIGITAL)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "item del carrito"
        verbose_name_plural = "items del carrito"
        unique_together = ("carrito", "album", "formato")
        ordering = ["agregado"]

    def __str__(self):
        return f"{self.album.titulo} ({self.get_formato_display()}) x{self.cantidad}"

    def save(self, *args, **kwargs):
        if not self.nombre_album:
            self.nombre_album = self.album.titulo
        if not self.precio_unitario:
            self.precio_unitario = self.album.precio_por_formato(self.formato)
        super().save(*args, **kwargs)

    def subtotal(self):
        return self.precio_unitario * self.cantidad

    @property
    def es_digital(self):
        return self.formato == Formato.DIGITAL


ALFABETO_PEDIDO = string.ascii_uppercase + string.digits


def _numero_pedido():
    """Número legible del pedido. `secrets` evita secuencias predecibles."""
    sufijo = "".join(secrets.choice(ALFABETO_PEDIDO) for _ in range(6))
    return f"KL-{timezone.localdate():%Y%m%d}-{sufijo}"


class Pedido(models.Model):
    """Compra confirmada (resultado de finalizar el carrito)."""

    # Los estados que cuentan como plata cobrada (facturado del panel).
    ESTADOS_COBRADOS = ("PAGADO", "ENVIADO", "ENTREGADO")

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PAGADO = "PAGADO", "Pagado"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGADO = "ENTREGADO", "Entregado"
        CANCELADO = "CANCELADO", "Cancelado"

    numero = models.CharField(max_length=24, unique=True, default=_numero_pedido)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pedidos"
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["fecha"], name="pedido_fecha"),
            models.Index(fields=["estado"], name="pedido_estado"),
        ]

    def __str__(self):
        return f"{self.numero} - {self.usuario.username}"

    def save(self, *args, **kwargs):
        # El numero es único: si el azar repite uno, se reintenta en vez de
        # cortar la compra con un IntegrityError.
        if not self.pk:
            while Pedido.objects.filter(numero=self.numero).exists():
                self.numero = _numero_pedido()
        super().save(*args, **kwargs)

    @property
    def tiene_fisicos(self):
        # Con items.all() aprovecha el prefetch de la lista de pedidos (sin una consulta por pedido).
        return any(item.formato == Formato.FISICO for item in self.items.all())

    def recorrido(self):
        """Etapas del pedido para dibujarlas como un surco (hechas, actual, por venir).

        Un pedido solo digital no se envía: pasa de pagado a "en tu biblioteca".
        """
        if self.estado == self.Estado.CANCELADO:
            return [{"nombre": "Cancelado", "hecha": True, "actual": True}]
        if self.tiene_fisicos:
            etapas = [
                (self.Estado.PENDIENTE, "Recibido"), (self.Estado.PAGADO, "Pagado"),
                (self.Estado.ENVIADO, "En camino"), (self.Estado.ENTREGADO, "Entregado"),
            ]
        else:
            etapas = [(self.Estado.PENDIENTE, "Recibido"), (self.Estado.PAGADO, "En tu biblioteca")]
        codigos = [codigo for codigo, _ in etapas]
        actual = codigos.index(self.estado) if self.estado in codigos else len(codigos) - 1
        return [
            {"nombre": nombre, "hecha": i <= actual, "actual": i == actual}
            for i, (_, nombre) in enumerate(etapas)
        ]

    def color_estado(self):
        return {
            self.Estado.PENDIENTE: "warning",
            self.Estado.PAGADO: "success",
            self.Estado.ENVIADO: "info",
            self.Estado.ENTREGADO: "secondary",
            self.Estado.CANCELADO: "danger",
        }[self.Estado(self.estado)]


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="items")
    album = models.ForeignKey(Album, on_delete=models.SET_NULL, null=True, related_name="vendido_en")
    nombre_album = models.CharField(max_length=200)
    artista = models.CharField(max_length=150, blank=True)
    formato = models.CharField(max_length=10, choices=Formato.choices)
    tipo_disco = models.CharField(max_length=10, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "item del pedido"
        verbose_name_plural = "items del pedido"

    def __str__(self):
        return f"{self.nombre_album} x{self.cantidad}"

    def subtotal(self):
        return self.precio_unitario * self.cantidad


class Pago(models.Model):
    """Datos del pago. Solo se guardan los últimos 4 digitos de la tarjeta."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name="pago")
    nombre_titular = models.CharField(max_length=120)
    ultimos_digitos = models.CharField(max_length=4)
    marca = models.CharField(max_length=20, blank=True)
    vencimiento = models.CharField(max_length=5, help_text="MM/AA")
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_pago = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pago"
        verbose_name_plural = "pagos"

    def __str__(self):
        return f"Pago {self.pedido.numero} ({self.get_estado_display()})"

    def procesar_pago(self):
        """Simulación del sistema de pago del diagrama de secuencia."""
        self.estado = self.Estado.APROBADO
        self.save(update_fields=["estado"])
        self.pedido.estado = Pedido.Estado.PAGADO
        self.pedido.save(update_fields=["estado"])
        return True

    @property
    def tarjeta_enmascarada(self):
        return f"**** **** **** {self.ultimos_digitos}"

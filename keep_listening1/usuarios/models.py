"""Modelos de usuarios.

Del diagrama entidad-relacion:
    USUARIO (id_usuario, nombre_usuario, correo_electronico, contrasena, fecha_registro)
    ADMINISTRADOR (id_admin, nombre, correo_electronico, contrasena)

Se resuelve con un único modelo de usuario y un campo `rol`, de modo que el
administrador es un usuario con permisos de moderacion (is_staff).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Usuario(AbstractUser):
    """Usuario de la plataforma. Sirve tanto para oyentes como administradores."""

    class Rol(models.TextChoices):
        USUARIO = "USUARIO", "Usuario"
        ADMIN = "ADMIN", "Administrador"

    email = models.EmailField("correo electrónico", unique=True)
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.USUARIO)
    avatar = models.ImageField("avatar", upload_to="avatares/", blank=True, null=True)
    biografia = models.TextField("biografia", max_length=500, blank=True)
    fecha_registro = models.DateTimeField("fecha de registro", default=timezone.now)
    bloqueado = models.BooleanField(
        "bloqueado", default=False, help_text="Sanción aplicada por un administrador."
    )
    motivo_bloqueo = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["-fecha_registro"]
        indexes = [models.Index(fields=["fecha_registro"], name="usuario_registro")]

    def __str__(self):
        return self.username

    # -- Helpers usados en templates y vistas -----------------------------
    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.is_superuser or self.is_staff

    @property
    def iniciales(self):
        base = (self.first_name or self.username or "?").strip()
        return base[:2].upper()

    def save(self, *args, **kwargs):
        # Mantiene coherente el rol con los flags de Django.
        if self.rol == self.Rol.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

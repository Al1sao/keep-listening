from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "email", "rol", "bloqueado", "is_staff", "fecha_registro")
    list_filter = ("rol", "bloqueado", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-fecha_registro",)
    fieldsets = UserAdmin.fieldsets + (
        (
            "Keep Listening",
            {"fields": ("rol", "avatar", "biografia", "bloqueado", "motivo_bloqueo", "fecha_registro")},
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Keep Listening", {"fields": ("email", "rol")}),
    )

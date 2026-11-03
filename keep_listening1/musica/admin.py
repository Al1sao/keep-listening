from django.contrib import admin
from django.utils import timezone

from .models import Album, Cancion, Favorito, Genero, MeGusta, Reproduccion


@admin.register(Genero)
class GeneroAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "total_canciones")
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ("nombre",)


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("titulo", "artista", "tipo", "fecha_lanzamiento", "precio_digital",
                    "precio_fisico", "stock_fisico", "publicado")
    list_filter = ("tipo", "tipo_disco", "publicado", "genero")
    search_fields = ("titulo", "artista__username")
    prepopulated_fields = {"slug": ("titulo",)}


@admin.register(Cancion)
class CancionAdmin(admin.ModelAdmin):
    list_display = ("titulo", "artista", "genero", "tipo", "estado", "reproducciones", "fecha_subida")
    list_filter = ("estado", "tipo", "genero")
    search_fields = ("titulo", "artista__username")
    prepopulated_fields = {"slug": ("titulo",)}
    actions = ("aprobar", "rechazar")

    @admin.action(description="Aprobar canciones seleccionadas")
    def aprobar(self, request, queryset):
        actualizadas = queryset.update(
            estado=Cancion.Estado.APROBADA,
            revisada_por=request.user,
            fecha_revision=timezone.now(),
            motivo_rechazo="",
        )
        self.message_user(request, f"{actualizadas} canción(es) aprobadas.")

    @admin.action(description="Rechazar canciones seleccionadas")
    def rechazar(self, request, queryset):
        actualizadas = queryset.update(
            estado=Cancion.Estado.RECHAZADA,
            revisada_por=request.user,
            fecha_revision=timezone.now(),
            # El artista ve el motivo en "Mis publicaciones", igual que desde el panel.
            motivo_rechazo="Rechazada desde la administración de Django.",
        )
        self.message_user(request, f"{actualizadas} canción(es) rechazadas.")


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cancion", "fecha_agregado")
    search_fields = ("usuario__username", "cancion__titulo")


@admin.register(Reproduccion)
class ReproduccionAdmin(admin.ModelAdmin):
    list_display = ("cancion", "usuario", "fecha")
    list_filter = ("fecha",)


@admin.register(MeGusta)
class MeGustaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "artista", "usuario", "fecha")
    list_select_related = ("usuario",)
    search_fields = ("titulo", "artista", "usuario__username")

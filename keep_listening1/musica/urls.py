from django.urls import path

from . import views

app_name = "musica"

urlpatterns = [
    path("", views.home, name="home"),
    path("explorar/", views.explorar, name="explorar"),
    path("mi-musica/", views.mi_musica, name="mi_musica"),
    path("subir/", views.subir_cancion, name="subir_cancion"),
    path("mis-publicaciones/", views.mis_publicaciones, name="mis_publicaciones"),
    path("album/nuevo/", views.crear_album, name="crear_album"),
    path("album/<slug:slug>/editar/", views.editar_album, name="editar_album"),
    path("cancion/<slug:slug>/", views.detalle_cancion, name="detalle_cancion"),
    path("cancion/<slug:slug>/editar/", views.editar_cancion, name="editar_cancion"),
    path("cancion/<slug:slug>/eliminar/", views.eliminar_cancion, name="eliminar_cancion"),
    # AJAX
    path("api/favorito/<int:cancion_id>/", views.toggle_favorito, name="toggle_favorito"),
    path("api/reproducir/<int:cancion_id>/", views.registrar_reproduccion, name="registrar_reproduccion"),
    path("api/duracion/<int:cancion_id>/", views.actualizar_duracion, name="actualizar_duracion"),
    path("api/buscar/", views.api_buscar, name="api_buscar"),
    path("api/cola/", views.api_cola, name="api_cola"),
    path("api/letra/", views.api_letra, name="api_letra"),
    path("api/preview/", views.api_preview, name="api_preview"),
    path("api/me-gusta/", views.api_me_gusta, name="api_me_gusta"),
]

from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    # Moderacion de contenido
    path("canciones/", views.canciones, name="canciones"),
    path("canciones/<slug:slug>/", views.detalle_cancion, name="detalle_cancion"),
    path("canciones/<slug:slug>/aprobar/", views.aprobar_cancion, name="aprobar_cancion"),
    path("canciones/<slug:slug>/rechazar/", views.rechazar_cancion, name="rechazar_cancion"),
    path("canciones/<slug:slug>/eliminar/", views.eliminar_cancion, name="eliminar_cancion"),
    # Usuarios
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/<int:user_id>/sancionar/", views.sancionar_usuario, name="sancionar_usuario"),
    path("usuarios/<int:user_id>/rol/", views.cambiar_rol, name="cambiar_rol"),
    # Tienda
    path("productos/", views.albumes, name="albumes"),
    path("productos/nuevo/", views.album_form, name="nuevo_album"),
    path("productos/<slug:slug>/editar/", views.album_form, name="editar_album"),
    path("productos/<slug:slug>/eliminar/", views.eliminar_album, name="eliminar_album"),
    path("pedidos/", views.pedidos, name="pedidos"),
    path("pedidos/<str:numero>/estado/", views.cambiar_estado_pedido, name="cambiar_estado_pedido"),
    # Generos
    path("generos/", views.generos, name="generos"),
    path("generos/<slug:slug>/eliminar/", views.eliminar_genero, name="eliminar_genero"),
]

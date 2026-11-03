from django.urls import path

from . import views

app_name = "tienda"

urlpatterns = [
    path("", views.catalogo, name="catalogo"),
    path("portada/<slug:slug>.svg", views.portada, name="portada"),
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/vaciar/", views.vaciar_carrito, name="vaciar_carrito"),
    path("checkout/", views.checkout, name="checkout"),
    path("pedidos/", views.mis_pedidos, name="mis_pedidos"),
    path("pedido/<str:numero>/", views.confirmacion, name="confirmacion"),
    path("album/<slug:slug>/", views.detalle_album, name="detalle_album"),
    path("muestra/<int:album_id>/<int:numero>.wav", views.muestra, name="muestra"),
    # AJAX
    path("api/carrito/agregar/<int:album_id>/", views.agregar_al_carrito, name="agregar_al_carrito"),
    path("api/carrito/item/<int:item_id>/", views.actualizar_item, name="actualizar_item"),
    path("api/carrito/item/<int:item_id>/eliminar/", views.eliminar_item, name="eliminar_item"),
]

from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("login/", views.LoginKeepListening.as_view(), name="login"),
    path("logout/", views.cerrar_sesion, name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/password/", views.cambiar_password, name="cambiar_password"),
    path("artista/<str:username>/", views.perfil_publico, name="perfil_publico"),
]

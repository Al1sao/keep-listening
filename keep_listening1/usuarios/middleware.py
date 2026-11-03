from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


class CerrarSesionBloqueados:
    """Un usuario bloqueado pierde la sesión en el siguiente pedido, no recién
    cuando intente entrar de nuevo."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and getattr(usuario, "bloqueado", False):
            logout(request)
            messages.error(request, "Tu cuenta está bloqueada. Escribinos si creés que es un error.")
            return redirect("usuarios:login")
        return self.get_response(request)

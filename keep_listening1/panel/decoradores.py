"""Control de acceso al panel de administración."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse


def admin_requerido(vista):
    """Solo usuarios con rol ADMIN (o staff/superuser) acceden al panel."""

    @wraps(vista)
    def _envoltorio(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # redirect_to_login arma el ?next= escapado y respeta LOGIN_URL.
            return redirect_to_login(request.get_full_path(), reverse("usuarios:login"))
        if not request.user.es_admin:
            messages.error(request, "Necesitas permisos de administrador para entrar al panel.")
            return redirect("musica:home")
        return vista(request, *args, **kwargs)

    return _envoltorio

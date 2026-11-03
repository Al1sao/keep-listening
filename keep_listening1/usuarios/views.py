"""Vistas de cuenta: registro, inicio/cierre de sesion y perfil.

Casos de uso 1 y 2 del informe.
"""

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from musica.limites import LIMITES, excedido, ip_de
from musica.models import Album, Cancion, Favorito, MeGusta, Reproduccion
from tienda.models import Pedido

from .forms import PerfilForm, RegistroForm
from .models import Usuario


def registro(request):
    """Caso de uso 1: Registro de usuario."""
    if request.user.is_authenticated:
        return redirect("musica:home")

    form = RegistroForm(request.POST or None)
    # Un tope de cuentas nuevas por IP y por hora: frena la creación en masa.
    if request.method == "POST" and excedido(request, "registro", *LIMITES["registro"]):
        form.add_error(None, "Demasiados registros desde esta conexión. Probá más tarde.")
        return render(request, "usuarios/registro.html", {"form": form, "titulo": "Registro"}, status=429)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        # Hay dos backends (contraseña y plataformas): esta cuenta es de contraseña.
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            request, f"Bienvenido a Keep Listening, {usuario.username}. Tu cuenta fue creada."
        )
        # Si venía de tocar un tema, vuelve a esa página (solo rutas de este sitio).
        destino = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
            return redirect(destino)
        return redirect("musica:home")

    return render(request, "usuarios/registro.html", {"form": form, "titulo": "Registro"})


INTENTOS_MAXIMOS = 5            # por usuario desde una IP
INTENTOS_MAXIMOS_POR_IP = 20    # en total desde una IP (probar muchos usuarios)
VENTANA_INTENTOS = 15 * 60


def _clave_intentos(request):
    usuario = (request.POST.get("username") or "").strip().lower()[:150]
    return f"kl-login-{ip_de(request)}-{usuario}"


def _clave_ip(request):
    return f"kl-login-ip-{ip_de(request)}"


def _sumar(clave):
    if cache.add(clave, 1, VENTANA_INTENTOS) is False:
        try:
            cache.incr(clave)
        except ValueError:
            cache.set(clave, 1, VENTANA_INTENTOS)


class LoginKeepListening(LoginView):
    """Caso de uso 2: Inicio de sesión.

    Después de 5 intentos fallidos para el mismo usuario desde la misma IP,
    se frena 15 minutos: adivinar contraseñas deja de ser práctico. Y una IP que
    falla 20 veces en total (probando una contraseña con muchos usuarios)
    también se frena.
    """

    template_name = "usuarios/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if (
            cache.get(_clave_intentos(request), 0) >= INTENTOS_MAXIMOS
            or cache.get(_clave_ip(request), 0) >= INTENTOS_MAXIMOS_POR_IP
        ):
            form = self.get_form()
            form.errors.clear()
            form.add_error(None, "Demasiados intentos. Esperá unos minutos y probá de nuevo.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        _sumar(_clave_intentos(self.request))
        _sumar(_clave_ip(self.request))
        return super().form_invalid(form)

    def get_form_class(self):
        from .forms import LoginForm

        return LoginForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Iniciar sesión"
        return ctx

    def form_valid(self, form):
        cache.delete(_clave_intentos(self.request))
        messages.success(self.request, f"Hola de nuevo, {form.get_user().username}.")
        return super().form_valid(form)


@require_POST
def cerrar_sesion(request):
    """Solo por POST y con token CSRF: evita el cierre de sesión por enlace."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "Cerraste sesión correctamente.")
    return redirect("musica:home")


@login_required
def perfil(request):
    """Datos de la cuenta + resumen de actividad."""
    form = PerfilForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil actualizado.")
        return redirect("usuarios:perfil")

    contexto = {
        "form": form,
        "titulo": "Tu perfil",
        # Texto grabado en el anillo de la etiqueta.
        "grabado": f"KEEP LISTENING · {request.user.username.upper()} · DESDE {request.user.fecha_registro.year}",
        "me_gusta": MeGusta.objects.filter(usuario=request.user).count(),
        "publicaciones": Cancion.objects.filter(artista=request.user).count(),
        "aprobadas": Cancion.objects.filter(artista=request.user, estado=Cancion.Estado.APROBADA).count(),
        "pendientes": Cancion.objects.filter(artista=request.user, estado=Cancion.Estado.PENDIENTE).count(),
        "favoritos": Favorito.objects.filter(usuario=request.user).count(),
        "reproducciones": Reproduccion.objects.filter(usuario=request.user).count(),
        "pedidos": Pedido.objects.filter(usuario=request.user).count(),
    }
    return render(request, "usuarios/perfil.html", contexto)


@login_required
def cambiar_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for campo in form.fields.values():
        campo.widget.attrs.update({"class": "kl-input", "data-password": "1"})
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        update_session_auth_hash(request, usuario)
        messages.success(request, "Contraseña actualizada.")
        return redirect("usuarios:perfil")
    return render(
        request, "usuarios/cambiar_password.html", {"form": form, "titulo": "Cambiar contraseña"}
    )


def perfil_publico(request, username):
    """Perfil público de un artista con sus canciones aprobadas."""
    artista = get_object_or_404(Usuario, username=username)
    canciones = list(
        Cancion.objects.filter(artista=artista, estado=Cancion.Estado.APROBADA)
        .select_related("artista", "genero", "album")
        .order_by("-fecha_subida")
    )
    albumes = list(Album.objects.filter(artista=artista, publicado=True).select_related("artista"))
    contexto = {
        "artista": artista,
        "canciones": canciones,
        "albumes": albumes,
        "titulo": artista.username,
        # Cola para el reproductor con las canciones del artista.
        "pistas": [c.como_pista() for c in canciones],
    }
    return render(request, "usuarios/perfil_publico.html", contexto)

"""Panel de administracion (caso de uso 7: administracion de contenido).

Cubre las tres columnas del mockup de administrador:
    - Moderacion y control de contenido (cola de aprobacion, edicion, eliminacion, portadas)
    - Administrar usuarios (cuentas, sanciones, verificaciones)
    - Gestion de tienda y pedidos (inventario, pedidos, entregas digitales, productos)
"""

import logging
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Min, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from musica.forms import AlbumForm, EditarCancionForm
from musica.models import Album, Cancion, Favorito, Genero, MeGusta, Reproduccion
from musica.seleccion import mezcla
from tienda.models import Formato, Pedido
from usuarios.models import Usuario

from musica.utilidades import es_ajax

from .decoradores import admin_requerido

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resumen general
# ---------------------------------------------------------------------------
def _nivel(parte, total):
    """Proporción 0-1 para los medidores de la consola."""
    return round(min(1, parte / total), 3) if total else 0


def _actividad(dias=14):
    """Eventos por día (escuchas, me gusta, cuentas y pedidos) para el bus master."""
    hoy = timezone.localdate()
    desde = hoy - timedelta(days=dias - 1)
    fuentes = (
        ("escuchas", Reproduccion.objects, "fecha"),
        ("me_gusta", MeGusta.objects, "fecha"),
        ("cuentas", Usuario.objects, "fecha_registro"),
        ("pedidos", Pedido.objects, "fecha"),
    )
    tabla = {desde + timedelta(days=n): dict.fromkeys((nombre for nombre, *_ in fuentes), 0) for n in range(dias)}
    medianoche = timezone.make_aware(datetime.combine(desde, time.min))
    for nombre, manager, campo in fuentes:
        filas = (
            manager.filter(**{f"{campo}__gte": medianoche})
            .annotate(dia=TruncDate(campo))
            .values("dia")
            .annotate(n=Count("pk"))
        )
        for fila in filas:
            if fila["dia"] in tabla:
                tabla[fila["dia"]][nombre] = fila["n"]
    maximo = max((sum(v.values()) for v in tabla.values()), default=0) or 1
    return [
        {"dia": dia, "total": sum(v.values()), "nivel": _nivel(sum(v.values()), maximo), **v}
        for dia, v in tabla.items()
    ]


def _mas_guardados(cantidad=5):
    """Los temas con más me gusta. Se agrupa por id (el título lo manda el
    navegador y no se puede usar para contar); los datos salen del catálogo
    curado y, si el tema no está ahí, de la primera vez que alguien lo guardó."""
    votos = list(
        MeGusta.objects.values("pista_id")
        .annotate(n=Count("pk"), titulo=Min("titulo"), artista=Min("artista"), portada=Min("portada"))
        .order_by("-n", "pista_id")[:cantidad]
    )
    try:
        catalogo = {str(t["id"]): t for t in mezcla(0)}
    except Exception:
        log.exception("Sin selección curada para el ranking del panel")
        catalogo = {}
    filas = []
    for voto in votos:
        tema = catalogo.get(voto["pista_id"]) or voto
        filas.append({
            "titulo": tema.get("titulo", ""), "artista": tema.get("artista", ""),
            "portada": tema.get("portada", ""), "n": voto["n"],
        })
    return filas


@admin_requerido
def dashboard(request):
    hace_7 = timezone.now() - timedelta(days=7)
    pendientes = Cancion.objects.pendientes().con_relaciones().order_by("fecha_subida")

    # Un aggregate por tabla en lugar de un count() por número.
    u = Usuario.objects.aggregate(
        total=Count("pk"), nuevos=Count("pk", filter=Q(fecha_registro__gte=hace_7)),
        bloqueados=Count("pk", filter=Q(bloqueado=True)),
    )
    c = Cancion.objects.aggregate(
        total=Count("pk"),
        aprobadas=Count("pk", filter=Q(estado=Cancion.Estado.APROBADA)),
        pendientes=Count("pk", filter=Q(estado=Cancion.Estado.PENDIENTE)),
        rechazadas=Count("pk", filter=Q(estado=Cancion.Estado.RECHAZADA)),
    )
    r = Reproduccion.objects.aggregate(total=Count("pk"), semana=Count("pk", filter=Q(fecha__gte=hace_7)))
    m = MeGusta.objects.aggregate(total=Count("pk"), semana=Count("pk", filter=Q(fecha__gte=hace_7)))
    cobrado = Q(estado__in=Pedido.ESTADOS_COBRADOS)
    p = Pedido.objects.aggregate(
        cantidad=Count("pk"), cobrados=Count("pk", filter=cobrado), facturado=Sum("total", filter=cobrado),
    )
    total_usuarios, usuarios_nuevos = u["total"], u["nuevos"]
    total_canciones, canciones_aprobadas, canciones_pendientes = c["total"], c["aprobadas"], c["pendientes"]
    reproducciones, reproducciones_semana = r["total"], r["semana"]
    total_me_gusta, me_gusta_semana = m["total"], m["semana"]
    pedidos, facturado = p["cantidad"], p["facturado"] or 0

    # Cada canal de la consola: el medidor muestra qué parte del total es reciente
    # (o está pendiente), así el nivel siempre significa algo.
    canales = [
        {"nombre": "Cuentas", "valor": total_usuarios, "detalle": f"+{usuarios_nuevos} esta semana",
         "nivel": _nivel(usuarios_nuevos, total_usuarios), "icono": "people", "url": "panel:usuarios"},
        {"nombre": "En revisión", "valor": canciones_pendientes, "detalle": f"de {total_canciones} subidas",
         "nivel": _nivel(canciones_pendientes, total_canciones), "icono": "hourglass-split",
         "url": "panel:canciones", "alerta": bool(canciones_pendientes)},
        {"nombre": "En la sala", "valor": canciones_aprobadas, "detalle": "temas publicados",
         "nivel": _nivel(canciones_aprobadas, total_canciones), "icono": "music-note-list", "url": "panel:canciones"},
        {"nombre": "Escuchas", "valor": reproducciones, "detalle": f"{reproducciones_semana} esta semana",
         "nivel": _nivel(reproducciones_semana, reproducciones), "icono": "play-circle", "url": "panel:canciones"},
        {"nombre": "Me gusta", "valor": total_me_gusta, "detalle": f"{me_gusta_semana} esta semana",
         "nivel": _nivel(me_gusta_semana, total_me_gusta), "icono": "heart", "url": "panel:usuarios"},
        {"nombre": "Pedidos", "valor": pedidos, "detalle": f"{p['cobrados']} cobrados",
         "nivel": _nivel(p["cobrados"], pedidos), "icono": "bag-check", "url": "panel:pedidos"},
    ]

    top_generos = list(
        Genero.objects.annotate(
            n=Count("canciones", filter=Q(canciones__estado=Cancion.Estado.APROBADA))
        ).order_by("-n")[:8]
    )
    tope_generos = max((g.n for g in top_generos), default=0)
    for genero in top_generos:
        genero.nivel = _nivel(genero.n, tope_generos)

    contexto = {
        "titulo": "Panel de administración",
        "canales": canales,
        "actividad": _actividad(),
        "total_usuarios": total_usuarios,
        "canciones_pendientes": canciones_pendientes,
        "canciones_rechazadas": c["rechazadas"],
        "total_albumes": Album.objects.count(),
        "facturado": facturado,
        "cola": pendientes[:6],
        "ultimos_pedidos": Pedido.objects.select_related("usuario")[:5],
        "top_canciones": Cancion.objects.aprobadas().con_relaciones().order_by("-reproducciones")[:5],
        "top_me_gusta": _mas_guardados(),
        "top_generos": top_generos,
        "usuarios_bloqueados": u["bloqueados"],
    }
    return render(request, "panel/dashboard.html", contexto)


# ---------------------------------------------------------------------------
# Gestion de canciones
# ---------------------------------------------------------------------------
@admin_requerido
def canciones(request):
    listado = Cancion.objects.con_relaciones()
    estado = request.GET.get("estado", Cancion.Estado.PENDIENTE)
    q = request.GET.get("q", "").strip()

    if estado in Cancion.Estado.values:
        listado = listado.filter(estado=estado)
    if q:
        listado = listado.filter(Q(titulo__icontains=q) | Q(artista__username__icontains=q))

    listado = listado.order_by("fecha_subida" if estado == Cancion.Estado.PENDIENTE else "-fecha_subida")
    paginador = Paginator(listado, 15)
    pagina = paginador.get_page(request.GET.get("page"))

    contexto = {
        "titulo": "Gestión de canciones",
        "pagina": pagina,
        "canciones": pagina.object_list,
        "estado": estado,
        "q": q,
        "conteos": {
            "PENDIENTE": Cancion.objects.pendientes().count(),
            "APROBADA": Cancion.objects.aprobadas().count(),
            "RECHAZADA": Cancion.objects.filter(estado=Cancion.Estado.RECHAZADA).count(),
        },
    }
    return render(request, "panel/canciones.html", contexto)


@admin_requerido
def detalle_cancion(request, slug):
    """Detalle con vista previa, datos y acciones (aprobar / modificar / eliminar)."""
    cancion = get_object_or_404(Cancion.objects.con_relaciones(), slug=slug)
    form = EditarCancionForm(
        request.POST if request.POST.get("formulario") == "editar" else None,
        request.FILES or None,
        instance=cancion,
        usuario=cancion.artista,
    )
    if request.method == "POST" and request.POST.get("formulario") == "editar":
        if form.is_valid():
            form.save()
            messages.success(request, "Los datos de la canción fueron modificados.")
            return redirect("panel:detalle_cancion", slug=cancion.slug)

    contexto = {
        "titulo": f"Revisar: {cancion.titulo}",
        "cancion": cancion,
        "form": form,
        "favoritos": Favorito.objects.filter(cancion=cancion).count(),
        "otras_del_artista": Cancion.objects.filter(artista=cancion.artista)
        .exclude(pk=cancion.pk)
        .count(),
    }
    return render(request, "panel/detalle_cancion.html", contexto)


@admin_requerido
@require_POST
def aprobar_cancion(request, slug):
    cancion = get_object_or_404(Cancion, slug=slug)
    cancion.estado = Cancion.Estado.APROBADA
    cancion.motivo_rechazo = ""
    cancion.revisada_por = request.user
    cancion.fecha_revision = timezone.now()
    cancion.save()

    if es_ajax(request):
        return JsonResponse(
            {
                "ok": True,
                "estado": cancion.estado,
                "mensaje": f'"{cancion.titulo}" fue aprobada.',
                "pendientes": Cancion.objects.pendientes().count(),
            }
        )
    messages.success(request, f'"{cancion.titulo}" fue aprobada y ya es publica.')
    return redirect("panel:canciones")


@admin_requerido
@require_POST
def rechazar_cancion(request, slug):
    cancion = get_object_or_404(Cancion, slug=slug)
    # El campo guarda 250 caracteres: más largo se corta, no rompe.
    motivo = request.POST.get("motivo", "").strip()[:250]
    if not motivo:
        mensaje = "Indicá el motivo del rechazo."
        if es_ajax(request):
            return JsonResponse({"ok": False, "mensaje": mensaje}, status=400)
        messages.error(request, mensaje)
        return redirect("panel:detalle_cancion", slug=cancion.slug)

    cancion.estado = Cancion.Estado.RECHAZADA
    cancion.motivo_rechazo = motivo
    cancion.revisada_por = request.user
    cancion.fecha_revision = timezone.now()
    cancion.save()

    if es_ajax(request):
        return JsonResponse(
            {
                "ok": True,
                "estado": cancion.estado,
                "mensaje": f'"{cancion.titulo}" fue rechazada.',
                "pendientes": Cancion.objects.pendientes().count(),
            }
        )
    messages.warning(request, f'"{cancion.titulo}" fue rechazada.')
    return redirect("panel:canciones")


@admin_requerido
@require_POST
def eliminar_cancion(request, slug):
    cancion = get_object_or_404(Cancion, slug=slug)
    titulo = cancion.titulo
    cancion.delete()
    if es_ajax(request):
        return JsonResponse({"ok": True, "mensaje": f'"{titulo}" fue eliminada.'})
    messages.success(request, f'"{titulo}" fue eliminada de la plataforma.')
    return redirect("panel:canciones")


# ---------------------------------------------------------------------------
# Gestion de usuarios
# ---------------------------------------------------------------------------
@admin_requerido
def usuarios(request):
    listado = Usuario.objects.annotate(
        n_canciones=Count("canciones", distinct=True),
        n_pedidos=Count("pedidos", distinct=True),
    )
    q = request.GET.get("q", "").strip()
    filtro = request.GET.get("filtro", "")
    if q:
        listado = listado.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if filtro == "bloqueados":
        listado = listado.filter(bloqueado=True)
    elif filtro == "admins":
        listado = listado.filter(rol=Usuario.Rol.ADMIN)

    paginador = Paginator(listado.order_by("-fecha_registro"), 15)
    pagina = paginador.get_page(request.GET.get("page"))

    contexto = {
        "titulo": "Administrar usuarios",
        "pagina": pagina,
        "usuarios": pagina.object_list,
        "q": q,
        "filtro": filtro,
        "total": paginador.count,
    }
    return render(request, "panel/usuarios.html", contexto)


@admin_requerido
@require_POST
def sancionar_usuario(request, user_id):
    usuario = get_object_or_404(Usuario, pk=user_id)
    if usuario == request.user:
        messages.error(request, "No podés bloquear tu propia cuenta.")
        return redirect("panel:usuarios")
    if usuario.es_admin and not request.user.is_superuser:
        messages.error(request, "Solo un superusuario puede sancionar a otro administrador.")
        return redirect("panel:usuarios")
    usuario.bloqueado = not usuario.bloqueado
    usuario.motivo_bloqueo = request.POST.get("motivo", "").strip()[:200] if usuario.bloqueado else ""
    usuario.save(update_fields=["bloqueado", "motivo_bloqueo"])
    estado = "bloqueado" if usuario.bloqueado else "desbloqueado"
    if es_ajax(request):
        return JsonResponse(
            {"ok": True, "bloqueado": usuario.bloqueado, "mensaje": f"{usuario.username} fue {estado}."}
        )
    messages.success(request, f"{usuario.username} fue {estado}.")
    return redirect("panel:usuarios")


@admin_requerido
@require_POST
def cambiar_rol(request, user_id):
    usuario = get_object_or_404(Usuario, pk=user_id)
    if usuario == request.user:
        messages.error(request, "No podés cambiar tu propio rol.")
        return redirect("panel:usuarios")
    if not request.user.is_superuser:
        messages.error(request, "Solo un superusuario puede cambiar roles.")
        return redirect("panel:usuarios")
    if usuario.is_superuser:
        messages.error(request, "El rol de un superusuario se cambia desde la administración de Django.")
        return redirect("panel:usuarios")
    if usuario.rol == Usuario.Rol.ADMIN:
        usuario.rol = Usuario.Rol.USUARIO
        usuario.is_staff = False
    else:
        usuario.rol = Usuario.Rol.ADMIN
        usuario.is_staff = True
    usuario.save(update_fields=["rol", "is_staff"])
    messages.success(request, f"{usuario.username} ahora es {usuario.get_rol_display()}.")
    return redirect("panel:usuarios")


# ---------------------------------------------------------------------------
# Gestion de tienda
# ---------------------------------------------------------------------------
@admin_requerido
def albumes(request):
    listado = (
        Album.objects.select_related("artista", "genero")
        .annotate(n_canciones=Count("canciones"))
        .order_by("-fecha_lanzamiento")
    )
    q = request.GET.get("q", "").strip()
    if q:
        listado = listado.filter(Q(titulo__icontains=q) | Q(artista__username__icontains=q))
    paginador = Paginator(listado, 12)
    pagina = paginador.get_page(request.GET.get("page"))
    return render(
        request,
        "panel/albumes.html",
        {
            "titulo": "Gestión de productos",
            "pagina": pagina,
            "albumes": pagina.object_list,
            "q": q,
            "sin_stock": Album.objects.filter(disponible_fisico=True, stock_fisico=0).count(),
        },
    )


@admin_requerido
def album_form(request, slug=None):
    album = get_object_or_404(Album, slug=slug) if slug else None
    form = AlbumForm(request.POST or None, request.FILES or None, instance=album)
    if request.method == "POST" and form.is_valid():
        nuevo = form.save(commit=False)
        if album is None:
            nuevo.artista = request.user
        nuevo.save()
        messages.success(request, "Producto guardado.")
        return redirect("panel:albumes")
    return render(
        request,
        "panel/album_form.html",
        {"titulo": "Editar producto" if album else "Nuevo producto", "form": form, "album": album},
    )


@admin_requerido
@require_POST
def eliminar_album(request, slug):
    album = get_object_or_404(Album, slug=slug)
    titulo = album.titulo
    album.delete()
    messages.success(request, f'"{titulo}" fue eliminado de la tienda.')
    return redirect("panel:albumes")


@admin_requerido
def pedidos(request):
    listado = Pedido.objects.select_related("usuario", "pago").prefetch_related("items")
    estado = request.GET.get("estado", "")
    if estado in Pedido.Estado.values:
        listado = listado.filter(estado=estado)
    paginador = Paginator(listado, 15)
    pagina = paginador.get_page(request.GET.get("page"))
    return render(
        request,
        "panel/pedidos.html",
        {
            "titulo": "Procesamiento de pedidos",
            "pagina": pagina,
            "pedidos": pagina.object_list,
            "estado": estado,
            "estados": Pedido.Estado.choices,
            "facturado": Pedido.objects.filter(estado__in=Pedido.ESTADOS_COBRADOS)
            .aggregate(t=Sum("total"))["t"] or 0,
        },
    )


@admin_requerido
@require_POST
def cambiar_estado_pedido(request, numero):
    pedido = get_object_or_404(Pedido, numero=numero)
    nuevo = request.POST.get("estado")
    if nuevo in Pedido.Estado.values:
        if pedido.estado == Pedido.Estado.CANCELADO and nuevo != pedido.estado:
            messages.error(request, "Un pedido cancelado no se reabre: el stock ya se devolvió.")
            return redirect("panel:pedidos")
        with transaction.atomic():
            # El cambio se hace con un UPDATE condicionado: si dos pedidos de
            # "cancelar" llegan juntos, solo uno lo logra y el stock vuelve una vez.
            cambiados = (
                Pedido.objects.filter(pk=pedido.pk)
                .exclude(estado=Pedido.Estado.CANCELADO)
                .update(estado=nuevo)
            )
            if cambiados and nuevo == Pedido.Estado.CANCELADO:
                for item in pedido.items.filter(formato=Formato.FISICO, album__isnull=False):
                    Album.objects.filter(pk=item.album_id).update(
                        stock_fisico=F("stock_fisico") + item.cantidad
                    )
        pedido.refresh_from_db(fields=["estado"])
        if es_ajax(request):
            return JsonResponse(
                {"ok": True, "estado": pedido.get_estado_display(), "color": pedido.color_estado()}
            )
        messages.success(request, f"Pedido {pedido.numero}: {pedido.get_estado_display()}.")
    return redirect("panel:pedidos")


# ---------------------------------------------------------------------------
# Generos
# ---------------------------------------------------------------------------
@admin_requerido
def generos(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()[:60]
        if nombre:
            # "Rock" y "rock!" darían el mismo slug: se compara por slug, no por nombre.
            existente = Genero.objects.filter(slug=slugify(nombre)).first()
            if existente:
                messages.info(request, f'El género "{existente.nombre}" ya existe.')
            elif not slugify(nombre):
                messages.error(request, "Ese nombre no sirve como género.")
            else:
                genero = Genero.objects.create(nombre=nombre)
                messages.success(request, f'Género "{genero.nombre}" creado.')
        return redirect("panel:generos")

    listado = Genero.objects.annotate(
        n=Count("canciones", filter=Q(canciones__estado=Cancion.Estado.APROBADA))
    ).order_by("nombre")
    return render(request, "panel/generos.html", {"titulo": "Géneros", "generos": listado})


@admin_requerido
@require_POST
def eliminar_genero(request, slug):
    genero = get_object_or_404(Genero, slug=slug)
    nombre = genero.nombre
    genero.delete()
    messages.info(request, f'Género "{nombre}" eliminado.')
    return redirect("panel:generos")

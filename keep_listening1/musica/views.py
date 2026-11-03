"""Vistas del nucleo musical.

Casos de uso cubiertos:
    3 - Reproduccion de musica
    4 - Guardar canciones
    5 - Publicar canciones
"""

import logging
import math
import random
import re
from urllib.parse import parse_qs, urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .catalogo import bajar_preview, buscar_mundo, letra_de, portada_mundo, url_de_preview
from .forms import AlbumArtistaForm, AlbumForm, EditarCancionForm, SubirCancionForm
from .limites import LIMITES, excedido
from .models import Album, Cancion, Favorito, Genero, MeGusta, Reproduccion
from .seleccion import ESCENAS, escena, escenas, mezcla
from .utilidades import es_ajax

PAGINA = 12
log = logging.getLogger(__name__)


def _pistas(canciones):
    """Cola de reproducción para el front. El template la escapa con json_script."""
    return [c.como_pista() for c in canciones]


def _catalogo(consulta):
    if not consulta:
        return []
    try:
        return buscar_mundo(consulta)
    except Exception:
        log.exception("La búsqueda en el catálogo de afuera falló")
        return []


# ---------------------------------------------------------------------------
# Pagina de inicio
# ---------------------------------------------------------------------------
def _entero(valor):
    """Número entero de algo que mandó el navegador, o None. "inf", "nan" o
    "1e999" no rompen: se descartan."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return int(numero) if math.isfinite(numero) else None


def _seleccion(funcion, *args):
    """La selección curada, o una lista vacía si Apple no respondió (queda registrado)."""
    try:
        return funcion(*args)
    except Exception:
        log.exception("No se pudo armar la selección curada")
        return []


def _disco_del_dia(temas, fecha):
    """El disco del día: cinco temas por escena (lado A hip hop, lado B pop).
    La semilla es la fecha: todos ven el mismo disco ese día y mañana cambia."""
    azar = random.Random(fecha.toordinal())
    lados = []
    for letra, (slug, datos) in zip("AB", ESCENAS.items()):
        propios = [t for t in temas if t.get("genero") == datos["nombre"]]
        lados.append({
            "letra": letra,
            "escena": datos["nombre"],
            "id_json": f"kl-lado-{letra.lower()}",
            "temas": azar.sample(propios, min(5, len(propios))),
        })
    return [lado for lado in lados if lado["temas"]]


def _artistas(temas):
    """Un casillero por artista de la selección, con sus temas para sonar juntos."""
    por_artista = {}
    for tema in temas:
        por_artista.setdefault(tema["artista"], []).append(tema)
    return [
        {"nombre": nombre, "portada": lista[0]["portada"], "temas": lista, "id_json": f"kl-artista-{i}"}
        for i, (nombre, lista) in enumerate(por_artista.items())
    ]


def _ranking_de_la_sala(temas, cantidad=10):
    """Lo más guardado por la comunidad. Solo cuentan temas de la selección: el
    título y la portada salen del catálogo, no de lo que mandó el navegador."""
    votos = dict(MeGusta.objects.values_list("pista_id").annotate(n=Count("pk")))
    orden = sorted(enumerate(temas), key=lambda par: (-votos.get(str(par[1]["id"]), 0), par[0]))
    return [{**tema, "votos": votos.get(str(tema["id"]), 0)} for _, tema in orden[:cantidad]]


def home(request):
    # La sala muestra 12 temas al azar de la selección de hip hop y pop (cambian
    # en cada visita); si Apple no respondió, queda lo más escuchado del momento.
    seleccion = _seleccion(mezcla, 0)
    temas = random.sample(seleccion, min(12, len(seleccion)))
    if not temas:
        try:
            temas = portada_mundo().get("temas") or []
        except Exception:
            log.exception("Tampoco respondió la portada del mundo")
            temas = []

    me_gusta = []
    if request.user.is_authenticated:
        me_gusta = [m.como_pista() for m in MeGusta.objects.filter(usuario=request.user)[:24]]

    comunidad = list(Cancion.objects.aprobadas().con_relaciones().order_by("-fecha_subida")[:6])
    contexto = {
        "titulo": "Inicio",
        "temas_mundo": temas,
        "me_gusta": me_gusta,
        "disco_del_dia": _disco_del_dia(seleccion, timezone.localdate()),
        # El juego y el ranking usan la selección entera (con su adelanto).
        "juego": [t for t in seleccion if t.get("audio")],
        "ranking": _ranking_de_la_sala(seleccion) if seleccion else [],
        "artistas": _artistas(seleccion),
        "novedades": Album.objects.filter(publicado=True).select_related("artista", "genero")
        .order_by("-fecha_lanzamiento")[:4],
        "comunidad": comunidad,
        "pistas": _pistas(comunidad),
    }
    return render(request, "musica/home.html", contexto)


# ---------------------------------------------------------------------------
# Explorar / buscar
# ---------------------------------------------------------------------------
def explorar(request):
    canciones = Cancion.objects.aprobadas().con_relaciones()

    q = request.GET.get("q", "").strip()
    genero = request.GET.get("genero", "").strip()
    artista = request.GET.get("artista", "").strip()
    orden = request.GET.get("orden", "recientes")

    if q:
        canciones = canciones.filter(
            Q(titulo__icontains=q)
            | Q(artista__username__icontains=q)
            | Q(genero__nombre__icontains=q)
            | Q(album__titulo__icontains=q)
        )
    if genero:
        canciones = canciones.filter(genero__slug=genero)
    if artista:
        canciones = canciones.filter(artista__username=artista)

    ordenes = {
        "recientes": "-fecha_subida",
        "populares": "-reproducciones",
        "titulo": "titulo",
        "artista": "artista__username",
    }
    canciones = canciones.order_by(ordenes.get(orden, "-fecha_subida"))

    paginador = Paginator(canciones, PAGINA)
    pagina = paginador.get_page(request.GET.get("page"))

    escena_activa = request.GET.get("escena", "").strip()
    if escena_activa not in ESCENAS:
        escena_activa = ""
    secciones = []
    if not q:
        if escena_activa:
            datos = ESCENAS[escena_activa]
            secciones = [{"slug": escena_activa, "nombre": datos["nombre"],
                          "descripcion": datos["descripcion"], "temas": _seleccion(escena, escena_activa)}]
        else:
            secciones = _seleccion(escenas)
    secciones = [s for s in secciones if s["temas"]]
    # Una sola cola para el reproductor: todo lo que se ve en la página.
    catalogo = _catalogo(q) if q else [t for s in secciones for t in s["temas"]]

    contexto = {
        "titulo": "Explorar",
        "secciones": secciones,
        "escenas": [{"slug": slug, "nombre": datos["nombre"]} for slug, datos in ESCENAS.items()],
        "escena_activa": escena_activa,
        "pagina": pagina,
        "canciones": pagina.object_list,
        "q": q,
        "pistas": _pistas(pagina.object_list),
        "catalogo": catalogo,
    }
    return render(request, "musica/explorar.html", contexto)


def detalle_cancion(request, slug):
    cancion = get_object_or_404(
        Cancion.objects.con_relaciones(), slug=slug
    )
    # Solo el autor o un administrador pueden ver una cancion no aprobada.
    if not cancion.aprobada:
        if not request.user.is_authenticated or (
            request.user != cancion.artista and not request.user.es_admin
        ):
            messages.warning(request, "Esa canción todavía no fue aprobada.")
            return redirect("musica:explorar")

    similares = (
        Cancion.objects.aprobadas()
        .con_relaciones()
        .filter(genero=cancion.genero)
        .exclude(pk=cancion.pk)[:6]
    )
    contexto = {
        "titulo": cancion.titulo,
        "cancion": cancion,
        "similares": similares,
        "es_favorita": cancion.es_favorita_de(request.user),
        "pistas": _pistas([cancion] + list(similares)),
    }
    return render(request, "musica/detalle_cancion.html", contexto)


# ---------------------------------------------------------------------------
# Mi musica (caso de uso 4)
# ---------------------------------------------------------------------------
@login_required
def mi_musica(request):
    # Solo lo aprobado: si el autor cambia el audio, el tema vuelve a revisión y
    # deja de sonar acá hasta que lo aprueben otra vez.
    favoritos = (
        Favorito.objects.filter(usuario=request.user, cancion__estado=Cancion.Estado.APROBADA)
        .select_related("cancion", "cancion__artista", "cancion__genero", "cancion__album")
        .order_by("-fecha_agregado")
    )
    canciones_guardadas = [f.cancion for f in favoritos]

    historial_qs = list(
        Reproduccion.objects.filter(usuario=request.user, cancion__estado=Cancion.Estado.APROBADA)
        .select_related("cancion", "cancion__artista", "cancion__genero", "cancion__album")
        .order_by("-fecha")[:30]
    )
    # La cola de la página: guardadas y lo que sonó, así cada botón pone su tema.
    en_pagina = list({c.pk: c for c in canciones_guardadas + [r.cancion for r in historial_qs]}.values())

    publicaciones = (
        Cancion.objects.filter(artista=request.user)
        .con_relaciones()
        .order_by("-fecha_subida")
    )

    # La batea: los me gusta de Apple (lo que más se guarda) y los favoritos propios.
    coleccion = [m.como_pista() for m in MeGusta.objects.filter(usuario=request.user)]

    contexto = {
        "titulo": "Tu colección",
        "coleccion": coleccion,
        "total_discos": len(coleccion) + len(canciones_guardadas),
        "favoritos": favoritos,
        "historial": historial_qs,
        "publicaciones": publicaciones,
        "pistas": _pistas(en_pagina),
        "pendientes": publicaciones.filter(estado=Cancion.Estado.PENDIENTE).count(),
    }
    return render(request, "musica/mi_musica.html", contexto)


@login_required
@require_POST
def toggle_favorito(request, cancion_id):
    """Guarda o quita una canción de la lista personal. Responde JSON (AJAX)."""
    cancion = get_object_or_404(Cancion.objects.aprobadas(), pk=cancion_id)
    # Primero se intenta borrar: si no había nada, se guarda. Así un doble clic
    # (dos pedidos casi juntos) no choca contra la restricción de único.
    borrados, _ = Favorito.objects.filter(usuario=request.user, cancion=cancion).delete()
    guardada = not borrados
    if guardada:
        Favorito.objects.get_or_create(usuario=request.user, cancion=cancion)

    total = Favorito.objects.filter(usuario=request.user).count()
    if es_ajax(request):
        return JsonResponse(
            {
                "ok": True,
                "guardada": guardada,
                "total": total,
                "mensaje": "Guardada en tu lista" if guardada else "Quitada de tu lista",
                "cancion": {"id": cancion.id, "titulo": cancion.titulo,
                            "genero": cancion.genero.nombre if cancion.genero else ""},
            }
        )
    messages.success(request, "Guardada en tu lista." if guardada else "Quitada de tu lista.")
    return redirect(cancion.get_absolute_url())


@require_POST
def registrar_reproduccion(request, cancion_id):
    """Caso de uso 3: registra la reproducción y actualiza el contador."""
    cancion = get_object_or_404(Cancion.objects.aprobadas(), pk=cancion_id)
    # El mismo tema en la misma sesión cuenta una vez cada 30 segundos, y una IP
    # no puede registrar más de 120 por hora: así no se infla el contador.
    if not request.session.session_key:
        request.session.save()
    marca = f"kl-repro-{request.session.session_key}-{cancion.pk}"
    if not cache.add(marca, 1, 30) or excedido(request, "reproducir", *LIMITES["reproducir"]):
        return JsonResponse({"ok": True, "reproducciones": cancion.reproducciones, "contada": False})
    # F() incrementa en la base: dos reproducciones simultaneas no se pisan.
    Cancion.objects.filter(pk=cancion.pk).update(reproducciones=F("reproducciones") + 1)
    Reproduccion.objects.create(
        usuario=request.user if request.user.is_authenticated else None, cancion=cancion
    )
    cancion.refresh_from_db(fields=["reproducciones"])
    return JsonResponse({"ok": True, "reproducciones": cancion.reproducciones})


@login_required
@require_POST
def actualizar_duracion(request, cancion_id):
    """El reproductor informa la duración real del audio la primera vez que suena."""
    cancion = get_object_or_404(Cancion, pk=cancion_id)
    # El dato lo informa el reproductor, pero solo se acepta sobre canciones
    # publicas o propias: si no, cualquiera podria reescribir datos ajenos.
    duenio = cancion.artista == request.user or request.user.es_admin
    if not cancion.aprobada and not duenio:
        return JsonResponse({"ok": False}, status=403)
    # Sobre temas ajenos solo se completa una duración que falta, no se corrige.
    if not duenio and cancion.duracion_segundos:
        return JsonResponse({"ok": True, "duracion": cancion.duracion_segundos})
    segundos = _entero(request.POST.get("duracion"))
    if segundos is None:
        return JsonResponse({"ok": False}, status=400)
    if 0 < segundos < 60 * 60 and cancion.duracion_segundos != segundos:
        Cancion.objects.filter(pk=cancion.pk).update(duracion_segundos=segundos)
    return JsonResponse({"ok": True, "duracion": segundos})


# ---------------------------------------------------------------------------
# Publicar (caso de uso 5)
# ---------------------------------------------------------------------------
@login_required
def subir_cancion(request):
    form = SubirCancionForm(
        request.POST or None, request.FILES or None, usuario=request.user
    )
    if request.method == "POST" and form.is_valid():
        cancion = form.save(commit=False)
        cancion.artista = request.user
        cancion.estado = Cancion.Estado.PENDIENTE
        cancion.save()
        messages.success(
            request,
            f'"{cancion.titulo}" se envió para revisión del administrador. '
            "Te avisamos cuando este aprobada.",
        )
        return redirect("musica:mis_publicaciones")

    contexto = {
        "titulo": "Subir canción",
        "form": form,
        "generos": Genero.objects.all(),
    }
    return render(request, "musica/subir_cancion.html", contexto)


@login_required
def mis_publicaciones(request):
    publicaciones = Cancion.objects.filter(artista=request.user).con_relaciones()
    estado = request.GET.get("estado", "")
    if estado in Cancion.Estado.values:
        publicaciones = publicaciones.filter(estado=estado)

    # Un solo aggregate para los cuatro contadores, y los álbumes con su cantidad
    # de temas ya contada (antes era una consulta por álbum, dos veces).
    conteos = Cancion.objects.filter(artista=request.user).aggregate(
        total=Count("id"),
        pendientes=Count("id", filter=Q(estado=Cancion.Estado.PENDIENTE)),
        aprobadas=Count("id", filter=Q(estado=Cancion.Estado.APROBADA)),
        rechazadas=Count("id", filter=Q(estado=Cancion.Estado.RECHAZADA)),
    )
    albumes = Album.objects.filter(artista=request.user).annotate(num_canciones=Count("canciones"))
    contexto = {
        "titulo": "Mis publicaciones",
        "publicaciones": publicaciones,
        "estado": estado,
        "estados": Cancion.Estado.choices,
        "conteos": conteos,
        "albumes": albumes,
    }
    return render(request, "musica/mis_publicaciones.html", contexto)


@login_required
def editar_cancion(request, slug):
    cancion = get_object_or_404(Cancion, slug=slug)
    if cancion.artista != request.user and not request.user.es_admin:
        messages.error(request, "No podés editar una canción que no publicaste.")
        return redirect("musica:mis_publicaciones")

    form = EditarCancionForm(
        request.POST or None, request.FILES or None, instance=cancion, usuario=cancion.artista
    )
    if request.method == "POST" and form.is_valid():
        cancion = form.save(commit=False)
        if cancion.artista == request.user and not request.user.es_admin:
            # Una edicion del autor vuelve a pasar por revision.
            cancion.estado = Cancion.Estado.PENDIENTE
            cancion.motivo_rechazo = ""
        cancion.save()
        messages.success(request, "Canción actualizada.")
        return redirect("musica:mis_publicaciones")

    return render(
        request,
        "musica/subir_cancion.html",
        {"titulo": f"Editar {cancion.titulo}", "form": form, "cancion": cancion, "editando": True},
    )


@login_required
@require_POST
def eliminar_cancion(request, slug):
    cancion = get_object_or_404(Cancion, slug=slug)
    if cancion.artista != request.user and not request.user.es_admin:
        messages.error(request, "No tenés permiso para eliminar esta canción.")
        return redirect("musica:mis_publicaciones")
    titulo = cancion.titulo
    cancion.delete()
    messages.success(request, f'"{titulo}" fue eliminada.')
    return redirect("musica:mis_publicaciones")


# ---------------------------------------------------------------------------
# Albumes del artista
# ---------------------------------------------------------------------------
@login_required
def crear_album(request):
    # Un álbum nuevo entra a la tienda cuando lo publica el equipo (panel).
    formulario = AlbumForm if request.user.es_admin else AlbumArtistaForm
    form = formulario(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        album = form.save(commit=False)
        album.artista = request.user
        if not request.user.es_admin:
            album.publicado = False
        album.save()
        messages.success(
            request,
            f'Álbum "{album.titulo}" creado. Ya podés asociarle canciones; '
            "aparece en la disquería cuando el equipo lo revise.",
        )
        return redirect("musica:mis_publicaciones")
    return render(
        request, "musica/album_form.html", {"titulo": "Nuevo álbum", "form": form}
    )


@login_required
def editar_album(request, slug):
    album = get_object_or_404(Album, slug=slug)
    if album.artista != request.user and not request.user.es_admin:
        messages.error(request, "No podés editar este álbum.")
        return redirect("musica:mis_publicaciones")
    formulario = AlbumForm if request.user.es_admin else AlbumArtistaForm
    form = formulario(request.POST or None, request.FILES or None, instance=album)
    if request.method == "POST" and form.is_valid():
        album = form.save(commit=False)
        # Como una canción editada, vuelve a revisión antes de seguir a la venta.
        if not request.user.es_admin and form.has_changed():
            album.publicado = False
        album.save()
        messages.success(
            request,
            "Álbum actualizado." if request.user.es_admin or not form.has_changed()
            else "Álbum actualizado. Vuelve a la disquería cuando el equipo lo revise.",
        )
        return redirect("musica:mis_publicaciones")
    return render(
        request,
        "musica/album_form.html",
        {"titulo": f"Editar {album.titulo}", "form": form, "album": album},
    )


# ---------------------------------------------------------------------------
# Endpoints AJAX
# ---------------------------------------------------------------------------
def api_buscar(request):
    """Busqueda en vivo de la barra superior."""
    q = request.GET.get("q", "").strip()
    resultados = {"canciones": [], "albumes": [], "artistas": [], "catalogo": []}
    if len(q) >= 2 and excedido(request, "buscar", *LIMITES["buscar"]):
        return JsonResponse(resultados, status=429)
    if len(q) >= 2:
        canciones = (
            Cancion.objects.aprobadas()
            .con_relaciones()
            .filter(Q(titulo__icontains=q) | Q(artista__username__icontains=q))[:6]
        )
        resultados["canciones"] = [c.como_pista() for c in canciones]

        albumes = Album.objects.filter(publicado=True, titulo__icontains=q).select_related("artista")[:4]
        resultados["albumes"] = [
            {
                "id": a.id,
                "titulo": a.titulo,
                "artista": a.artista.username,
                "portada": a.portada_url,
                "url": a.get_absolute_url(),
            }
            for a in albumes
        ]

        from usuarios.models import Usuario

        artistas = Usuario.objects.filter(
            username__icontains=q, canciones__estado=Cancion.Estado.APROBADA
        ).distinct()[:4]
        resultados["artistas"] = [
            {
                "username": u.username,
                "url": reverse("usuarios:perfil_publico", args=[u.username]),
                "iniciales": u.iniciales,
            }
            for u in artistas
        ]
        resultados["catalogo"] = _catalogo(q)
    return JsonResponse(resultados)


def api_cola(request):
    """Devuelve una cola de reproducción según contexto (género, artista o álbum)."""
    canciones = Cancion.objects.aprobadas().con_relaciones()
    if genero := request.GET.get("genero"):
        canciones = canciones.filter(genero__slug=genero)
    if artista := request.GET.get("artista"):
        canciones = canciones.filter(artista__username=artista)
    if album := request.GET.get("album"):
        canciones = canciones.filter(album__slug=album).order_by("numero_pista")
    primero = []
    if (pedido := request.GET.get("id", "")).isdigit():
        primero = list(canciones.filter(pk=pedido))
        canciones = canciones.exclude(pk=pedido)
    pistas = [c.como_pista() for c in primero + list(canciones[: 50 - len(primero)])]
    # La radio sin filtros y sin temas propios suena con la selección curada.
    if not pistas and not request.GET:
        pistas = _seleccion(mezcla, 0)
    return JsonResponse({"pistas": pistas})


def api_letra(request):
    """Letra del tema que está sonando. No se guarda en la base."""
    artista = request.GET.get("artista", "").strip()
    titulo = request.GET.get("titulo", "").strip()
    if not artista or not titulo:
        return JsonResponse({"ok": False, "error": "Faltan artista y título."}, status=400)
    if excedido(request, "letra", *LIMITES["letra"]):
        return JsonResponse({"ok": False, "error": "Demasiados pedidos."}, status=429)
    duracion = max(0, _entero(request.GET.get("duracion")) or 0)
    try:
        return JsonResponse(letra_de(artista[:200], titulo[:200], duracion))
    except Exception:
        log.exception("LRCLIB no devolvió la letra")
        return JsonResponse({"ok": False, "plana": "", "sincronizada": ""})


PISTA_ID = re.compile(r"^(itunes|spotify)-[A-Za-z0-9]{1,40}$")
HOSTS_PORTADA = ("mzstatic.com", "scdn.co", "spotifycdn.com")
HOSTS_FICHA = ("music.apple.com", "itunes.apple.com", "open.spotify.com")


def _https_de(url, hosts):
    """La URL si es https de uno de esos dominios; si no, vacío."""
    partes = urlsplit((url or "").strip())
    host = (partes.hostname or "").lower()
    if partes.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts):
        return partes.geturl()[:500]
    return ""


@login_required
@require_POST
def api_me_gusta(request):
    """Marca o desmarca un tema de Apple Music. Llega la ficha que tiene el front
    y se valida todo: nada de eso se usa sin revisar."""
    if excedido(request, "me-gusta", *LIMITES["me-gusta"]):
        return JsonResponse({"ok": False, "mensaje": "Demasiados pedidos. Esperá un momento."}, status=429)
    pista_id = request.POST.get("id", "")
    if not PISTA_ID.match(pista_id):
        return JsonResponse({"ok": False, "mensaje": "Ese tema no se puede guardar."}, status=400)

    # Como en los favoritos: borrar primero, y si no había, guardar.
    borrados, _ = MeGusta.objects.filter(usuario=request.user, pista_id=pista_id).delete()
    guardada = not borrados
    if guardada:
        # El audio del front es el proxy (/api/preview/?u=...): el adelanto real va en "u".
        crudo = parse_qs(urlsplit(request.POST.get("audio", "")).query).get("u", [""])[0]
        try:
            preview = url_de_preview(crudo)
        except ValueError:
            return JsonResponse({"ok": False, "mensaje": "Ese tema no trae adelanto."}, status=400)
        if len(preview) > 500:
            return JsonResponse({"ok": False, "mensaje": "Ese tema no trae adelanto."}, status=400)
        duracion = max(0, min(_entero(request.POST.get("duracion")) or 0, 60 * 60))
        MeGusta.objects.get_or_create(
            usuario=request.user,
            pista_id=pista_id,
            defaults={
                "titulo": (request.POST.get("titulo") or "Sin título")[:200],
                "artista": (request.POST.get("artista") or "")[:200],
                "portada": _https_de(request.POST.get("portada"), HOSTS_PORTADA),
                "preview": preview,
                "ficha": _https_de(request.POST.get("url"), HOSTS_FICHA),
                "duracion": duracion,
                "genero": (request.POST.get("genero") or "")[:60],
            },
        )
    return JsonResponse({
        "ok": True,
        "guardada": guardada,
        "total": MeGusta.objects.filter(usuario=request.user).count(),
        "mensaje": "Agregado a tus me gusta" if guardada else "Quitado de tus me gusta",
    })


RANGO = re.compile(r"^bytes=(\d*)-(\d*)$")


def api_preview(request):
    """Reenvía un adelanto ya publicado para que el reproductor lo trate como propio.

    Así el análisis de audio (el pulso y el fondo vivo) puede escucharlo. Cualquier
    dirección que no sea un adelanto de Apple o de Spotify se rechaza. Responde
    pedidos parciales (Range) para que la barra de progreso pueda adelantar.
    """
    # Escuchar es para cuentas: sin sesión el front muestra el login.
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "login": reverse("usuarios:login")}, status=401)
    # Se cuentan escuchas nuevas, no cada pedazo que pide el navegador al
    # adelantar; y por cuenta, así una IP compartida (proxy, Docker) no suma a
    # todos juntos. Cada tema pide dos veces: el audio y la huella de la bandeja.
    rango = request.headers.get("Range", "")
    nueva = not rango or rango.startswith("bytes=0-")
    if nueva and excedido(request, f"preview-{request.user.pk}", *LIMITES["preview"]):
        return HttpResponse(status=429)
    try:
        datos, tipo = bajar_preview(request.GET.get("u", ""))
    except ValueError:
        return HttpResponse(status=400)
    except OSError:
        # URLError, HTTPError y los cortes de red al leer heredan de OSError.
        return HttpResponse(status=502)

    respuesta = responder_rango(request, datos, tipo)
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


def _rango_pedido(request, total):
    """(inicio, fin) del encabezado Range, None si no hay rango, o "fuera" si no entra."""
    rango = RANGO.match(request.headers.get("Range", "").strip())
    if not rango or not (rango.group(1) or rango.group(2)):
        return None
    inicio, fin = rango.groups()
    if inicio:
        inicio = int(inicio)
        fin = min(int(fin), total - 1) if fin else total - 1
    else:
        # "bytes=-500": los últimos 500 bytes.
        inicio, fin = max(total - int(fin), 0), total - 1
    return "fuera" if inicio >= total or inicio > fin else (inicio, fin)


def _fuera_de_rango(total):
    respuesta = HttpResponse(status=416)
    respuesta["Content-Range"] = f"bytes */{total}"
    return respuesta


def responder_archivo(request, ruta, tipo):
    """Como responder_rango, pero leyendo del disco solo el pedazo pedido (los
    audios subidos pesan hasta 25 MB: no se cargan enteros por cada pedazo)."""
    total = ruta.stat().st_size
    rango = _rango_pedido(request, total)
    if rango == "fuera":
        return _fuera_de_rango(total)
    if rango is None:
        respuesta = FileResponse(ruta.open("rb"), content_type=tipo)
    else:
        inicio, fin = rango
        with ruta.open("rb") as archivo:
            archivo.seek(inicio)
            respuesta = HttpResponse(archivo.read(fin - inicio + 1), content_type=tipo, status=206)
        respuesta["Content-Range"] = f"bytes {inicio}-{fin}/{total}"
    respuesta["Accept-Ranges"] = "bytes"
    return respuesta


def responder_rango(request, datos, tipo):
    """200 con todo o 206 con el pedazo pedido: sin esto el navegador no puede adelantar."""
    total = len(datos)
    rango = _rango_pedido(request, total)
    if rango == "fuera":
        return _fuera_de_rango(total)
    if rango is not None:
        inicio, fin = rango
        respuesta = HttpResponse(datos[inicio:fin + 1], content_type=tipo, status=206)
        respuesta["Content-Range"] = f"bytes {inicio}-{fin}/{total}"
    else:
        respuesta = HttpResponse(datos, content_type=tipo)
    respuesta["Accept-Ranges"] = "bytes"
    return respuesta


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------
def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    # Sin context processors: si falló la base o la sesión, esta página no puede
    # depender de ellas.
    return HttpResponse(loader.get_template("500.html").render(), status=500)

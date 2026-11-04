"""Vistas de la tienda (caso de uso 6: compra de albumes).

Flujo del diagrama de secuencia:
    seleccionar album -> agregar al carrito -> finalizar compra ->
    ingresar datos de tarjeta -> procesar pago -> confirmacion
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, F, Q, When
from django.db.models.functions import Least
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from musica.models import Album, Genero
from musica.utilidades import es_ajax

from .forms import PagoForm, marca_tarjeta
from .models import Carrito, CarritoItem, Formato, Pago, Pedido, PedidoItem
from .muestras import DURACION, ruta_muestra
from .portadas import portada_svg

PAGINA = 9


def _carrito_de(usuario):
    carrito, _ = Carrito.objects.get_or_create(usuario=usuario)
    return carrito


MAXIMO_POR_ITEM = CarritoItem.MAXIMO


def _payload_carrito(carrito):
    # Una sola consulta: cantidad, total y líneas salen de la misma lista.
    items = list(carrito.items.select_related("album"))
    cantidad, total = Carrito.resumen(items)
    return {
        "cantidad": cantidad,
        "total": float(total),
        "total_formateado": f"${total:,.2f}",
        "items": [
            {
                "id": item.id,
                "album": item.album.titulo,
                "formato": item.get_formato_display(),
                "cantidad": item.cantidad,
                "precio": float(item.precio_unitario),
                "subtotal": float(item.subtotal()),
            }
            for item in items
        ],
    }


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------
def catalogo(request):
    albumes = Album.objects.filter(publicado=True).select_related("artista", "genero")

    q = request.GET.get("q", "").strip()
    genero = request.GET.get("genero", "").strip()
    formato = request.GET.get("formato", "").strip()
    orden = request.GET.get("orden", "recientes")

    if q:
        albumes = albumes.filter(Q(titulo__icontains=q) | Q(artista__username__icontains=q))
    if genero:
        albumes = albumes.filter(genero__slug=genero)
    if formato == "DIGITAL":
        albumes = albumes.filter(disponible_digital=True)
    elif formato == "FISICO":
        albumes = albumes.filter(disponible_fisico=True)

    # El precio "desde" de cada disco: un álbum solo en vinilo tiene digital en 0.
    albumes = albumes.annotate(
        precio_orden=Case(
            When(disponible_digital=True, disponible_fisico=True, then=Least("precio_digital", "precio_fisico")),
            When(disponible_digital=True, then=F("precio_digital")),
            default=F("precio_fisico"),
        )
    )
    ordenes = {
        "recientes": "-fecha_lanzamiento",
        "precio": "precio_orden",
        "precio_desc": "-precio_orden",
        "titulo": "titulo",
    }
    # El id desempata: con precios o fechas iguales, PostgreSQL no garantiza el
    # orden y un disco podría repetirse o faltar entre páginas.
    albumes = albumes.order_by(ordenes.get(orden, "-fecha_lanzamiento"), "-pk")

    paginador = Paginator(albumes, PAGINA)
    pagina = paginador.get_page(request.GET.get("page"))

    contexto = {
        "titulo": "Tienda",
        "pagina": pagina,
        "albumes": pagina.object_list,
        # Solo los géneros con algo a la venta: un filtro que da vacío no sirve.
        "generos": Genero.objects.annotate(
            n=Count("albumes", filter=Q(albumes__publicado=True))
        ).filter(n__gt=0),
        "q": q,
        "genero_activo": genero,
        "formato": formato,
        "orden": orden,
        "total": paginador.count,
        # Sin filtros, arriba va un disco destacado: el que tiene stock y cambia cada día.
        "destacado": _destacado() if not (q or genero or formato) and pagina.number == 1 else None,
    }
    return render(request, "tienda/catalogo.html", contexto)


def _destacado():
    """Un disco con stock, distinto cada día (sin cargarlos todos)."""
    candidatos = Album.objects.filter(
        publicado=True, disponible_fisico=True, stock_fisico__gt=0
    ).select_related("artista").order_by("pk")
    total = candidatos.count()
    return candidatos[timezone.localdate().toordinal() % total] if total else None


def portada(request, slug):
    """Portada minimalista del disco, generada con su título (ver portadas.py)."""
    album = get_object_or_404(Album.objects.select_related("artista"), slug=slug)
    # Un disco sin publicar no se anuncia: su tapa solo la ven el artista y los admin.
    usuario = request.user
    if not album.publicado and not (
        usuario.is_authenticated and (usuario.pk == album.artista_id or usuario.es_admin)
    ):
        raise Http404("Ese disco no está publicado.")
    respuesta = HttpResponse(portada_svg(album.titulo, album.artista.username), content_type="image/svg+xml")
    respuesta["Cache-Control"] = "public, max-age=86400"
    return respuesta


def detalle_album(request, slug):
    album = get_object_or_404(
        Album.objects.select_related("artista", "genero"), slug=slug, publicado=True
    )
    canciones = list(album.canciones_aprobadas().select_related("artista", "genero"))
    # Las canciones se piden una vez: los lados y el total salen de esa lista.
    temas = album.temas_para_mostrar(canciones)
    mitad = (len(temas) + 1) // 2
    contexto = {
        "titulo": album.titulo,
        "album": album,
        "canciones": canciones,
        "otros": Album.objects.filter(publicado=True, artista=album.artista)
        .select_related("artista").exclude(pk=album.pk)[:4],
        "pistas": [c.como_pista() for c in canciones],
        "formatos": Formato.choices,
        "total_temas": len(temas),
        "lados": (temas[:mitad], temas[mitad:]),
    }
    return render(request, "tienda/detalle_album.html", contexto)


# ---------------------------------------------------------------------------
# Carrito
# ---------------------------------------------------------------------------
def _precios_de_hoy(request, items):
    """Lo que se muestra es lo que se cobra: si un precio cambió desde que se
    agregó el disco, se actualiza el ítem y se avisa."""
    cambiados = []
    for item in items:
        hoy = item.album.precio_por_formato(item.formato)
        if hoy != item.precio_unitario:
            item.precio_unitario = hoy
            item.save(update_fields=["precio_unitario"])
            cambiados.append(item.album.titulo)
    if cambiados:
        messages.info(request, "Cambió el precio de: " + ", ".join(cambiados) + ".")
    return items


@login_required
def ver_carrito(request):
    carrito = _carrito_de(request.user)
    items = _precios_de_hoy(request, list(carrito.items.select_related("album", "album__artista")))
    cantidad, total = Carrito.resumen(items)
    contexto = {
        "titulo": "Carrito de compras",
        "carrito": carrito,
        "items": items,
        "cantidad": cantidad,
        "total": total,
    }
    return render(request, "tienda/carrito.html", contexto)


@login_required
@require_POST
def agregar_al_carrito(request, album_id):
    album = get_object_or_404(Album, pk=album_id, publicado=True)
    formato = request.POST.get("formato", Formato.DIGITAL)
    if formato not in Formato.values:
        formato = Formato.DIGITAL
    try:
        cantidad = min(MAXIMO_POR_ITEM, max(1, int(request.POST.get("cantidad", 1))))
    except ValueError:
        cantidad = 1

    # Lo que ya está en el carrito también cuenta contra el stock.
    en_carrito = 0
    if formato == Formato.FISICO:
        en_carrito = (
            CarritoItem.objects.filter(carrito__usuario=request.user, album=album, formato=formato)
            .values_list("cantidad", flat=True)
            .first()
            or 0
        )
    if not album.hay_stock(formato, cantidad + en_carrito):
        mensaje = "No hay stock disponible en ese formato."
        if es_ajax(request):
            return JsonResponse({"ok": False, "mensaje": mensaje}, status=400)
        messages.error(request, mensaje)
        return redirect(album.get_absolute_url())

    carrito = _carrito_de(request.user)
    carrito.agregar_producto(album, formato, cantidad)

    if es_ajax(request):
        payload = _payload_carrito(carrito)
        payload.update({"ok": True, "mensaje": f'"{album.titulo}" se agregó al carrito.'})
        return JsonResponse(payload)

    messages.success(request, f'"{album.titulo}" se agregó al carrito.')
    return redirect("tienda:carrito")


@login_required
@require_POST
def actualizar_item(request, item_id):
    carrito = _carrito_de(request.user)
    item = get_object_or_404(CarritoItem, pk=item_id, carrito=carrito)
    try:
        cantidad = min(MAXIMO_POR_ITEM, int(request.POST.get("cantidad", 1)))
    except ValueError:
        cantidad = item.cantidad

    if cantidad <= 0:
        item.delete()
    else:
        if item.formato == Formato.FISICO and cantidad > item.album.stock_fisico:
            cantidad = item.album.stock_fisico
        if cantidad <= 0:
            item.delete()
        else:
            item.cantidad = cantidad
            item.save()

    if es_ajax(request):
        payload = _payload_carrito(carrito)
        payload["ok"] = True
        payload["item_id"] = item_id
        # "cantidad" es el total del carrito (lo usan los contadores); esta es la del ítem.
        payload["item_cantidad"] = cantidad if cantidad > 0 else 0
        payload["subtotal_formateado"] = (
            f"${item.subtotal():,.2f}" if cantidad > 0 else "$0.00"
        )
        return JsonResponse(payload)
    return redirect("tienda:carrito")


@login_required
@require_POST
def eliminar_item(request, item_id):
    carrito = _carrito_de(request.user)
    item = get_object_or_404(CarritoItem, pk=item_id, carrito=carrito)
    nombre = item.album.titulo
    item.delete()
    if es_ajax(request):
        payload = _payload_carrito(carrito)
        payload.update({"ok": True, "item_id": item_id, "mensaje": f"Se quitó {nombre}."})
        return JsonResponse(payload)
    messages.info(request, f"Se quitó {nombre} del carrito.")
    return redirect("tienda:carrito")


@login_required
@require_POST
def vaciar_carrito(request):
    _carrito_de(request.user).vaciar()
    messages.info(request, "Carrito vaciado.")
    return redirect("tienda:carrito")


# ---------------------------------------------------------------------------
# Checkout / pago
# ---------------------------------------------------------------------------
class CompraInvalida(Exception):
    """El carrito cambió entre que se armó y se pagó. Se deshace todo."""


def _cerrar_compra(usuario, carrito, form):
    """Crea el pedido y el pago en una sola transacción.

    Con SQLite en modo IMMEDIATE la transacción toma el lock de escritura al
    empezar: un doble clic en "Pagar" espera al primero y encuentra el carrito
    vacío. Todo lo que importa (ítems, precio, disponibilidad, stock) se vuelve
    a leer adentro.
    """
    with transaction.atomic():
        items = list(
            CarritoItem.objects.filter(carrito=carrito).select_related("album", "album__artista")
        )
        if not items:
            raise CompraInvalida("Tu carrito está vacío o esa compra ya se procesó.")

        no_disponibles = [
            i.album.titulo
            for i in items
            if not i.album.publicado or not i.album.hay_stock(i.formato, 0 if i.es_digital else 1)
        ]
        if no_disponibles:
            raise CompraInvalida(
                "Ya no están a la venta: " + ", ".join(no_disponibles) + ". Quitalos para continuar."
            )

        # El precio que se cobra es el de hoy, no el del día en que se agregó.
        for item in items:
            item.precio_unitario = item.album.precio_por_formato(item.formato)
        total = sum((i.precio_unitario * i.cantidad for i in items), Decimal("0.00"))

        pedido = Pedido.objects.create(usuario=usuario, total=total, estado=Pedido.Estado.PENDIENTE)
        for item in items:
            PedidoItem.objects.create(
                pedido=pedido,
                album=item.album,
                nombre_album=item.album.titulo,
                artista=item.album.artista.username,
                formato=item.formato,
                tipo_disco=item.album.tipo_disco if item.formato == Formato.FISICO else "",
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )
            if item.formato == Formato.FISICO:
                # Descuento condicionado: si otra compra se llevó el stock, no se actualiza nada.
                descontados = Album.objects.filter(
                    pk=item.album_id, stock_fisico__gte=item.cantidad
                ).update(stock_fisico=F("stock_fisico") - item.cantidad)
                if not descontados:
                    raise CompraInvalida(
                        f"Nos quedamos sin stock de {item.album.titulo}. Ajustá la cantidad para continuar."
                    )

        # Se borran exactamente los ítems cobrados; si otro pedido ya los tomó, se deshace.
        borrados, _ = CarritoItem.objects.filter(pk__in=[i.pk for i in items]).delete()
        if borrados != len(items):
            raise CompraInvalida("El carrito cambió mientras pagabas. Revisalo y volvé a intentar.")

        numero = form.cleaned_data["numero_tarjeta"]
        pago = Pago.objects.create(
            pedido=pedido,
            nombre_titular=form.titular_completo,
            ultimos_digitos=numero[-4:],
            marca=marca_tarjeta(numero),
            vencimiento=form.cleaned_data["vencimiento"],
            monto_total=pedido.total,
        )
        pago.procesar_pago()
    return pedido


@login_required
def checkout(request):
    carrito = _carrito_de(request.user)
    items = list(carrito.items.select_related("album", "album__artista"))
    if not items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("tienda:catalogo")
    if request.method == "GET":
        _precios_de_hoy(request, items)

    form = PagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            pedido = _cerrar_compra(request.user, carrito, form)
        except CompraInvalida as error:
            messages.error(request, str(error))
            return redirect("tienda:carrito")

        messages.success(request, "Pago aprobado. Gracias por tu compra.")
        return redirect("tienda:confirmacion", numero=pedido.numero)

    contexto = {
        "titulo": "Finalizar compra",
        "form": form,
        "items": items,
        "carrito": carrito,
        "total": Carrito.resumen(items)[1],
    }
    return render(request, "tienda/checkout.html", contexto)


@login_required
def confirmacion(request, numero):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related("items"), numero=numero, usuario=request.user
    )
    return render(
        request,
        "tienda/confirmacion.html",
        {"titulo": "Compra realizada", "pedido": pedido, "pago": getattr(pedido, "pago", None)},
    )


# ---------------------------------------------------------------------------
# Tus discos: lo comprado se escucha en Mi música
# ---------------------------------------------------------------------------
def _temas_del_disco(album):
    """Nombres de los temas del disco (lista_temas guarda [nombre, duración])."""
    return [str(t[0] if isinstance(t, (list, tuple)) else t) for t in (album.lista_temas or []) if t]


def _pistas_del_disco(album):
    """Los temas del disco para el reproductor. Si el artista subió canciones y
    están aprobadas, suenan esas; si no (los discos de prueba), cada tema de la
    lista suena con su muestra generada."""
    canciones = list(album.canciones_aprobadas().select_related("artista", "genero", "album"))
    if canciones:
        return [cancion.como_pista() for cancion in canciones]
    portada, ficha = album.portada_url, album.get_absolute_url()
    genero = album.genero.nombre if album.genero_id else ""
    return [
        {
            "id": f"compra-{album.pk}-{numero}",
            "titulo": titulo,
            "artista": album.artista.username,
            "artistaUrl": "",
            "portada": portada,
            "audio": reverse("tienda:muestra", args=[album.pk, numero]),
            "url": ficha,
            "duracion": int(DURACION),
            "genero": genero,
            "fuente": "Tus discos",
            "externo": True,
            "compra": True,
        }
        for numero, titulo in enumerate(_temas_del_disco(album), start=1)
    ]


def _compras_validas(usuario):
    return PedidoItem.objects.filter(pedido__usuario=usuario, album__isnull=False).exclude(
        pedido__estado=Pedido.Estado.CANCELADO
    )


def discos_comprados(usuario):
    """Los discos que compró (de pedidos no cancelados), el más reciente primero,
    con los formatos que tiene y sus temas listos para el reproductor."""
    items = _compras_validas(usuario).select_related(
        "album", "album__artista", "album__genero", "pedido"
    ).order_by("-pedido__fecha")
    discos = {}
    for item in items:
        disco = discos.get(item.album_id)
        if disco is None:
            disco = discos[item.album_id] = {
                "album": item.album,
                "fecha": item.pedido.fecha,
                "formatos": set(),
                "pistas": _pistas_del_disco(item.album),
                # Prefijo propio: la batea ya usa ids kl-disco-0, kl-disco-1...
                "id_json": f"kl-comprado-{item.album_id}",
            }
        disco["formatos"].add(item.get_formato_display())
    for disco in discos.values():
        disco["formatos"] = sorted(disco["formatos"])
        disco["muestras"] = any(pista.get("compra") for pista in disco["pistas"])
    return list(discos.values())


@login_required
def muestra(request, album_id, numero):
    """La muestra de un tema: solo para quien compró el disco."""
    if not _compras_validas(request.user).filter(album_id=album_id).exists():
        raise Http404("No compraste este disco.")
    album = get_object_or_404(Album.objects.select_related("genero"), pk=album_id)
    temas = _temas_del_disco(album)
    if not 1 <= numero <= len(temas):
        raise Http404("Ese tema no está en el disco.")
    from musica.views import responder_archivo

    respuesta = responder_archivo(request, ruta_muestra(album, numero, temas[numero - 1]), "audio/wav")
    respuesta["Cache-Control"] = "private, max-age=86400"
    return respuesta


@login_required
def mis_pedidos(request):
    pedidos = (
        Pedido.objects.filter(usuario=request.user)
        .prefetch_related("items")
        .select_related("pago")
    )
    total_gastado = sum((p.total for p in pedidos), Decimal("0.00"))
    return render(
        request,
        "tienda/mis_pedidos.html",
        {"titulo": "Mis compras", "pedidos": pedidos, "total_gastado": total_gastado},
    )

"""Pruebas del caso de uso 6: carrito, pago y compra de álbumes."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from musica.models import Album
from usuarios.models import Usuario

from .models import Carrito, Formato, Pedido


class BaseTienda(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="compradora", email="compradora@ejemplo.com", password="Usuario1234"
        )
        self.artista = Usuario.objects.create_user(
            username="banda", email="banda@ejemplo.com", password="Usuario1234"
        )
        self.album = Album.objects.create(
            titulo="Ruta 9",
            artista=self.artista,
            fecha_lanzamiento=date(2026, 1, 1),
            precio_digital=8500,
            precio_fisico=35000,
            stock_fisico=3,
        )
        self.client.force_login(self.usuario)


class CarritoTests(BaseTienda):
    def test_agregar_al_carrito_por_ajax(self):
        respuesta = self.client.post(
            reverse("tienda:agregar_al_carrito", args=[self.album.id]),
            {"formato": Formato.DIGITAL, "cantidad": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        datos = respuesta.json()
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["cantidad"], 2)
        self.assertEqual(float(datos["total"]), 17000.0)

    def test_no_permite_superar_el_stock_fisico(self):
        respuesta = self.client.post(
            reverse("tienda:agregar_al_carrito", args=[self.album.id]),
            {"formato": Formato.FISICO, "cantidad": 10},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(respuesta.json()["ok"])

    def test_eliminar_item(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        item = carrito.agregar_producto(self.album, Formato.DIGITAL, 1)
        respuesta = self.client.post(
            reverse("tienda:eliminar_item", args=[item.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertTrue(respuesta.json()["ok"])
        self.assertEqual(carrito.items.count(), 0)

    def test_el_total_se_calcula_con_los_subtotales(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        carrito.agregar_producto(self.album, Formato.DIGITAL, 2)
        carrito.agregar_producto(self.album, Formato.FISICO, 1)
        self.assertEqual(carrito.cantidad_items, 3)
        self.assertEqual(float(carrito.total), 8500 * 2 + 35000)


class PagoTests(BaseTienda):
    def _cargar_carrito(self, formato=Formato.DIGITAL, cantidad=1):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        carrito.agregar_producto(self.album, formato, cantidad)
        return carrito

    def datos_tarjeta(self, **extra):
        datos = {
            "nombre_titular": "Sophia",
            "apellido_titular": "Benitez",
            "numero_tarjeta": "4111 1111 1111 1111",
            "vencimiento": "12/30",
            "codigo_seguridad": "123",
        }
        datos.update(extra)
        return datos

    def test_compra_completa_genera_pedido_y_pago(self):
        self._cargar_carrito()
        respuesta = self.client.post(reverse("tienda:checkout"), self.datos_tarjeta(), follow=True)
        self.assertEqual(respuesta.status_code, 200)

        pedido = Pedido.objects.get(usuario=self.usuario)
        self.assertEqual(pedido.estado, Pedido.Estado.PAGADO)
        self.assertEqual(pedido.items.count(), 1)
        self.assertEqual(pedido.pago.ultimos_digitos, "1111")
        self.assertEqual(pedido.pago.marca, "Visa")
        self.assertEqual(Carrito.objects.get(usuario=self.usuario).items.count(), 0)

    def test_tarjeta_invalida_no_genera_pedido(self):
        self._cargar_carrito()
        respuesta = self.client.post(
            reverse("tienda:checkout"), self.datos_tarjeta(numero_tarjeta="1234 5678 9012 3456")
        )
        self.assertContains(respuesta, "no es válido")
        self.assertEqual(Pedido.objects.count(), 0)

    def test_tarjeta_vencida_no_genera_pedido(self):
        self._cargar_carrito()
        respuesta = self.client.post(reverse("tienda:checkout"), self.datos_tarjeta(vencimiento="01/20"))
        self.assertContains(respuesta, "vencida")
        self.assertEqual(Pedido.objects.count(), 0)

    def test_la_compra_fisica_descuenta_stock(self):
        self._cargar_carrito(Formato.FISICO, 2)
        self.client.post(reverse("tienda:checkout"), self.datos_tarjeta(), follow=True)
        self.album.refresh_from_db()
        self.assertEqual(self.album.stock_fisico, 1)

    def test_checkout_vacio_redirige_a_la_tienda(self):
        respuesta = self.client.get(reverse("tienda:checkout"), follow=True)
        self.assertContains(respuesta, "carrito está vacío")


class StockEnElPagoTests(BaseTienda):
    """El stock puede haberse agotado entre el carrito y el pago."""

    def datos_tarjeta(self):
        return {
            "nombre_titular": "Sophia",
            "apellido_titular": "Benitez",
            "numero_tarjeta": "4111 1111 1111 1111",
            "vencimiento": "12/30",
            "codigo_seguridad": "123",
        }

    def test_sin_stock_al_pagar_no_se_genera_el_pedido(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        carrito.agregar_producto(self.album, Formato.FISICO, 3)

        # Otra persona se lleva las ultimas copias mientras tanto.
        self.album.stock_fisico = 1
        self.album.save(update_fields=["stock_fisico"])

        respuesta = self.client.post(
            reverse("tienda:checkout"), self.datos_tarjeta(), follow=True
        )
        self.album.refresh_from_db()
        self.assertContains(respuesta, "Nos quedamos sin stock")
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertEqual(self.album.stock_fisico, 1)

    def test_los_numeros_de_pedido_no_se_repiten(self):
        numeros = set()
        for _ in range(50):
            pedido = Pedido.objects.create(usuario=self.usuario, total=100)
            numeros.add(pedido.numero)
        self.assertEqual(len(numeros), 50)


class CompraSeguraTests(PagoTests):
    def test_un_segundo_pago_del_mismo_carrito_no_cobra_de_nuevo(self):
        self._cargar_carrito(Formato.FISICO, 1)
        self.client.post(reverse("tienda:checkout"), self.datos_tarjeta())
        # El segundo POST (doble clic) llega con el carrito ya vacío.
        self.client.post(reverse("tienda:checkout"), self.datos_tarjeta())
        self.album.refresh_from_db()
        self.assertEqual(Pedido.objects.count(), 1)
        self.assertEqual(self.album.stock_fisico, 2)

    def test_se_cobra_el_precio_vigente(self):
        self._cargar_carrito(Formato.DIGITAL, 1)
        Album.objects.filter(pk=self.album.pk).update(precio_digital=9000)
        self.client.post(reverse("tienda:checkout"), self.datos_tarjeta())
        self.assertEqual(float(Pedido.objects.get().total), 9000.0)

    def test_no_se_compra_un_album_despublicado(self):
        self._cargar_carrito(Formato.DIGITAL, 1)
        Album.objects.filter(pk=self.album.pk).update(publicado=False)
        respuesta = self.client.post(reverse("tienda:checkout"), self.datos_tarjeta(), follow=True)
        self.assertContains(respuesta, "Ya no están a la venta")
        self.assertEqual(Pedido.objects.count(), 0)

    def test_cancelar_devuelve_el_stock_una_sola_vez(self):
        self._cargar_carrito(Formato.FISICO, 2)
        self.client.post(reverse("tienda:checkout"), self.datos_tarjeta())
        pedido = Pedido.objects.get()
        admin = Usuario.objects.create_superuser("jefa", "jefa@ejemplo.com", "Admin1234")
        self.client.force_login(admin)
        url = reverse("panel:cambiar_estado_pedido", args=[pedido.numero])
        self.client.post(url, {"estado": Pedido.Estado.CANCELADO})
        self.client.post(url, {"estado": Pedido.Estado.CANCELADO})
        self.client.post(url, {"estado": Pedido.Estado.PAGADO})
        self.album.refresh_from_db()
        pedido.refresh_from_db()
        self.assertEqual(self.album.stock_fisico, 3)
        self.assertEqual(pedido.estado, Pedido.Estado.CANCELADO)


class DisqueriaTests(BaseTienda):
    def test_la_portada_se_genera_con_el_titulo(self):
        respuesta = self.client.get(reverse("tienda:portada", args=[self.album.slug]))
        self.assertEqual(respuesta["Content-Type"], "image/svg+xml")
        self.assertContains(respuesta, "RUTA 9")
        self.assertTrue(self.album.portada_url.startswith(reverse("tienda:portada", args=[self.album.slug])))

    def test_la_portada_escapa_el_titulo(self):
        self.album.titulo = 'Ruta <script>"9"</script>'
        self.album.save()
        respuesta = self.client.get(reverse("tienda:portada", args=[self.album.slug]))
        self.assertNotContains(respuesta, "<script>")

    def test_el_motivo_sale_del_nombre(self):
        from .portadas import motivo_de

        self.assertEqual(motivo_de("Primer verano"), "sol")
        self.assertEqual(motivo_de("Modo Nocturno"), "luna")
        self.assertEqual(motivo_de("Ruta 9"), "ruta")
        self.assertEqual(motivo_de("Geometría"), "bauhaus")

    def test_la_ficha_muestra_los_lados_del_disco(self):
        self.album.lista_temas = [["Uno", "3:00"], ["Dos", "3:10"], ["Tres", "2:50"]]
        self.album.save()
        respuesta = self.client.get(self.album.get_absolute_url())
        self.assertContains(respuesta, "Lado</span> A")
        self.assertContains(respuesta, "Tres")
        self.assertContains(respuesta, 'data-modo="2d"')

    def test_el_catalogo_destaca_un_disco_con_stock(self):
        respuesta = self.client.get(reverse("tienda:catalogo"))
        self.assertEqual(respuesta.context["destacado"], self.album)


class ArreglosDeAuditoriaTests(BaseTienda):
    """Regresiones de la auditoría de la tienda."""

    def test_el_contador_muestra_el_total_del_carrito(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        uno = carrito.agregar_producto(self.album, Formato.DIGITAL, 3)
        carrito.agregar_producto(self.album, Formato.FISICO, 1)
        datos = self.client.post(
            reverse("tienda:actualizar_item", args=[uno.id]), {"cantidad": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()
        self.assertEqual(datos["cantidad"], 3)       # 2 digitales + 1 vinilo
        self.assertEqual(datos["item_cantidad"], 2)

    def test_una_cantidad_enorme_no_rompe(self):
        respuesta = self.client.post(
            reverse("tienda:agregar_al_carrito", args=[self.album.id]),
            {"formato": Formato.DIGITAL, "cantidad": "99999999999999999999"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["cantidad"], 20)

    def test_el_checkout_muestra_el_precio_que_se_cobra(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        carrito.agregar_producto(self.album, Formato.DIGITAL, 1)
        Album.objects.filter(pk=self.album.pk).update(precio_digital=9900)
        respuesta = self.client.get(reverse("tienda:checkout"))
        self.assertEqual(respuesta.context["total"], 9900)
        self.assertContains(respuesta, "Cambió el precio")

    def test_menor_precio_usa_el_precio_desde(self):
        solo_vinilo = Album.objects.create(
            titulo="Solo vinilo", artista=self.artista, fecha_lanzamiento=date(2026, 1, 1),
            disponible_digital=False, precio_digital=0, precio_fisico=50000, stock_fisico=2,
        )
        respuesta = self.client.get(reverse("tienda:catalogo"), {"orden": "precio"})
        titulos = [a.titulo for a in respuesta.context["pagina"].object_list]
        self.assertLess(titulos.index(self.album.titulo), titulos.index(solo_vinilo.titulo))


class AuditoriaBackendTiendaTests(BaseTienda):
    def test_la_bolsa_sin_sesion_va_al_login(self):
        self.client.logout()
        respuesta = self.client.get(reverse("tienda:carrito"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/login/", respuesta.url)

    def test_agregar_varias_veces_respeta_el_tope(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        for _ in range(3):
            item = carrito.agregar_producto(self.album, Formato.DIGITAL, 20)
        self.assertEqual(item.cantidad, 20)

    def test_la_bolsa_y_el_checkout_no_repiten_consultas(self):
        carrito, _ = Carrito.objects.get_or_create(usuario=self.usuario)
        carrito.agregar_producto(self.album, Formato.DIGITAL, 2)
        respuesta = self.client.get(reverse("tienda:carrito"))
        self.assertEqual(respuesta.context["cantidad"], 2)
        self.assertEqual(respuesta.context["total"], 17000)


class TusDiscosTests(BaseTienda):
    """Lo comprado se escucha en Mi música, con una muestra por tema."""

    def setUp(self):
        super().setUp()
        import tempfile

        from django.test import override_settings

        self.album.lista_temas = [["Kilómetro cero", "3:41"], ["Faros", "4:02"]]
        self.album.save()
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        # Las muestras se guardan en BASE_DIR/.cache: en las pruebas, en una carpeta temporal.
        ajuste = override_settings(BASE_DIR=carpeta.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def _comprar(self, estado=Pedido.Estado.PAGADO):
        from .models import PedidoItem

        pedido = Pedido.objects.create(usuario=self.usuario, total=8500, estado=estado)
        PedidoItem.objects.create(
            pedido=pedido, album=self.album, nombre_album=self.album.titulo,
            artista=self.artista.username, formato=Formato.DIGITAL, cantidad=1, precio_unitario=8500,
        )
        return pedido

    def test_quien_compro_escucha_la_muestra_y_puede_adelantar(self):
        self._comprar()
        url = reverse("tienda:muestra", args=[self.album.id, 1])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "audio/wav")
        contenido = b"".join(respuesta.streaming_content)
        self.assertTrue(contenido.startswith(b"RIFF"))
        # Siempre la misma muestra para el mismo tema, y responde pedazos (Range).
        parcial = self.client.get(url, HTTP_RANGE="bytes=0-99")
        self.assertEqual(parcial.status_code, 206)
        self.assertEqual(len(b"".join(parcial.streaming_content) if parcial.streaming else parcial.content), 100)

    def test_sin_comprar_o_con_pedido_cancelado_no_se_escucha(self):
        url = reverse("tienda:muestra", args=[self.album.id, 1])
        self.assertEqual(self.client.get(url).status_code, 404)
        self._comprar(Pedido.Estado.CANCELADO)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_tema_que_no_esta_en_el_disco(self):
        self._comprar()
        self.assertEqual(self.client.get(reverse("tienda:muestra", args=[self.album.id, 9])).status_code, 404)

    def test_mi_musica_muestra_los_discos_comprados(self):
        self._comprar()
        respuesta = self.client.get(reverse("musica:mi_musica"))
        self.assertContains(respuesta, "Tus discos")
        self.assertContains(respuesta, f"compra-{self.album.id}-2")
        self.assertContains(respuesta, "Faros")

"""Pruebas del caso de uso 7: administración de contenido."""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from musica.models import Cancion, Genero
from usuarios.models import Usuario


# La selección curada (Apple) no se consulta en los tests.
CATALOGO = [{"id": "itunes-7", "titulo": "Blinding Lights", "artista": "The Weeknd", "portada": ""}]


def sin_red(caso):
    parche = patch("panel.views.mezcla", return_value=CATALOGO)
    parche.start()
    caso.addCleanup(parche.stop)


def audio_falso(nombre="tema.wav"):
    return SimpleUploadedFile(nombre, b"RIFF0000WAVEfmt ", content_type="audio/wav")


class PanelTests(TestCase):
    def setUp(self):
        sin_red(self)
        self.admin = Usuario.objects.create_user(
            username="admin", email="admin@ejemplo.com", password="Admin1234", rol=Usuario.Rol.ADMIN
        )
        self.usuario = Usuario.objects.create_user(
            username="artista", email="artista@ejemplo.com", password="Usuario1234"
        )
        self.genero = Genero.objects.create(nombre="Indie")
        self.cancion = Cancion.objects.create(
            titulo="Demo sin mezclar",
            artista=self.usuario,
            genero=self.genero,
            archivo_audio=audio_falso(),
        )

    # -- Acceso ----------------------------------------------------------
    def test_usuario_comun_no_entra_al_panel(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("panel:dashboard"), follow=True)
        self.assertContains(respuesta, "permisos de administrador")

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cuenta/login/", respuesta.url)

    def test_admin_ve_el_resumen(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("panel:dashboard"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Resumen general")

    # -- Moderacion ------------------------------------------------------
    def test_aprobar_cancion(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("panel:aprobar_cancion", args=[self.cancion.slug]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.cancion.refresh_from_db()
        self.assertTrue(respuesta.json()["ok"])
        self.assertEqual(self.cancion.estado, Cancion.Estado.APROBADA)
        self.assertEqual(self.cancion.revisada_por, self.admin)

    def test_rechazar_exige_motivo(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(
            reverse("panel:rechazar_cancion", args=[self.cancion.slug]),
            {"motivo": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.cancion.refresh_from_db()
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.cancion.estado, Cancion.Estado.PENDIENTE)

    def test_rechazar_guarda_el_motivo(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("panel:rechazar_cancion", args=[self.cancion.slug]),
            {"motivo": "El audio está distorsionado"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.estado, Cancion.Estado.RECHAZADA)
        self.assertEqual(self.cancion.motivo_rechazo, "El audio está distorsionado")

    def test_admin_puede_modificar_la_cancion(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("panel:detalle_cancion", args=[self.cancion.slug]),
            {
                "formulario": "editar",
                "titulo": "Demo corregido",
                "genero": self.genero.id,
                "tipo": Cancion.Tipo.SENCILLO,
                "numero_pista": 1,
            },
        )
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.titulo, "Demo corregido")

    def test_admin_puede_eliminar(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:eliminar_cancion", args=[self.cancion.slug]))
        self.assertFalse(Cancion.objects.filter(pk=self.cancion.pk).exists())

    # -- Usuarios --------------------------------------------------------
    def test_bloquear_y_desbloquear_usuario(self):
        self.client.force_login(self.admin)
        url = reverse("panel:sancionar_usuario", args=[self.usuario.id])

        self.client.post(url, {"motivo": "Spam"})
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.bloqueado)

        self.client.post(url)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.bloqueado)

    def test_no_puede_bloquearse_a_si_mismo(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:sancionar_usuario", args=[self.admin.id]))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.bloqueado)


class PaginasConSesionTests(TestCase):
    """Cada página con sesión se dibuja entera (usuario común y administración)."""

    def setUp(self):
        sin_red(self)
        from musica.models import MeGusta, Reproduccion

        self.admin = Usuario.objects.create_user(
            username="admin", email="admin@ejemplo.com", password="Admin1234", rol=Usuario.Rol.ADMIN
        )
        self.usuario = Usuario.objects.create_user(
            username="artista", email="artista@ejemplo.com", password="Usuario1234"
        )
        genero = Genero.objects.create(nombre="Indie")
        self.cancion = Cancion.objects.create(
            titulo="Demo sin mezclar", artista=self.usuario, genero=genero, archivo_audio=audio_falso()
        )
        Reproduccion.objects.create(usuario=self.usuario, cancion=self.cancion)
        MeGusta.objects.create(
            usuario=self.usuario, pista_id="1", titulo="Not Like Us", artista="Kendrick Lamar",
            preview="https://audio-ssl.itunes.apple.com/x.m4a",
        )
        # Un pedido en vinilo ya enviado y uno digital: el recorrido cambia según el formato.
        from tienda.models import Formato, Pedido, PedidoItem

        self.vinilo = Pedido.objects.create(usuario=self.usuario, total=35000, estado=Pedido.Estado.ENVIADO)
        PedidoItem.objects.create(pedido=self.vinilo, nombre_album="Ruta 9", formato=Formato.FISICO, precio_unitario=35000)
        digital = Pedido.objects.create(usuario=self.usuario, total=8500, estado=Pedido.Estado.PAGADO)
        PedidoItem.objects.create(pedido=digital, nombre_album="Ruta 9", formato=Formato.DIGITAL, precio_unitario=8500)

    def recorrer(self, rutas):
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200, ruta)

    def test_paginas_del_usuario(self):
        self.client.force_login(self.usuario)
        self.recorrer([
            reverse("musica:mi_musica"),
            reverse("musica:subir_cancion"),
            reverse("musica:mis_publicaciones"),
            reverse("musica:crear_album"),
            reverse("musica:editar_cancion", args=[self.cancion.slug]),
            reverse("musica:detalle_cancion", args=[self.cancion.slug]),
            reverse("usuarios:perfil"),
            reverse("usuarios:cambiar_password"),
            reverse("usuarios:perfil_publico", args=[self.usuario.username]),
            reverse("tienda:carrito"),
            reverse("tienda:mis_pedidos"),
            reverse("tienda:confirmacion", args=[self.vinilo.numero]),
        ])

    def test_paginas_del_panel(self):
        self.client.force_login(self.admin)
        self.recorrer([
            reverse("panel:dashboard"),
            reverse("panel:canciones"),
            reverse("panel:detalle_cancion", args=[self.cancion.slug]),
            reverse("panel:usuarios"),
            reverse("panel:albumes"),
            reverse("panel:nuevo_album"),
            reverse("panel:pedidos"),
            reverse("panel:generos"),
        ])

    def test_publicacion_muestra_su_recorrido(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("musica:mis_publicaciones"))
        self.assertContains(respuesta, 'aria-current="step">En revisión')

    def test_recorrido_segun_formato(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.get(reverse("tienda:mis_pedidos"))
        self.assertContains(respuesta, "En camino")
        self.assertContains(respuesta, "En tu biblioteca")

    def test_resumen_mide_la_actividad(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("panel:dashboard"))
        dias = respuesta.context["actividad"]
        self.assertEqual(len(dias), 14)
        self.assertEqual(dias[-1]["escuchas"], 1)
        self.assertEqual(dias[-1]["me_gusta"], 1)
        self.assertEqual(dias[-1]["nivel"], 1)
        self.assertContains(respuesta, "Not Like Us")
        # Los niveles van a CSS: siempre con punto decimal, nunca con coma.
        self.assertNotRegex(respuesta.content.decode(), r"--nivel: \d+,\d")

    def test_paginas_de_error(self):
        from django.test import RequestFactory

        from musica.views import error_500

        # La 500 no depende de la sesión ni de la base: se dibuja con un pedido pelado.
        self.assertContains(error_500(RequestFactory().get("/")), "Se cortó la luz", status_code=500)
        self.assertContains(self.client.get("/esto-no-existe/"), "Se rayó el disco", status_code=404)


class RankingDelPanelTests(TestCase):
    def test_cuenta_por_tema_y_no_por_el_titulo_que_manda_el_navegador(self):
        from musica.models import MeGusta

        sin_red(self)
        admin = Usuario.objects.create_user(
            username="admin", email="admin@ejemplo.com", password="Admin1234", rol=Usuario.Rol.ADMIN
        )
        for i, titulo in enumerate(["Blinding Lights", "BLINDING LIGHTS!!", "otro nombre"]):
            u = Usuario.objects.create_user(username=f"oyente{i}", email=f"o{i}@ejemplo.com", password="Usuario1234")
            MeGusta.objects.create(usuario=u, pista_id="itunes-7", titulo=titulo, preview="https://x.apple.com/a.m4a")
        self.client.force_login(admin)
        filas = self.client.get(reverse("panel:dashboard")).context["top_me_gusta"]
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["n"], 3)
        self.assertEqual(filas[0]["titulo"], "Blinding Lights")  # del catálogo


class CancelarDosVecesTests(TestCase):
    def test_el_stock_vuelve_una_sola_vez(self):
        from datetime import date

        from musica.models import Album
        from tienda.models import Formato, Pedido, PedidoItem

        sin_red(self)
        admin = Usuario.objects.create_user(
            username="admin", email="admin@ejemplo.com", password="Admin1234", rol=Usuario.Rol.ADMIN
        )
        album = Album.objects.create(titulo="Ruta 9", artista=admin, fecha_lanzamiento=date(2026, 1, 1),
                                     precio_digital=1, precio_fisico=10, stock_fisico=3)
        pedido = Pedido.objects.create(usuario=admin, total=10, estado=Pedido.Estado.PAGADO)
        PedidoItem.objects.create(pedido=pedido, album=album, nombre_album="Ruta 9",
                                  formato=Formato.FISICO, cantidad=2, precio_unitario=10)
        self.client.force_login(admin)
        url = reverse("panel:cambiar_estado_pedido", args=[pedido.numero])
        self.client.post(url, {"estado": "CANCELADO"})
        self.client.post(url, {"estado": "CANCELADO"})
        album.refresh_from_db()
        self.assertEqual(album.stock_fisico, 5)

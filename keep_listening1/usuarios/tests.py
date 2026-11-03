"""Pruebas de los casos de uso 1 y 2: registro e inicio de sesión."""

from django.test import TestCase
from django.urls import reverse

from .models import Usuario


class RegistroTests(TestCase):
    def test_registro_crea_usuario_y_inicia_sesion(self):
        respuesta = self.client.post(
            reverse("usuarios:registro"),
            {
                "username": "nuevo",
                "email": "nuevo@ejemplo.com",
                "password1": "Melodia2026",
                "password2": "Melodia2026",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Usuario.objects.filter(username="nuevo").exists())
        self.assertTrue(respuesta.context["user"].is_authenticated)

    def test_password_sin_mayuscula_es_rechazada(self):
        respuesta = self.client.post(
            reverse("usuarios:registro"),
            {
                "username": "otro",
                "email": "otro@ejemplo.com",
                "password1": "password123",
                "password2": "password123",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="otro").exists())
        self.assertContains(respuesta, "mayúscula")

    def test_correo_duplicado_es_rechazado(self):
        Usuario.objects.create_user(username="uno", email="repetido@ejemplo.com", password="Melodia2026")
        respuesta = self.client.post(
            reverse("usuarios:registro"),
            {
                "username": "dos",
                "email": "repetido@ejemplo.com",
                "password1": "Melodia2026",
                "password2": "Melodia2026",
            },
        )
        self.assertContains(respuesta, "Ya existe una cuenta")


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="sophia", email="sophia@ejemplo.com", password="Usuario1234"
        )

    def test_login_con_usuario(self):
        respuesta = self.client.post(
            reverse("usuarios:login"), {"username": "sophia", "password": "Usuario1234"}, follow=True
        )
        self.assertTrue(respuesta.context["user"].is_authenticated)

    def test_login_con_correo(self):
        respuesta = self.client.post(
            reverse("usuarios:login"),
            {"username": "sophia@ejemplo.com", "password": "Usuario1234"},
            follow=True,
        )
        self.assertTrue(respuesta.context["user"].is_authenticated)

    def test_usuario_bloqueado_no_puede_entrar(self):
        self.usuario.bloqueado = True
        self.usuario.motivo_bloqueo = "Spam"
        self.usuario.save()
        respuesta = self.client.post(
            reverse("usuarios:login"), {"username": "sophia", "password": "Usuario1234"}
        )
        self.assertContains(respuesta, "bloqueada")

    def test_rol_admin_activa_permisos_de_staff(self):
        self.usuario.rol = Usuario.Rol.ADMIN
        self.usuario.save()
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_staff)
        self.assertTrue(self.usuario.es_admin)


class CerrarSesionTests(TestCase):
    """El cierre de sesión cambia estado: no puede dispararse con un GET."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="sophia", email="sophia@ejemplo.com", password="Usuario1234"
        )
        self.client.force_login(self.usuario)

    def test_logout_por_get_no_cierra_la_sesion(self):
        respuesta = self.client.get(reverse("usuarios:logout"))
        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(self.client.get(reverse("usuarios:perfil")).status_code == 200)

    def test_logout_por_post_cierra_la_sesion(self):
        respuesta = self.client.post(reverse("usuarios:logout"), follow=True)
        self.assertFalse(respuesta.context["user"].is_authenticated)


class LimiteDeIntentosTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        Usuario.objects.create_user(username="lara", email="lara@ejemplo.com", password="Clave1234")

    def test_frena_despues_de_cinco_intentos_fallidos(self):
        url = reverse("usuarios:login")
        for _ in range(5):
            self.client.post(url, {"username": "lara", "password": "mala"})
        respuesta = self.client.post(url, {"username": "lara", "password": "Clave1234"})
        self.assertEqual(respuesta.status_code, 429)
        self.assertContains(respuesta, "Demasiados intentos", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_un_login_bueno_limpia_los_intentos(self):
        url = reverse("usuarios:login")
        for _ in range(3):
            self.client.post(url, {"username": "lara", "password": "mala"})
        respuesta = self.client.post(url, {"username": "lara", "password": "Clave1234"})
        self.assertEqual(respuesta.status_code, 302)


class EncabezadosTests(TestCase):
    def test_la_pagina_lleva_csp_con_nonce(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        politica = respuesta["Content-Security-Policy"]
        self.assertIn("script-src 'self' 'nonce-", politica)
        self.assertIn("frame-ancestors 'none'", politica)
        nonce = politica.split("'nonce-")[1].split("'")[0]
        self.assertContains(respuesta, f'nonce="{nonce}"')
        self.assertIn("camera=()", respuesta["Permissions-Policy"])


class RegistroLimitadoTests(TestCase):
    def test_frena_la_creacion_de_cuentas_en_masa(self):
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)  # el límite no se arrastra a otros tests
        for i in range(11):
            respuesta = self.client.post(reverse("usuarios:registro"), {"username": f"u{i}"})
        self.assertEqual(respuesta.status_code, 429)
        self.assertContains(respuesta, "Demasiados registros", status_code=429)


class PlataformasTests(TestCase):
    """Entrar con Google, Apple, ... (allauth)."""

    GOOGLE = {"google": {"SCOPE": ["profile", "email"], "APPS": [{"client_id": "id-de-prueba", "secret": "secreto"}]}}

    def _con_google(self):
        from unittest.mock import patch

        from . import context_processors, sociales

        activas = sociales.disponibles(self.GOOGLE)
        for parche in (
            patch.object(context_processors, "PLATAFORMAS", activas),
            patch.object(context_processors, "HAY_ACTIVAS", True),
        ):
            parche.start()
            self.addCleanup(parche.stop)

    def test_sin_claves_no_hay_botones(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertNotContains(respuesta, "Entrar con Google")

    def test_con_claves_aparece_el_boton_y_lleva_a_google(self):
        from django.test import override_settings

        self._con_google()
        with override_settings(SOCIALACCOUNT_PROVIDERS=self.GOOGLE):
            respuesta = self.client.get(reverse("usuarios:login"))
            ida = self.client.post("/auth/google/login/?process=login")
        self.assertContains(respuesta, "Entrar con YouTube Music")  # en el aria-label del disco
        self.assertContains(respuesta, 'action="/auth/google/login/')
        self.assertEqual(ida.status_code, 302)
        self.assertTrue(ida.url.startswith("https://accounts.google.com/"))
        self.assertIn("client_id=id-de-prueba", ida.url)

    def test_las_paginas_de_allauth_llevan_a_las_del_sitio(self):
        self.assertRedirects(self.client.get("/auth/login/?next=/explorar/"),
                             reverse("usuarios:login") + "?next=/explorar/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/auth/signup/"), reverse("usuarios:registro"),
                             fetch_redirect_response=False)

    def test_las_claves_salen_del_entorno(self):
        from unittest.mock import patch

        from . import sociales

        with patch.dict("os.environ", {"KL_SPOTIFY_ID": "abc", "KL_SPOTIFY_SECRET": "xyz"}, clear=False):
            config = sociales.configuracion()
        self.assertEqual(config["spotify"]["APPS"][0]["client_id"], "abc")
        # Solo plataformas de música.
        self.assertEqual(set(config), {"spotify", "apple", "google", "soundcloud"})
        # Apple necesita las cuatro piezas; con una sola no se activa.
        with patch.dict("os.environ", {"KL_APPLE_ID": "com.ejemplo"}, clear=False):
            self.assertNotIn("APPS", sociales.configuracion()["apple"])

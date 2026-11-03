"""Pruebas de los casos de uso 3, 4 y 5: reproducir, guardar y publicar."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from usuarios.models import Usuario

from .models import Album, Cancion, Favorito, Genero, Reproduccion


def audio_falso(nombre="tema.wav"):
    return SimpleUploadedFile(nombre, b"RIFF0000WAVEfmt ", content_type="audio/wav")


class BaseMusica(TestCase):
    def setUp(self):
        self.artista = Usuario.objects.create_user(
            username="artista", email="artista@ejemplo.com", password="Usuario1234"
        )
        self.oyente = Usuario.objects.create_user(
            username="oyente", email="oyente@ejemplo.com", password="Usuario1234"
        )
        self.genero = Genero.objects.create(nombre="Rock")
        self.cancion = Cancion.objects.create(
            titulo="Tema aprobado",
            artista=self.artista,
            genero=self.genero,
            archivo_audio=audio_falso(),
            estado=Cancion.Estado.APROBADA,
        )


class PublicarTests(BaseMusica):
    def test_publicar_deja_la_cancion_pendiente(self):
        self.client.force_login(self.artista)
        respuesta = self.client.post(
            reverse("musica:subir_cancion"),
            {
                "titulo": "Canción nueva",
                "genero": self.genero.id,
                "tipo": Cancion.Tipo.SENCILLO,
                "numero_pista": 1,
                "archivo_audio": audio_falso("nueva.wav"),
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        nueva = Cancion.objects.get(titulo="Canción nueva")
        self.assertEqual(nueva.estado, Cancion.Estado.PENDIENTE)
        self.assertEqual(nueva.artista, self.artista)

    def test_tipo_album_sin_album_da_error(self):
        self.client.force_login(self.artista)
        respuesta = self.client.post(
            reverse("musica:subir_cancion"),
            {
                "titulo": "Sin álbum",
                "genero": self.genero.id,
                "tipo": Cancion.Tipo.ALBUM,
                "numero_pista": 1,
                "archivo_audio": audio_falso("sin-album.wav"),
            },
        )
        self.assertContains(respuesta, "Elegí el álbum")
        self.assertFalse(Cancion.objects.filter(titulo="Sin álbum").exists())

    def test_solo_el_autor_o_un_admin_pueden_editar(self):
        self.client.force_login(self.oyente)
        respuesta = self.client.get(reverse("musica:editar_cancion", args=[self.cancion.slug]), follow=True)
        self.assertContains(respuesta, "No podés editar")

    def test_las_pendientes_no_aparecen_en_explorar(self):
        Cancion.objects.create(
            titulo="Pendiente",
            artista=self.artista,
            genero=self.genero,
            archivo_audio=audio_falso("p.wav"),
            estado=Cancion.Estado.PENDIENTE,
        )
        respuesta = self.client.get(reverse("musica:explorar"))
        self.assertContains(respuesta, "Tema aprobado")
        self.assertNotContains(respuesta, "Pendiente</a>")


class FavoritosTests(BaseMusica):
    def test_guardar_y_quitar_favorito_por_ajax(self):
        self.client.force_login(self.oyente)
        url = reverse("musica:toggle_favorito", args=[self.cancion.id])

        respuesta = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(respuesta.json()["guardada"])
        self.assertTrue(Favorito.objects.filter(usuario=self.oyente, cancion=self.cancion).exists())

        respuesta = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(respuesta.json()["guardada"])
        self.assertFalse(Favorito.objects.filter(usuario=self.oyente, cancion=self.cancion).exists())

    def test_favorito_requiere_sesion(self):
        respuesta = self.client.post(reverse("musica:toggle_favorito", args=[self.cancion.id]))
        self.assertEqual(respuesta.status_code, 302)

    def test_mi_musica_lista_las_guardadas(self):
        Favorito.objects.create(usuario=self.oyente, cancion=self.cancion)
        self.client.force_login(self.oyente)
        respuesta = self.client.get(reverse("musica:mi_musica"))
        self.assertContains(respuesta, "Tema aprobado")


class ReproduccionTests(BaseMusica):
    def test_reproducir_suma_al_contador_y_al_historial(self):
        url = reverse("musica:registrar_reproduccion", args=[self.cancion.id])
        self.client.force_login(self.oyente)
        respuesta = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.cancion.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.cancion.reproducciones, 1)
        self.assertEqual(Reproduccion.objects.filter(usuario=self.oyente).count(), 1)

    def test_busqueda_ajax_devuelve_resultados(self):
        with patch("musica.views.buscar_mundo", return_value=[]):
            respuesta = self.client.get(reverse("musica:api_buscar"), {"q": "Tema"})
        datos = respuesta.json()
        self.assertEqual(len(datos["canciones"]), 1)
        self.assertEqual(datos["canciones"][0]["titulo"], "Tema aprobado")


class AlbumTests(BaseMusica):
    def test_crear_album_asigna_el_artista(self):
        self.client.force_login(self.artista)
        self.client.post(
            reverse("musica:crear_album"),
            {
                "titulo": "Mi álbum",
                "genero": self.genero.id,
                "tipo": Album.Tipo.ALBUM,
                "descripcion": "",
                "fecha_lanzamiento": "2026-01-01",
                "tipo_disco": Album.TipoDisco.CD,
                "disponible_digital": "on",
                "precio_digital": "5000",
                "precio_fisico": "0",
                "stock_fisico": "0",
                "publicado": "on",
            },
        )
        album = Album.objects.get(titulo="Mi álbum")
        self.assertEqual(album.artista, self.artista)
        self.assertTrue(album.slug)
        # Aunque mande "publicado", entra oculto: lo publica el equipo.
        self.assertFalse(album.publicado)


class SeguridadTests(BaseMusica):
    """Regresiones de los agujeros detectados en la auditoria."""

    def test_el_titulo_no_puede_cerrar_el_bloque_de_script(self):
        """La cola del reproductor se escapa: un título con HTML no ejecuta nada."""
        self.cancion.titulo = "Tema</script><script>alert(1)</script>"
        self.cancion.save()
        respuesta = self.client.get(reverse("musica:explorar"))
        cuerpo = respuesta.content.decode()
        self.assertNotIn("</script><script>alert(1)", cuerpo)
        self.assertIn("\u003C/script", cuerpo)

    def test_no_se_puede_cambiar_la_duracion_de_una_cancion_ajena(self):
        pendiente = Cancion.objects.create(
            titulo="Pendiente ajena",
            artista=self.artista,
            genero=self.genero,
            archivo_audio=audio_falso("ajena.wav"),
            estado=Cancion.Estado.PENDIENTE,
        )
        self.client.force_login(self.oyente)
        respuesta = self.client.post(
            reverse("musica:actualizar_duracion", args=[pendiente.id]), {"duracion": "999"}
        )
        pendiente.refresh_from_db()
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(pendiente.duracion_segundos, 0)

    def test_un_archivo_que_no_es_audio_se_rechaza(self):
        """La extensión no alcanza: se mira la firma del contenido."""
        falso = SimpleUploadedFile(
            "virus.mp3", b"<?php echo 1; ?>--relleno--", content_type="audio/mpeg"
        )
        self.client.force_login(self.artista)
        respuesta = self.client.post(
            reverse("musica:subir_cancion"),
            {
                "titulo": "No es audio",
                "genero": self.genero.id,
                "tipo": Cancion.Tipo.SENCILLO,
                "numero_pista": 1,
                "archivo_audio": falso,
            },
        )
        self.assertContains(respuesta, "no parece ser audio")
        self.assertFalse(Cancion.objects.filter(titulo="No es audio").exists())

    def test_el_contador_de_reproducciones_no_pierde_incrementos(self):
        """Dos oyentes a la vez deben sumar dos, no una."""
        url = reverse("musica:registrar_reproduccion", args=[self.cancion.id])
        self.client.post(url)
        self.client_class().post(url)
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.reproducciones, 2)


class CatalogoExternoTests(BaseMusica):
    def test_preview_rechaza_un_host_desconocido(self):
        self.client.force_login(self.oyente)
        respuesta = self.client.get(
            reverse("musica:api_preview"), {"u": "https://example.com/tema.mp3"}
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_letra_exige_artista_y_titulo(self):
        respuesta = self.client.get(reverse("musica:api_letra"))
        self.assertEqual(respuesta.status_code, 400)

    def test_el_inicio_muestra_artistas_del_mapa(self):
        mundo = {
            "temas": [{
                "id": "itunes-1",
                "titulo": "Tema mapa",
                "artista": "Artista Mapa",
                "portada": "/static/img/vacio.png",
                "audio": "/api/preview/?u=x",
                "url": "https://music.apple.com/tema",
                "duracion": 200,
                "genero": "Pop",
                "fuente": "Apple Music",
                "externo": True,
            }],
            "artistas": [{
                "nombre": "Artista Mapa",
                "portada": "/static/img/vacio.png",
                "genero": "Pop",
                "tema": "itunes-1",
            }],
        }
        # Sin selección curada (Apple no respondió) queda lo más escuchado.
        with patch("musica.views.mezcla", return_value=[]),                 patch("musica.views.portada_mundo", return_value=mundo):
            respuesta = self.client.get(reverse("musica:home"), HTTP_HOST="127.0.0.1")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Artista Mapa")
        self.assertNotContains(respuesta, "Circuito nocturno")

    def test_el_inicio_sigue_si_el_mapa_falla(self):
        with patch("musica.views.mezcla", side_effect=OSError("sin red")),                 patch("musica.views.portada_mundo", side_effect=OSError("sin red")):
            respuesta = self.client.get(reverse("musica:home"), HTTP_HOST="127.0.0.1")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La sala")

    def test_la_busqueda_local_sigue_si_el_mapa_falla(self):
        with patch("musica.views.buscar_mundo", side_effect=OSError("sin red")):
            respuesta = self.client.get(reverse("musica:api_buscar"), {"q": "Tema"})
        datos = respuesta.json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(datos["canciones"][0]["titulo"], "Tema aprobado")
        self.assertEqual(datos["catalogo"], [])


class ReproduccionRepetidaTests(BaseMusica):
    def test_la_misma_sesion_no_infla_el_contador(self):
        url = reverse("musica:registrar_reproduccion", args=[self.cancion.id])
        for _ in range(5):
            self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.reproducciones, 1)


class DuracionAjenaTests(BaseMusica):
    def test_no_se_corrige_la_duracion_de_un_tema_ajeno(self):
        Cancion.objects.filter(pk=self.cancion.pk).update(duracion_segundos=200)
        self.client.force_login(self.oyente)
        self.client.post(reverse("musica:actualizar_duracion", args=[self.cancion.id]), {"duracion": 5})
        self.cancion.refresh_from_db()
        self.assertEqual(self.cancion.duracion_segundos, 200)


class ArchivosHuerfanosTests(BaseMusica):
    def test_borrar_la_cancion_borra_el_audio(self):
        storage = self.cancion.archivo_audio.storage
        nombre = self.cancion.archivo_audio.name
        self.assertTrue(storage.exists(nombre))
        with self.captureOnCommitCallbacks(execute=True):
            self.cancion.delete()
        self.assertFalse(storage.exists(nombre))

    def test_reemplazar_el_audio_borra_el_anterior(self):
        storage = self.cancion.archivo_audio.storage
        viejo = self.cancion.archivo_audio.name
        self.cancion.archivo_audio = audio_falso("otro.wav")
        with self.captureOnCommitCallbacks(execute=True):
            self.cancion.save()
        self.assertFalse(storage.exists(viejo))
        self.assertTrue(storage.exists(self.cancion.archivo_audio.name))


class PreviewTests(TestCase):
    URL = "https://audio-ssl.itunes.apple.com/itunes-assets/x/y.m4a"

    def setUp(self):
        self.client.force_login(
            Usuario.objects.create_user(username="oye", email="oye@ejemplo.com", password="Usuario1234")
        )

    def test_sin_sesion_no_hay_audio(self):
        self.client.logout()
        respuesta = self.client.get(reverse("musica:api_preview"), {"u": self.URL})
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("login", respuesta.json())

    def test_rechaza_hosts_desconocidos(self):
        respuesta = self.client.get(reverse("musica:api_preview"), {"u": "https://evil.example/a.m4a"})
        self.assertEqual(respuesta.status_code, 400)

    def test_responde_rangos_para_poder_adelantar(self):
        with patch("musica.views.bajar_preview", return_value=(b"0123456789", "audio/mp4")):
            completa = self.client.get(reverse("musica:api_preview"), {"u": self.URL})
            parcial = self.client.get(reverse("musica:api_preview"), {"u": self.URL}, HTTP_RANGE="bytes=2-5")
            fuera = self.client.get(reverse("musica:api_preview"), {"u": self.URL}, HTTP_RANGE="bytes=50-")
        self.assertEqual(completa["Accept-Ranges"], "bytes")
        self.assertEqual(parcial.status_code, 206)
        self.assertEqual(parcial.content, b"2345")
        self.assertEqual(parcial["Content-Range"], "bytes 2-5/10")
        self.assertEqual(fuera.status_code, 416)

    def test_si_apple_falla_responde_502(self):
        with patch("musica.views.bajar_preview", side_effect=OSError("corte")):
            respuesta = self.client.get(reverse("musica:api_preview"), {"u": self.URL})
        self.assertEqual(respuesta.status_code, 502)


class SeleccionTests(TestCase):
    TEMA = {
        "trackId": 7, "trackName": "Not Like Us", "artistName": "Kendrick Lamar",
        "previewUrl": "https://audio-ssl.itunes.apple.com/itunes-assets/a/b.m4a",
        "artworkUrl100": "https://is1-ssl.mzstatic.com/x/100x100bb.jpg", "trackTimeMillis": 274000,
    }

    def test_elige_el_tema_pedido_y_no_uno_cualquiera(self):
        from .seleccion import _temas_de

        remix = {**self.TEMA, "trackId": 8, "trackName": "Not Like Us (Remix)"}
        otro = {**self.TEMA, "trackId": 9, "trackName": "HUMBLE."}
        with patch("musica.seleccion._buscar", return_value=[remix, self.TEMA, otro]):
            temas = _temas_de("Kendrick Lamar", ["Not Like Us", "Tema que no existe"], "Hip hop")
        self.assertEqual([t["id"] for t in temas], ["itunes-7"])
        self.assertTrue(temas[0]["audio"].startswith("/api/preview/"))

    def test_explorar_muestra_las_escenas(self):
        pista = {"id": "itunes-7", "titulo": "Not Like Us", "artista": "Kendrick Lamar",
                 "portada": "", "audio": "/api/preview/?u=x", "url": "", "duracion": 30,
                 "genero": "Hip hop", "fuente": "Apple Music", "externo": True}
        escenas = [{"slug": "hip-hop", "nombre": "Hip hop", "descripcion": "", "temas": [pista]}]
        with patch("musica.views.escenas", return_value=escenas):
            respuesta = self.client.get(reverse("musica:explorar"))
        self.assertContains(respuesta, "Not Like Us")
        self.assertContains(respuesta, 'data-reproducir-escena="kl-escena-hip-hop"')

    def test_la_radio_usa_la_seleccion_si_no_hay_temas_propios(self):
        pista = {"id": "itunes-7", "titulo": "Not Like Us", "audio": "/api/preview/?u=x"}
        with patch("musica.views.mezcla", return_value=[pista]):
            datos = self.client.get(reverse("musica:api_cola")).json()
        self.assertEqual(datos["pistas"], [pista])


class MeGustaTests(BaseMusica):
    PISTA = {
        "id": "itunes-7",
        "titulo": "Not Like Us",
        "artista": "Kendrick Lamar",
        "portada": "https://is1-ssl.mzstatic.com/x/300x300bb.jpg",
        "audio": "/api/preview/?u=https%3A%2F%2Faudio-ssl.itunes.apple.com%2Fa%2Fb.m4a",
        "url": "https://music.apple.com/us/album/x",
        "duracion": "274",
        "genero": "Hip hop",
    }

    def test_pide_sesion(self):
        respuesta = self.client.post(reverse("musica:api_me_gusta"), self.PISTA)
        self.assertEqual(respuesta.status_code, 302)

    def test_marca_y_desmarca(self):
        from .models import MeGusta

        self.client.force_login(self.oyente)
        url = reverse("musica:api_me_gusta")
        datos = self.client.post(url, self.PISTA, HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()
        self.assertTrue(datos["guardada"])
        guardado = MeGusta.objects.get(usuario=self.oyente)
        self.assertEqual(guardado.preview, "https://audio-ssl.itunes.apple.com/a/b.m4a")
        self.assertTrue(guardado.como_pista()["audio"].startswith("/api/preview/"))
        datos = self.client.post(url, self.PISTA).json()
        self.assertFalse(datos["guardada"])
        self.assertFalse(MeGusta.objects.exists())

    def test_rechaza_adelantos_y_portadas_de_otros_sitios(self):
        from .models import MeGusta

        self.client.force_login(self.oyente)
        url = reverse("musica:api_me_gusta")
        malo = {**self.PISTA, "audio": "/api/preview/?u=https%3A%2F%2Fevil.example%2Fa.m4a"}
        self.assertEqual(self.client.post(url, malo).status_code, 400)
        portada_rara = {**self.PISTA, "portada": "javascript:alert(1)"}
        self.client.post(url, portada_rara)
        self.assertEqual(MeGusta.objects.get().portada, "")

    def test_el_inicio_muestra_tus_me_gusta(self):
        self.client.force_login(self.oyente)
        self.client.post(reverse("musica:api_me_gusta"), self.PISTA)
        with patch("musica.views.mezcla", return_value=[]), patch("musica.views.portada_mundo", return_value={}):
            respuesta = self.client.get(reverse("musica:home"))
        self.assertContains(respuesta, "Tus me gusta")
        self.assertContains(respuesta, "Not Like Us")


def _pista_curada(i, genero):
    return {
        "id": f"itunes-{i}", "titulo": f"Tema {i}", "artista": f"Artista {i % 3}",
        "portada": "", "audio": f"/api/preview/?u=x{i}", "duracion": 180, "genero": genero,
    }


class InicioTests(BaseMusica):
    CURADA = [_pista_curada(i, "Hip hop" if i % 2 else "Pop") for i in range(12)]

    def test_el_disco_del_dia_es_el_mismo_todo_el_dia(self):
        from datetime import date

        from .views import _disco_del_dia

        hoy = date(2026, 9, 29)
        primero = _disco_del_dia(self.CURADA, hoy)
        self.assertEqual([lado["letra"] for lado in primero], ["A", "B"])
        self.assertTrue(all(t["genero"] == "Hip hop" for t in primero[0]["temas"]))
        self.assertEqual(primero, _disco_del_dia(self.CURADA, hoy))

    def test_el_ranking_cuenta_solo_temas_del_catalogo(self):
        from .models import MeGusta
        from .views import _ranking_de_la_sala

        for usuario in (self.oyente, self.artista):
            MeGusta.objects.create(usuario=usuario, pista_id="itunes-5", titulo="lo que sea",
                                   preview="https://x.apple.com/a.m4a")
        MeGusta.objects.create(usuario=self.oyente, pista_id="itunes-999", titulo="<b>inventado</b>",
                               preview="https://x.apple.com/a.m4a")
        ranking = _ranking_de_la_sala(self.CURADA, cantidad=3)
        self.assertEqual(ranking[0]["id"], "itunes-5")
        self.assertEqual(ranking[0]["titulo"], "Tema 5")
        self.assertEqual(ranking[0]["votos"], 2)
        self.assertNotIn("itunes-999", [t["id"] for t in ranking])

    def test_el_inicio_arma_todas_las_secciones(self):
        with patch("musica.views.mezcla", return_value=self.CURADA):
            respuesta = self.client.get(reverse("musica:home"))
        for texto in ("Dos caras", "Tres segundos", "Lo más guardado", "En la batea", "Hecho en la sala"):
            self.assertContains(respuesta, texto)
        self.assertContains(respuesta, 'id="kl-lado-a"')
        # El tema de la comunidad se puede reproducir desde la página.
        self.assertContains(respuesta, "Tema aprobado")


class AuditoriaMusicaTests(BaseMusica):
    URL = "https://audio-ssl.itunes.apple.com/itunes-assets/a.m4a"

    def test_los_guardados_que_vuelven_a_revision_no_suenan(self):
        Favorito.objects.create(usuario=self.oyente, cancion=self.cancion)
        Cancion.objects.filter(pk=self.cancion.pk).update(estado=Cancion.Estado.PENDIENTE)
        self.client.force_login(self.oyente)
        respuesta = self.client.get(reverse("musica:mi_musica"))
        self.assertEqual(respuesta.context["pistas"], [])

    def test_el_limite_de_adelantos_cuenta_escuchas_por_cuenta(self):
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)  # el límite no se arrastra a otros tests
        self.client.force_login(self.oyente)
        with patch("musica.views.bajar_preview", return_value=(b"0123456789", "audio/mp4")), \
                patch("musica.views.excedido", wraps=__import__("musica.limites", fromlist=["x"]).excedido) as limite:
            self.client.get(reverse("musica:api_preview"), {"u": self.URL})
            self.client.get(reverse("musica:api_preview"), {"u": self.URL}, HTTP_RANGE="bytes=4-")
        # El pedido parcial (adelantar) no cuenta como otra escucha.
        self.assertEqual(limite.call_count, 1)
        self.assertIn(str(self.oyente.pk), limite.call_args.args[1])

    def test_detras_de_un_proxy_se_lee_la_ip_real(self):
        from django.test import RequestFactory, override_settings

        from .limites import ip_de

        pedido = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.9", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(ip_de(pedido), "10.0.0.1")
        with override_settings(PROXIES_DE_CONFIANZA=1):
            # Lo que mandó el cliente ("6.6.6.6") no se usa: vale lo que agregó el proxy.
            self.assertEqual(ip_de(pedido), "203.0.113.9")


class AuditoriaBackendMusicaTests(BaseMusica):
    def test_numeros_imposibles_no_rompen(self):
        self.client.force_login(self.artista)
        url = reverse("musica:actualizar_duracion", args=[self.cancion.id])
        for valor in ("inf", "1e999", "nan", "abc"):
            self.assertEqual(self.client.post(url, {"duracion": valor}).status_code, 400)

    def test_doble_clic_en_guardar_no_rompe(self):
        self.client.force_login(self.oyente)
        url = reverse("musica:toggle_favorito", args=[self.cancion.id])
        Favorito.objects.create(usuario=self.oyente, cancion=self.cancion)
        datos = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest").json()
        self.assertFalse(datos["guardada"])
        self.assertFalse(Favorito.objects.exists())

    def test_una_subida_gigante_se_corta_antes_de_leerla(self):
        self.client.force_login(self.artista)
        respuesta = self.client.post(reverse("musica:subir_cancion"), CONTENT_LENGTH=str(500 * 1024 * 1024))
        self.assertEqual(respuesta.status_code, 413)

    def test_los_archivos_subidos_responden_por_pedazos(self):
        from django.test import RequestFactory

        from .views import responder_archivo

        ruta = __import__("pathlib").Path(self.cancion.archivo_audio.path)
        pedido = RequestFactory().get("/", HTTP_RANGE="bytes=4-7")
        respuesta = responder_archivo(pedido, ruta, "audio/wav")
        self.assertEqual(respuesta.status_code, 206)
        self.assertEqual(respuesta.content, b"0000")
        completa = responder_archivo(RequestFactory().get("/"), ruta, "audio/wav")
        self.assertEqual(b"".join(completa.streaming_content), b"RIFF0000WAVEfmt ")
        completa.close()

"""Runner de tests aislado y rápido.

- No ensucia `media/`: TestCase deshace la base al terminar cada test, pero no
  los archivos subidos (cada corrida dejaba audios huérfanos en la carpeta real).
- No toca la caché de disco del catálogo ni sale a internet: cualquier pedido a
  Apple, Spotify o LRCLIB falla como si no hubiera conexión; los tests que
  necesitan datos de afuera los simulan con patch.
- Usa un hasher de contraseñas rápido (el real es lento a propósito).
"""

import logging
import shutil
import tempfile
from unittest.mock import patch
from urllib.error import URLError

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class RunnerSinArchivos(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media = tempfile.mkdtemp(prefix="kl-tests-media-")
        # La caché de disco del catálogo tampoco se toca, y nadie sale a internet:
        # los tests que necesitan a Apple lo simulan con patch.
        caches = {**settings.CACHES, "catalogo": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        self._override = override_settings(
            MEDIA_ROOT=self._media,
            CACHES=caches,
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        self._override.enable()
        # Todo lo que sale a internet pasa por build_opener (catalogo.py); seleccion.py
        # importa _json por nombre, así que se corta también ahí.
        sin_red = URLError("sin red en los tests")
        self._sin_red = [
            patch("musica.catalogo.build_opener", side_effect=sin_red),
            patch("musica.seleccion._json", side_effect=sin_red),
        ]
        for parche in self._sin_red:
            parche.start()
        # Sin internet, los avisos de "Apple no respondió" son esperables: no ensucian la salida.
        logging.disable(logging.CRITICAL)

    def teardown_test_environment(self, **kwargs):
        logging.disable(logging.NOTSET)
        for parche in self._sin_red:
            parche.stop()
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)
        super().teardown_test_environment(**kwargs)

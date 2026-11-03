from django.apps import AppConfig


class MusicaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "musica"
    verbose_name = "Música"

    def ready(self):
        from django.contrib.auth import get_user_model

        from .models import Album, Cancion
        from .senales import conectar

        conectar(Album, Cancion, get_user_model())

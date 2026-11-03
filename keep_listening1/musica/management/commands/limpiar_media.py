"""Borra de MEDIA_ROOT los archivos que ningún registro usa.

    python manage.py limpiar_media --dry-run   # solo lista
    python manage.py limpiar_media             # borra
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import FileField

IGNORADOS = {".gitkeep"}


class Command(BaseCommand):
    help = "Borra los archivos de media/ que no están referenciados en la base."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Lista sin borrar nada.")

    def handle(self, *args, **opciones):
        raiz = Path(settings.MEDIA_ROOT)
        usados = set()
        for modelo in apps.get_models():
            campos = [c.name for c in modelo._meta.get_fields() if isinstance(c, FileField)]
            for campo in campos:
                for nombre in modelo._default_manager.exclude(**{campo: ""}).values_list(campo, flat=True):
                    if nombre:
                        usados.add(Path(nombre).as_posix())

        huerfanos = [
            ruta
            for ruta in raiz.rglob("*")
            if ruta.is_file()
            and ruta.name not in IGNORADOS
            and ruta.relative_to(raiz).as_posix() not in usados
        ]
        peso = sum(ruta.stat().st_size for ruta in huerfanos)
        for ruta in huerfanos:
            if opciones["dry_run"]:
                self.stdout.write(f"  {ruta.relative_to(raiz).as_posix()}")
            else:
                ruta.unlink()

        verbo = "Se borrarían" if opciones["dry_run"] else "Se borraron"
        self.stdout.write(self.style.SUCCESS(
            f"{verbo} {len(huerfanos)} archivos ({peso / 1024 / 1024:.1f} MB). "
            f"En uso: {len(usados)}."
        ))

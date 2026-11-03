"""Calcula dónde empieza cada adelanto dentro del tema completo.

Los adelantos de Apple son 30 segundos de algún punto del tema. Este comando
escucha cada adelanto de la selección con Whisper (reconocimiento de voz
local), busca esas frases en la letra sincronizada de LRCLIB y guarda el
desfase en musica/desfases.json. Con eso la letra se resalta justo cuando
se canta.

Whisper NO es dependencia del proyecto: se instala aparte solo para correr
este comando cuando cambia la selección.

    pip install faster-whisper
    python manage.py calcular_desfases            # solo los que faltan
    python manage.py calcular_desfases --todos    # recalcula todo
"""

import json
import re
import statistics
import tempfile
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote

from django.core.management.base import BaseCommand, CommandError

from musica.catalogo import bajar_preview, letra_de
from musica.seleccion import mezcla

ARCHIVO = Path(__file__).resolve().parents[2] / "desfases.json"


def normal(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9 ]+", " ", texto).split()


def parsear_lrc(lrc):
    versos = []
    for fila in (lrc or "").splitlines():
        marcas = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", fila)
        texto = re.sub(r"\[[^\]]+\]", "", fila).strip()
        if not texto or not normal(texto):
            continue
        for minutos, segundos in marcas:
            versos.append((int(minutos) * 60 + float(segundos), texto))
    return sorted(versos)


def parecido(a, b):
    return SequenceMatcher(None, normal(a), normal(b)).ratio()


def desfase_de(segmentos, versos):
    """Cada frase reconocida vota por un desfase (inicio en la letra - inicio en
    el adelanto). Gana el valor en el que coinciden más frases.

    Whisper suele juntar dos versos en una sola frase, así que también se
    compara contra pares de versos seguidos. Y un estribillo aparece varias
    veces en la letra: la frase vota por todas sus apariciones y decide el
    acuerdo con las demás frases, no la primera aparición."""
    opciones = list(versos) + [
        (versos[i][0], f"{versos[i][1]} {versos[i + 1][1]}") for i in range(len(versos) - 1)
    ]
    votos = []  # (desfase, similitud, número de frase)
    for numero, (inicio, texto) in enumerate(segmentos):
        if len(normal(texto)) < 3:
            continue
        for tiempo, verso in opciones:
            similitud = parecido(texto, verso)
            # Un desfase negativo es imposible: el adelanto no empieza antes del tema.
            if similitud >= 0.55 and tiempo - inicio >= 0:
                votos.append((tiempo - inicio, similitud, numero))
    if len(votos) < 2:
        return None
    # Agrupa votos a menos de 1,2 s entre sí (cada frase cuenta una sola vez,
    # con su mejor voto).
    grupos = []
    for centro, _, _ in votos:
        grupo = {}
        for d, s, numero in votos:
            if abs(d - centro) <= 1.2 and s > grupo.get(numero, (0, 0))[1]:
                grupo[numero] = (d, s)
        grupos.append((sum(s for _, s in grupo.values()), centro, grupo))
    # Gana el grupo más pesado. Si el adelanto es solo estribillo, encaja casi
    # igual en cada aparición: ante un empate (90 %) gana la primera.
    techo = max(peso for peso, _, _ in grupos)
    _, _, mejor_grupo = min((g for g in grupos if g[0] >= techo * 0.9), key=lambda g: g[1])
    # Con menos de 3 frases de acuerdo puede ser casualidad.
    if len(mejor_grupo) < 3:
        return None
    desfase = statistics.median(d for d, _ in mejor_grupo.values())
    frases = {numero for _, _, numero in votos}
    return {
        "desfase": round(desfase, 2),
        "frases": len(mejor_grupo),
        "confianza": round(len(mejor_grupo) / len(frases), 2),
    }


class Command(BaseCommand):
    help = "Calcula con Whisper el desfase de cada adelanto de la selección (musica/desfases.json)."

    def add_arguments(self, parser):
        parser.add_argument("--todos", action="store_true", help="Recalcula aunque ya exista.")
        parser.add_argument("--modelo", default="small", help="Modelo de Whisper (tiny, base, small...).")

    def handle(self, *args, **opciones):
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise CommandError("Falta faster-whisper: pip install faster-whisper") from error

        existentes = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}
        modelo = WhisperModel(opciones["modelo"], device="cpu", compute_type="int8")
        temas = mezcla(0)
        if not temas:
            raise CommandError("No se pudo armar la selección (¿Apple responde?).")

        for tema in temas:
            if tema["id"] in existentes and not opciones["todos"]:
                continue
            etiqueta = f"{tema['artista']} - {tema['titulo']}"
            letra = letra_de(tema["artista"], tema["titulo"], tema["duracion"])
            versos = parsear_lrc(letra.get("sincronizada"))
            if not versos:
                self.stdout.write(f"  sin letra sincronizada: {etiqueta}")
                continue
            url = tema["audio"].split("?u=", 1)[1]
            datos, _ = bajar_preview(unquote(url))
            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as archivo:
                archivo.write(datos)
                ruta = archivo.name
            try:
                segmentos, _ = modelo.transcribe(ruta, language="en", vad_filter=False, beam_size=5)
                segmentos = [(s.start, s.text) for s in segmentos]
            finally:
                Path(ruta).unlink(missing_ok=True)
            resultado = desfase_de(segmentos, versos)
            if resultado:
                existentes[tema["id"]] = {**resultado, "tema": etiqueta}
                self.stdout.write(self.style.SUCCESS(
                    f"  {etiqueta}: {resultado['desfase']} s ({resultado['frases']} frases)"
                ))
            else:
                self.stdout.write(self.style.WARNING(f"  no se pudo ubicar: {etiqueta}"))
            ARCHIVO.write_text(json.dumps(existentes, indent=2, ensure_ascii=False), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Listo: {len(existentes)} desfases en {ARCHIVO.name}"))

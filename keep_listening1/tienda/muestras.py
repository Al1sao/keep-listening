"""Muestras de los discos comprados.

Los discos de la tienda son de artistas de prueba y no traen audio. Para que lo
comprado se pueda escuchar, cada tema tiene una muestra de unos 20 segundos que
se compone a partir de su nombre: la misma canción suena siempre igual. El
género del disco elige el tempo, la escala y el timbre (rock, pop, jazz,
electrónica...). Se guarda en la caché de disco la primera vez que se pide.
"""

import hashlib
import io
import math
import random
import struct
import wave
from array import array
from pathlib import Path

from django.conf import settings

FRECUENCIA = 22050
DURACION = 20.0  # segundos
VERSION = 1  # subirla cambia todas las muestras (y las vuelve a generar)

# intervalos de cada escala, en semitonos desde la tónica
ESCALAS = {
    "mayor": (0, 2, 4, 5, 7, 9, 11),
    "menor": (0, 2, 3, 5, 7, 8, 10),
    "dorica": (0, 2, 3, 5, 7, 9, 10),
}

# tempo (mín, máx), escala, timbre de la melodía, batería
ESTILOS = {
    "rock": ((108, 128), "menor", "cuadrada", "rock"),
    "pop": ((100, 118), "mayor", "triangular", "pop"),
    "indie": ((96, 116), "mayor", "triangular", "pop"),
    "electronica": ((118, 128), "menor", "sierra", "electro"),
    "jazz": ((84, 100), "dorica", "seno", "jazz"),
    "hip hop": ((84, 96), "menor", "seno", "hiphop"),
    "folk": ((88, 104), "mayor", "triangular", "suave"),
}
ESTILO_POR_DEFECTO = ((96, 112), "mayor", "triangular", "pop")

# progresiones en grados de la escala (0 = I)
PROGRESIONES = ((0, 4, 5, 3), (0, 5, 3, 4), (5, 3, 0, 4), (0, 3, 4, 4), (0, 5, 1, 4))


def _normal(texto):
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return texto.lower().strip()


def _onda(tipo, fase):
    """Una oscilación por vuelta (fase en vueltas)."""
    x = fase % 1.0
    if tipo == "cuadrada":
        return 0.6 if x < 0.5 else -0.6
    if tipo == "sierra":
        return 2.0 * x - 1.0
    if tipo == "triangular":
        return 4.0 * x - 1.0 if x < 0.5 else 3.0 - 4.0 * x
    return math.sin(2 * math.pi * x)


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


class _Mezcla:
    def __init__(self, segundos):
        self.muestras = array("f", bytes(4 * int(segundos * FRECUENCIA)))

    def nota(self, inicio, duracion, hz, volumen, tipo="seno", ataque=0.008, caida=6.0):
        a = int(inicio * FRECUENCIA)
        n = min(int(duracion * FRECUENCIA), len(self.muestras) - a)
        paso = hz / FRECUENCIA
        ataque_n = max(1, int(ataque * FRECUENCIA))
        datos = self.muestras
        for i in range(max(n, 0)):
            t = i / FRECUENCIA
            env = min(1.0, i / ataque_n) * math.exp(-caida * t)
            # cola corta al final de la nota para que no haga clic
            if i > n - 200:
                env *= (n - i) / 200
            datos[a + i] += volumen * env * _onda(tipo, i * paso)

    def bombo(self, inicio, volumen=0.9):
        a = int(inicio * FRECUENCIA)
        n = min(int(0.28 * FRECUENCIA), len(self.muestras) - a)
        fase = 0.0
        for i in range(max(n, 0)):
            t = i / FRECUENCIA
            fase += (48 + 90 * math.exp(-28 * t)) / FRECUENCIA
            self.muestras[a + i] += volumen * math.exp(-11 * t) * math.sin(2 * math.pi * fase)

    def ruido(self, inicio, duracion, volumen, caida, azar):
        a = int(inicio * FRECUENCIA)
        n = min(int(duracion * FRECUENCIA), len(self.muestras) - a)
        previo = 0.0
        for i in range(max(n, 0)):
            blanco = azar.uniform(-1, 1)
            agudo = blanco - previo  # filtro simple: deja pasar los agudos
            previo = blanco
            self.muestras[a + i] += volumen * math.exp(-caida * i / FRECUENCIA) * agudo

    def a_wav(self):
        datos = self.muestras
        pico = max(1e-6, max(abs(v) for v in datos))
        ganancia = 0.85 / pico
        total = len(datos)
        fundido = int(0.6 * FRECUENCIA)
        salida = io.BytesIO()
        with wave.open(salida, "wb") as archivo:
            archivo.setnchannels(1)
            archivo.setsampwidth(2)
            archivo.setframerate(FRECUENCIA)
            cuadros = bytearray()
            for i, v in enumerate(datos):
                v = math.tanh(v * ganancia * 1.2)  # saturación suave, sin recortes
                if i < fundido:
                    v *= i / fundido
                elif i > total - fundido:
                    v *= (total - i) / fundido
                cuadros += struct.pack("<h", int(v * 30000))
            archivo.writeframes(bytes(cuadros))
        return salida.getvalue()


def componer(semilla, genero=""):
    """WAV (bytes) de una muestra: misma semilla y género, mismo resultado."""
    azar = random.Random(semilla)
    (bpm_min, bpm_max), nombre_escala, timbre, bateria = ESTILOS.get(_normal(genero), ESTILO_POR_DEFECTO)
    escala = ESCALAS[nombre_escala]
    bpm = azar.randint(bpm_min, bpm_max)
    tiempo = 60.0 / bpm
    compas = 4 * tiempo
    tonica = 45 + azar.randint(0, 7)  # La2 a Mi3
    progresion = azar.choice(PROGRESIONES)
    swing = 0.33 if bateria == "jazz" else 0.0

    def grado(g, octava=0):
        g = int(g)
        return tonica + escala[g % 7] + 12 * (g // 7 + octava)

    mezcla = _Mezcla(DURACION)
    compases = int(DURACION / compas) + 1

    for c in range(compases):
        inicio = c * compas
        raiz = progresion[c % len(progresion)]
        # Acorde de fondo (tríada) que dura el compás
        for intervalo in (0, 2, 4):
            mezcla.nota(inicio, compas, _hz(grado(raiz + intervalo, 1)), 0.07, "seno", ataque=0.08, caida=0.35)
        # Bajo en corcheas (negras en el jazz y el hip hop)
        paso_bajo = tiempo if bateria in ("jazz", "hiphop", "suave") else tiempo / 2
        golpes = int(compas / paso_bajo)
        for b in range(golpes):
            nota = grado(raiz, -1) + (7 if bateria == "jazz" and b % 2 else 0)
            mezcla.nota(inicio + b * paso_bajo, paso_bajo * 0.9, _hz(nota), 0.22, "triangular", caida=3.5)
        # Batería
        for b in range(4):
            t = inicio + b * tiempo
            if bateria == "electro" or (bateria in ("rock", "pop") and b in (0, 2)) or (bateria == "hiphop" and b in (0, 2)):
                mezcla.bombo(t)
            if bateria == "hiphop" and b == 2:
                mezcla.bombo(t + tiempo / 2, 0.7)
            if bateria in ("rock", "pop", "electro", "hiphop") and b in (1, 3):
                mezcla.ruido(t, 0.18, 0.35, 18, azar)
            platillo = 0.05 if bateria == "jazz" else 0.09
            if bateria != "suave":
                mezcla.ruido(t, 0.05, platillo, 60, azar)
                mezcla.ruido(t + tiempo * (0.5 + swing / 2), 0.04, platillo * 0.7, 70, azar)

    # Melodía: un motivo de dos compases que se repite y varía, sobre la escala.
    motivo = []
    posicion = azar.choice((2, 4))
    for _ in range(16):
        if azar.random() < 0.22:
            motivo.append(None)  # silencio
            continue
        posicion = max(0, min(9, posicion + azar.choice((-2, -1, -1, 0, 1, 1, 2))))
        motivo.append(posicion)
    corchea = tiempo / 2
    for c in range(1, compases):  # entra después del primer compás
        raiz = progresion[c % len(progresion)]
        for k in range(8):
            g = motivo[(c % 2) * 8 + k]
            if g is None:
                continue
            desfase = corchea * swing if k % 2 else 0
            variacion = 1 if (c // 2) % 2 and k == 7 else 0
            mezcla.nota(
                c * compas + k * corchea + desfase, corchea * 1.6,
                _hz(grado(g + variacion, 2)), 0.16, timbre, caida=4.0,
            )

    return mezcla.a_wav()


def ruta_muestra(album, numero, titulo):
    """Archivo de la muestra en la caché de disco (se crea si no existe)."""
    clave = hashlib.sha256(f"{VERSION}|{album.pk}|{album.slug}|{numero}|{titulo}".encode()).hexdigest()[:24]
    carpeta = Path(settings.BASE_DIR) / ".cache" / "muestras"
    ruta = carpeta / f"{clave}.wav"
    if not ruta.exists():
        carpeta.mkdir(parents=True, exist_ok=True)
        genero = album.genero.nombre if album.genero_id else ""
        datos = componer(f"{album.slug}|{numero}|{titulo}", genero)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_bytes(datos)
        temporal.replace(ruta)  # nadie lee un archivo a medio escribir
    return ruta

"""Selección curada de hip hop y pop: temas famosos con su adelanto oficial.

No se guarda audio en el proyecto: cada tema se busca en la API de Apple y
suena el adelanto de 30 segundos que Apple publica. Los resultados se guardan
en la caché de disco una semana (Apple limita las consultas por minuto), así
un reinicio del servidor no vuelve a pedir todo.
"""

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from json import JSONDecodeError
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from django.core.cache import cache, caches

from .catalogo import _json, _pista, _portada_itunes

ESCENAS = {
    "hip-hop": {
        "nombre": "Hip hop",
        "descripcion": "Los temas que marcaron la década, de Compton a Toronto.",
        "artistas": [
            ("Kendrick Lamar", ["Not Like Us", "HUMBLE."]),
            ("Drake", ["God's Plan", "Hotline Bling"]),
            ("Travis Scott", ["SICKO MODE", "FE!N"]),
            ("Eminem", ["Lose Yourself", "Without Me"]),
            ("Kanye West", ["Stronger", "Heartless"]),
            ("J. Cole", ["No Role Modelz", "MIDDLE CHILD"]),
            ("Post Malone", ["Circles", "rockstar"]),
            ("Doja Cat", ["Say So", "Paint The Town Red"]),
            ("50 Cent", ["In Da Club", "Candy Shop"]),
            ("Nicki Minaj", ["Super Bass", "Starships"]),
        ],
    },
    "pop": {
        "nombre": "Pop",
        "descripcion": "Estribillos que se quedan: los hits más escuchados del pop.",
        "artistas": [
            ("The Weeknd", ["Blinding Lights", "Save Your Tears"]),
            ("Taylor Swift", ["Cruel Summer", "Anti-Hero"]),
            ("Dua Lipa", ["Levitating", "Houdini"]),
            ("Billie Eilish", ["BIRDS OF A FEATHER", "bad guy"]),
            ("Ariana Grande", ["7 rings", "we can't be friends (wait for your love)"]),
            ("Harry Styles", ["As It Was", "Watermelon Sugar"]),
            ("Sabrina Carpenter", ["Espresso", "Please Please Please"]),
            ("Olivia Rodrigo", ["drivers license", "good 4 u"]),
            ("Bruno Mars", ["Die With A Smile", "24K Magic"]),
            ("Ed Sheeran", ["Shape of You", "Perfect"]),
        ],
    },
}

SEMANA = 60 * 60 * 24 * 7
DESFASES = Path(__file__).resolve().parent / "desfases.json"


def _clave_tema(artista, titulo):
    return f"{_normal(artista)}|{_normal(titulo)}"


@lru_cache(maxsize=1)
def _desfases(modificado):
    """La tabla por id y, de respaldo, por "artista - título": Apple a veces
    devuelve el mismo tema con otro id (el del álbum o el del simple)."""
    try:
        por_id = json.loads(DESFASES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    por_nombre = {}
    for dato in por_id.values():
        artista, _, titulo = str(dato.get("tema", "")).partition(" - ")
        if titulo:
            por_nombre.setdefault(_clave_tema(artista, titulo), dato)
    return por_id, por_nombre


def con_desfase(pistas):
    """Suma a cada adelanto dónde empieza dentro del tema, si ya se calculó con
    `manage.py calcular_desfases`. El front lo usa para resaltar la letra."""
    try:
        modificado = DESFASES.stat().st_mtime
    except OSError:
        return pistas
    por_id, por_nombre = _desfases(modificado)
    for pista in pistas:
        dato = por_id.get(str(pista.get("id"))) or por_nombre.get(
            _clave_tema(pista.get("artista"), pista.get("titulo"))
        )
        if dato:
            pista["desfase"] = dato["desfase"]
    return pistas


def _almacen():
    return caches["catalogo"]


def _normal(texto):
    """"we can't be friends (wait…)" y "We Can't Be Friends" se comparan igual."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    texto = re.sub(r"[\(\[].*?[\)\]]", "", texto.casefold())
    return re.sub(r"[^a-z0-9]+", "", texto)


def _como_pista(tema, genero):
    return _pista(
        ident=f"itunes-{tema.get('trackId')}",
        titulo=tema.get("trackName") or "Sin título",
        artista=tema.get("artistName") or "",
        portada=_portada_itunes(tema.get("artworkUrl100") or ""),
        preview=tema.get("previewUrl") or "",
        ficha=tema.get("trackViewUrl") or "",
        duracion=int((tema.get("trackTimeMillis") or 0) / 1000),
        genero=genero,
        fuente="Apple Music",
    )


def _buscar(params):
    datos = _json("https://itunes.apple.com/search?" + urlencode(params), timeout=10)
    return [t for t in datos.get("results") or [] if t.get("previewUrl") and t.get("trackId")]


def _temas_de(artista, titulos, genero):
    """Los temas pedidos de un artista. Una consulta por artista; solo si falta
    alguno se busca ese tema puntual."""
    clave = f"kl-seleccion-{_normal(artista)}-{'-'.join(_normal(t) for t in titulos)}"
    guardado = _almacen().get(clave)
    if guardado is not None:
        return guardado

    nombre = _normal(artista)

    def elegir(temas, titulo):
        buscado = _normal(titulo)
        propios = [
            t for t in temas
            if nombre in _normal(t.get("artistName")) and _normal(t.get("trackName")) == buscado
        ]

        def preferencia(tema):
            # Primero el título tal cual, después el artista solo (no el dúo) y
            # por último lo que no sea remix, en vivo o versión alternativa.
            crudo = tema.get("trackName") or ""
            return (
                crudo.casefold() != titulo.casefold(),
                _normal(tema.get("artistName")) != nombre,
                re.search(r"remix|live|version|mix|edit|sped|slowed", crudo, re.I) is not None,
            )

        return min(propios, key=preferencia) if propios else None

    del_artista = _buscar({"term": artista, "entity": "song", "attribute": "artistTerm",
                           "limit": 200, "country": "US"})
    elegidos = []
    for titulo in titulos:
        tema = elegir(del_artista, titulo)
        if tema is None:
            tema = elegir(
                _buscar({"term": f"{artista} {titulo}", "entity": "song", "limit": 15, "country": "US"}),
                titulo,
            )
        # Si no aparece el tema pedido no se reemplaza por otro cualquiera.
        if tema is not None:
            elegidos.append(_como_pista(tema, genero))

    _almacen().set(clave, elegidos, SEMANA if len(elegidos) == len(titulos) else 60 * 30)
    return elegidos


def escena(slug):
    """Temas de una escena, guardados unos minutos en la caché de memoria: el
    inicio, Explorar, la radio y el panel la piden en cada visita y armarla lee
    diez archivos de caché con hilos."""
    datos = ESCENAS.get(slug)
    if not datos:
        return []
    clave = f"kl-escena-{slug}"
    guardada = cache.get(clave)
    if guardada is not None:
        return [dict(t) for t in guardada]
    temas = _armar_escena(datos)
    # Si Apple falló (lista vacía o corta), se reintenta pronto.
    cache.set(clave, temas, 10 * 60 if len(temas) >= len(datos["artistas"]) else 60)
    return [dict(t) for t in temas]


def _armar_escena(datos):
    """Temas de una escena. Si Apple falla con un artista, se sigue con el resto."""

    def uno(par):
        artista, titulos = par
        try:
            return _temas_de(artista, titulos, datos["nombre"])
        except (HTTPError, URLError, TimeoutError, ValueError, JSONDecodeError, OSError):
            return []

    # Pocos hilos a la vez: Apple corta si se le pide demasiado junto.
    with ThreadPoolExecutor(max_workers=4) as grupo:
        por_artista = list(grupo.map(uno, datos["artistas"]))

    # Se intercalan: primero el tema más conocido de cada artista, después el segundo.
    temas = []
    for ronda in range(max((len(t) for t in por_artista), default=0)):
        temas.extend(t[ronda] for t in por_artista if len(t) > ronda)
    # El género sale de la escena y no de la caché: así un dato viejo guardado
    # con otro género no desordena la banda ni el disco del día.
    return con_desfase([{**t, "genero": datos["nombre"]} for t in temas if t["audio"]])


def escenas():
    return [
        {"slug": slug, "nombre": datos["nombre"], "descripcion": datos["descripcion"], "temas": escena(slug)}
        for slug, datos in ESCENAS.items()
    ]


def mezcla(cantidad=12):
    """Hip hop y pop alternados, para la sala del inicio y la radio."""
    listas = [escena(slug) for slug in ESCENAS]
    temas = []
    for ronda in range(max((len(l) for l in listas), default=0)):
        temas.extend(l[ronda] for l in listas if len(l) > ronda)
    return temas[:cantidad] if cantidad else temas

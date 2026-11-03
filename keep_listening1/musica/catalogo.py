"""Catálogo de afuera: adelantos y letras, sin guardar la música en el proyecto.

Apple Music se consulta directo (no pide clave) y devuelve un adelanto de
unos treinta segundos. Spotify entra solo si existen SPOTIFY_CLIENT_ID y
SPOTIFY_CLIENT_SECRET en el entorno: su API de búsqueda no entrega el tema
completo, solo la ficha y, a veces, un adelanto.

La letra sale de LRCLIB en el momento de pedirla. No se copia al repositorio.
"""

import base64
import hashlib
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from django.core.cache import cache, caches
from django.urls import reverse

AGENTE = "KeepListening/1.0 (proyecto personal)"
HOSTS_AUDIO = {
    "audio-ssl.itunes.apple.com",
    "audio.itunes.apple.com",
    "p.scdn.co",
}
_spotify = {"token": "", "vence": 0.0}


def portada_mundo():
    """Lo más escuchado ahora, para el inicio.

    Si Apple no responde se usa la última lista buena (se guarda un día aparte);
    recién si nunca hubo una, vuelve vacío.
    """
    guardado = cache.get("kl-portada-mundo-3")
    if guardado is not None:
        return guardado
    vacio = {"temas": [], "artistas": []}
    try:
        feed = _json(
            "https://rss.marketingtools.apple.com/api/v2/us/music/most-played/18/songs.json",
            timeout=12,
        )
        entradas = (feed.get("feed") or {}).get("results") or []
        ids = [str(item.get("id")) for item in entradas if item.get("id")]
        if not ids:
            cache.set("kl-portada-mundo-3", vacio, 120)
            return vacio
        lookup = _json(
            "https://itunes.apple.com/lookup?" + urlencode({"id": ",".join(ids), "country": "US"}),
            timeout=12,
        )
        por_id = {
            str(tema.get("trackId")): tema
            for tema in (lookup.get("results") or [])
            if tema.get("trackId")
        }
        temas = []
        generos = {}
        for entrada in entradas:
            ident = str(entrada.get("id") or "")
            ficha = por_id.get(ident) or {}
            genero = ""
            for genero_item in entrada.get("genres") or []:
                nombre = genero_item.get("name") or ""
                if nombre and nombre != "Music":
                    genero = nombre
                    break
            pista = _pista(
                ident=f"itunes-{ident}",
                titulo=ficha.get("trackName") or entrada.get("name") or "Sin título",
                artista=ficha.get("artistName") or entrada.get("artistName") or "",
                portada=_portada_itunes(ficha.get("artworkUrl100") or entrada.get("artworkUrl100") or ""),
                preview=ficha.get("previewUrl") or "",
                ficha=ficha.get("trackViewUrl") or entrada.get("url") or "",
                duracion=int((ficha.get("trackTimeMillis") or 0) / 1000),
                genero=genero,
                fuente="Apple Music",
            )
            if not pista["audio"]:
                continue
            temas.append(pista)
            generos[pista["id"]] = genero
            if len(temas) >= 12:
                break
        artistas = []
        vistos = set()
        for pista in temas:
            clave = pista["artista"].casefold()
            if clave in vistos:
                continue
            vistos.add(clave)
            artistas.append({
                "nombre": pista["artista"],
                "portada": pista["portada"],
                "genero": generos.get(pista["id"], ""),
                "tema": pista["id"],
            })
        resultado = {"temas": temas, "artistas": artistas}
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        resultado = vacio
    if resultado["temas"]:
        cache.set("kl-portada-mundo-3", resultado, 1800)
        cache.set("kl-portada-mundo-respaldo", resultado, 60 * 60 * 24)
        return resultado
    respaldo = cache.get("kl-portada-mundo-respaldo")
    if respaldo:
        cache.set("kl-portada-mundo-3", respaldo, 120)
        return respaldo
    cache.set("kl-portada-mundo-3", vacio, 30)
    return vacio


def _clave(prefijo, *partes):
    texto = "|".join(str(p).strip().casefold() for p in partes)
    return f"kl-{prefijo}-" + hashlib.sha1(texto.encode("utf-8")).hexdigest()


def buscar_mundo(consulta):
    """Temas de afuera para una búsqueda. Si una fuente falla, sigue la otra."""
    texto = " ".join((consulta or "").split())
    if len(texto) < 2:
        return []
    clave = _clave("buscar", texto)
    guardado = cache.get(clave)
    if guardado is not None:
        return guardado
    temas = []
    fallo = False
    for fuente in (buscar_itunes, buscar_spotify):
        try:
            temas.extend(fuente(texto))
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
            fallo = True
            continue
    vistos = set()
    unicos = []
    for tema in temas:
        par = (tema["titulo"].casefold(), tema["artista"].casefold())
        if par in vistos:
            continue
        vistos.add(par)
        unicos.append(tema)
    unicos = unicos[:8]
    from .seleccion import con_desfase

    con_desfase(unicos)
    # La búsqueda en vivo repite consultas con cada tecla: diez minutos alcanzan.
    cache.set(_clave("buscar", texto), unicos, 60 if fallo and not unicos else 600)
    return unicos


def buscar_itunes(consulta):
    url = "https://itunes.apple.com/search?" + urlencode(
        {"term": consulta, "entity": "song", "media": "music", "limit": 8, "country": "US"}
    )
    datos = _json(url)
    temas = []
    for tema in datos.get("results") or []:
        preview = tema.get("previewUrl") or ""
        temas.append(
            _pista(
                ident=f"itunes-{tema.get('trackId')}",
                titulo=tema.get("trackName") or "Sin título",
                artista=tema.get("artistName") or "",
                portada=_portada_itunes(tema.get("artworkUrl100") or ""),
                preview=preview,
                ficha=tema.get("trackViewUrl") or "",
                duracion=int((tema.get("trackTimeMillis") or 0) / 1000),
                genero=tema.get("primaryGenreName") or "",
                fuente="Apple Music",
            )
        )
    return temas


def buscar_spotify(consulta):
    token = _token_spotify()
    if not token:
        return []
    url = "https://api.spotify.com/v1/search?" + urlencode(
        {"q": consulta, "type": "track", "limit": 6}
    )
    datos = _json(url, {"Authorization": f"Bearer {token}"})
    temas = []
    for tema in (datos.get("tracks") or {}).get("items") or []:
        artistas = ", ".join(a.get("name") or "" for a in tema.get("artists") or [])
        imagenes = (tema.get("album") or {}).get("images") or []
        portada = imagenes[-1]["url"] if imagenes else ""
        if len(imagenes) > 1:
            portada = imagenes[1]["url"]
        temas.append(
            _pista(
                ident=f"spotify-{tema.get('id')}",
                titulo=tema.get("name") or "Sin título",
                artista=artistas,
                portada=portada,
                preview=tema.get("preview_url") or "",
                ficha=(tema.get("external_urls") or {}).get("spotify") or "",
                duracion=int((tema.get("duration_ms") or 0) / 1000),
                genero="",
                fuente="Spotify",
            )
        )
    return temas


def letra_de(artista, titulo, duracion=0):
    """Letra plana y, si existe, sincronizada. Vacía cuando LRCLIB no la tiene."""
    if not artista or not titulo:
        return {"ok": False, "plana": "", "sincronizada": ""}
    clave = _clave("letra", artista, titulo, int(duracion or 0))
    guardada = cache.get(clave)
    if guardada is not None:
        return guardada
    letra = _letra_de(artista, titulo, duracion)
    # Una letra encontrada no cambia: se guarda un día. Si no hubo, se reintenta en una hora.
    cache.set(clave, letra, 60 * 60 * 24 if letra["ok"] else 60 * 60)
    return letra


def _letra_de(artista, titulo, duracion):
    consultas = [{"artist_name": artista, "track_name": titulo}]
    if duracion:
        consultas.insert(0, {**consultas[0], "duration": int(duracion)})
    for params in consultas:
        try:
            datos = _json("https://lrclib.net/api/get?" + urlencode(params), timeout=8)
        except HTTPError as error:
            if error.code == 404:
                continue
            return {"ok": False, "plana": "", "sincronizada": ""}
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
            return {"ok": False, "plana": "", "sincronizada": ""}
        if datos.get("plainLyrics") or datos.get("syncedLyrics"):
            return _letra(datos)
    return _buscar_letra(artista, titulo, duracion)


def _letra(datos):
    return {
        "ok": bool(datos.get("plainLyrics") or datos.get("syncedLyrics")),
        "plana": datos.get("plainLyrics") or "",
        "sincronizada": datos.get("syncedLyrics") or "",
    }


def _buscar_letra(artista, titulo, duracion):
    vacia = {"ok": False, "plana": "", "sincronizada": ""}
    try:
        lista = _json(
            "https://lrclib.net/api/search?" + urlencode({"q": f"{artista} {titulo}"}),
            timeout=8,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError):
        return vacia
    if not isinstance(lista, list):
        return vacia
    con_letra = [item for item in lista if item.get("plainLyrics") or item.get("syncedLyrics")]
    if not con_letra:
        return vacia
    if duracion:
        con_letra.sort(key=lambda item: abs(int(item.get("duration") or 0) - int(duracion)))
    return _letra(con_letra[0])


def url_de_preview(crudo):
    """Solo deja pasar adelantos de los hosts conocidos. Cualquier otra URL se rechaza."""
    partes = urlsplit((crudo or "").strip())
    host = (partes.hostname or "").lower()
    if partes.scheme != "https" or host not in HOSTS_AUDIO or partes.username or partes.port not in (None, 443):
        raise ValueError("preview no permitida")
    return partes.geturl()


class _RedireccionPermitida(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url_de_preview(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


PREVIEW_MAXIMO = 4_000_000
JSON_MAXIMO = 2_000_000


def abrir_preview(url):
    destino = url_de_preview(url)
    peticion = Request(destino, headers={"User-Agent": AGENTE})
    abridor = build_opener(_RedireccionPermitida)
    return abridor.open(peticion, timeout=8)


def bajar_preview(url):
    """Bytes y tipo del adelanto. Se guarda una hora para que adelantar y
    volver a escuchar no repitan la descarga. Lanza ValueError u OSError."""
    destino = url_de_preview(url)
    clave = _clave("preview", destino)
    almacen = caches["previews"]
    guardado = almacen.get(clave)
    if guardado is not None:
        return guardado
    with abrir_preview(destino) as remoto:
        tipo = (remoto.headers.get("Content-Type") or "audio/mp4").split(";")[0].strip()
        datos = remoto.read(PREVIEW_MAXIMO + 1)
    if len(datos) > PREVIEW_MAXIMO:
        raise ValueError("preview demasiado grande")
    if tipo in {"audio/x-m4p", "audio/m4a", "audio/x-m4a"} or not tipo.startswith("audio/"):
        tipo = "audio/mp4"
    resultado = (datos, tipo)
    almacen.set(clave, resultado, 60 * 60)
    return resultado


def _pista(ident, titulo, artista, portada, preview, ficha, duracion, genero, fuente):
    audio = ""
    if preview:
        try:
            url_de_preview(preview)
            audio = reverse("musica:api_preview") + "?u=" + quote(preview, safe="")
        except ValueError:
            audio = ""
    return {
        "id": ident,
        "titulo": titulo,
        "artista": artista,
        "artistaUrl": "",
        "portada": portada,
        "audio": audio,
        "url": ficha,
        "duracion": duracion,
        "genero": genero,
        "fuente": fuente,
        "externo": True,
    }


def _portada_itunes(url):
    return url.replace("100x100bb", "300x300bb") if url else ""


def _token_spotify():
    ahora = time.time()
    if _spotify["token"] and _spotify["vence"] > ahora + 20:
        return _spotify["token"]
    cliente = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    secreto = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not cliente or not secreto:
        return ""
    credencial = base64.b64encode(f"{cliente}:{secreto}".encode()).decode()
    peticion = Request(
        "https://accounts.spotify.com/api/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {credencial}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": AGENTE,
        },
    )
    with build_opener().open(peticion, timeout=6) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    _spotify["token"] = datos.get("access_token") or ""
    _spotify["vence"] = ahora + int(datos.get("expires_in") or 3600)
    return _spotify["token"]


def _json(url, extra=None, timeout=6):
    cabeceras = {"User-Agent": AGENTE, "Accept": "application/json"}
    if extra:
        cabeceras.update(extra)
    peticion = Request(url, headers=cabeceras)
    with build_opener().open(peticion, timeout=timeout) as respuesta:
        # Un JSON de catálogo nunca pesa megas: se corta para no llenar la memoria.
        return json.loads(respuesta.read(JSON_MAXIMO).decode("utf-8"))

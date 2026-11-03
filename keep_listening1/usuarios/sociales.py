"""Inicio de sesión con plataformas de música a través de django-allauth:
Spotify, Apple Music (Apple ID), YouTube Music (cuenta de Google) y
SoundCloud. Son las cuentas que ya tiene alguien que escucha música.

Las claves de cada plataforma salen de variables de entorno (ver .env.example):
una plataforma sin sus claves no se activa y su botón no aparece (en DEBUG se
muestra apagado, con la variable que falta). Este módulo no importa modelos:
settings.py lo usa para armar SOCIALACCOUNT_PROVIDERS.
"""

import os

# (id de allauth, nombre visible, clase del ícono, prefijo de las variables)
# La clase va completa ("bi-google"): así `npm run iconos` la encuentra y la incluye.
PROVEEDORES = (
    ("spotify", "Spotify", "bi-spotify", "KL_SPOTIFY"),
    ("apple", "Apple Music", "bi-apple-music", "KL_APPLE"),
    ("google", "YouTube Music", "bi-youtube", "KL_GOOGLE"),
    ("soundcloud", "SoundCloud", "bi-cloud-fill", "KL_SOUNDCLOUD"),
)

# Lo que pide cada una: con los permisos mínimos para conocer nombre y correo.
ALCANCES = {
    "spotify": {"SCOPE": ["user-read-email"]},
    "apple": {},
    "google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"prompt": "select_account"}},
    "soundcloud": {},
}


def _app(proveedor, prefijo):
    """La "app" de allauth para una plataforma, o None si faltan sus claves."""
    cliente = os.environ.get(f"{prefijo}_ID", "").strip()
    secreto = os.environ.get(f"{prefijo}_SECRET", "").strip()
    if proveedor == "apple":
        # Apple: ID = Service ID, SECRET = Key ID, más el Team ID y la clave privada (.p8).
        equipo = os.environ.get("KL_APPLE_TEAM", "").strip()
        clave = os.environ.get("KL_APPLE_PRIVATE_KEY", "").replace("\\n", "\n").strip()
        if not (cliente and secreto and equipo and clave):
            return None
        return {"client_id": cliente, "secret": secreto, "key": equipo, "settings": {"certificate_key": clave}}
    if not (cliente and secreto):
        return None
    return {"client_id": cliente, "secret": secreto}


def configuracion():
    """SOCIALACCOUNT_PROVIDERS: todas las plataformas, con su app si está configurada."""
    resultado = {}
    for proveedor, _nombre, _icono, prefijo in PROVEEDORES:
        datos = dict(ALCANCES.get(proveedor, {}))
        app = _app(proveedor, prefijo)
        if app:
            datos["APPS"] = [app]
        resultado[proveedor] = datos
    return resultado


def disponibles(providers):
    """Para los templates: cada plataforma con si está lista para usarse."""
    return [
        {
            "id": proveedor,
            "nombre": nombre,
            "icono": icono,
            "activo": bool(providers.get(proveedor, {}).get("APPS")),
            "variable": f"{prefijo}_ID",
        }
        for proveedor, nombre, icono, prefijo in PROVEEDORES
    ]

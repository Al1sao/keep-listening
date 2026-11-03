"""Portadas minimalistas generadas a partir del nombre del disco.

Cada título se lee buscando una imagen ("Primer verano" → un sol en el
horizonte, "Modo nocturno" → una luna, "Ruta 9" → una ruta en perspectiva).
Si no hay ninguna, sale una composición geométrica. La paleta y los detalles
salen de un hash del título: el mismo disco tiene siempre la misma tapa, y
el vinilo usa esos mismos colores.
"""

import hashlib
import math
import random
import re
import unicodedata
from xml.sax.saxutils import escape

TAM = 600
# Sube cuando cambia el diseño: las portadas se cachean un día en el navegador.
VERSION = 2

# (fondo, tinta, acento): pocas tintas y mucho aire.
PALETAS = [
    ("#f2e8d5", "#1d1d1b", "#e4572e"),
    ("#0e1b2c", "#f4efe6", "#f2c14e"),
    ("#e9e4dc", "#243b53", "#d64545"),
    ("#1f3d36", "#f1ead8", "#e7a33e"),
    ("#f6d6c8", "#3a2e39", "#c8553d"),
    ("#111111", "#f5f5f0", "#c6f54e"),
    ("#d9e4dd", "#264653", "#e76f51"),
    ("#2b2d42", "#edf2f4", "#ef233c"),
    ("#fdf0d5", "#003049", "#c1121f"),
    ("#e0d8f0", "#2d1e5f", "#ff7a59"),
]
OSCURAS = [1, 3, 5, 7]

MOTIVOS = [
    ("sol", r"sol|verano|summer|sun|atardecer|amanecer|calor|dorado"),
    ("luna", r"noche|nocturn|luna|moon|midnight|madrugada|insomnio|sueno|dream"),
    ("ruta", r"ruta|camino|road|km|kilometro|viaje|autopista|rumbo|norte|sur"),
    ("ondas", r"timbre|sesion|eco|onda|radio|senal|frecuencia|sonido|vivo|live"),
    ("lluvia", r"lluvia|rain|tormenta|gris|nublado|llanto"),
    ("mar", r"mar\b|marea|ola|playa|costa|sea|ocean|agua|rio|puerto"),
    ("grilla", r"neon|ciudad|city|luces|edificio|barrio|metro|urbano"),
    ("llama", r"fuego|incendio|fire|brasa|llama|ardor"),
    ("montana", r"montana|cerro|sierra|cumbre|andes|piedra"),
    ("orbita", r"estrella|cosmos|galaxia|espacio|orbita|planeta|satelite|astro"),
    ("flor", r"flor|jardin|primavera|garden|rosa|petalo"),
]


def _normal(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return texto.casefold()


def _azar(titulo):
    semilla = int(hashlib.sha1((titulo or "").encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(semilla)


def motivo_de(titulo):
    normal = _normal(titulo)
    for nombre, patron in MOTIVOS:
        if re.search(patron, normal):
            return nombre
    return "bauhaus"


def paleta_de(titulo):
    azar = _azar(titulo)
    motivo = motivo_de(titulo)
    opciones = OSCURAS if motivo in {"luna", "grilla", "orbita"} else list(range(len(PALETAS)))
    fondo, tinta, acento = PALETAS[azar.choice(opciones)]
    return {"fondo": fondo, "tinta": tinta, "acento": acento, "motivo": motivo}


def rgb(hex_color):
    """"#e4572e" → "228, 87, 46" (para las variables CSS del vinilo)."""
    valor = hex_color.lstrip("#")
    return ", ".join(str(int(valor[i:i + 2], 16)) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Motivos. Cada uno devuelve el SVG del dibujo (sin fondo ni texto).
# ---------------------------------------------------------------------------
def _sol(p, azar):
    y = 330 + azar.randint(-20, 20)
    r = 150 + azar.randint(-15, 25)
    franjas = "".join(
        f'<rect x="0" y="{y - r + 40 + i * 34}" width="{TAM}" height="{8 + i * 2}" fill="{p["fondo"]}"/>'
        for i in range(4, 9)
    )
    return (
        f'<clipPath id="c"><rect width="{TAM}" height="{y}"/></clipPath>'
        f'<g clip-path="url(#c)"><circle cx="300" cy="{y}" r="{r}" fill="{p["acento"]}"/>{franjas}</g>'
        f'<line x1="70" y1="{y}" x2="530" y2="{y}" stroke="{p["tinta"]}" stroke-width="3"/>'
    )


def _luna(p, azar):
    cx, cy, r = 330 + azar.randint(-30, 30), 250 + azar.randint(-20, 20), 120
    estrellas = "".join(
        f'<circle cx="{azar.randint(60, 540)}" cy="{azar.randint(60, 420)}" r="{azar.choice([1.5, 2, 2.5])}" fill="{p["tinta"]}" opacity=".7"/>'
        for _ in range(14)
    )
    return (
        f'{estrellas}<mask id="m"><rect width="{TAM}" height="{TAM}" fill="#fff"/>'
        f'<circle cx="{cx + 48}" cy="{cy - 30}" r="{r - 6}" fill="#000"/></mask>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{p["acento"]}" mask="url(#m)"/>'
    )


def _ruta(p, azar):
    horizonte = 230 + azar.randint(-20, 20)
    guiones = "".join(
        f'<rect x="{300 - (4 + i * 3)}" y="{horizonte + 30 + i * i * 9}" width="{8 + i * 6}" height="{10 + i * 6}" fill="{p["fondo"]}"/>'
        for i in range(1, 8)
    )
    return (
        f'<line x1="0" y1="{horizonte}" x2="{TAM}" y2="{horizonte}" stroke="{p["tinta"]}" stroke-width="2"/>'
        f'<polygon points="290,{horizonte} 310,{horizonte} 560,{TAM} 40,{TAM}" fill="{p["tinta"]}"/>{guiones}'
        f'<circle cx="{azar.choice([150, 450])}" cy="{horizonte - 70}" r="28" fill="{p["acento"]}"/>'
    )


def _ondas(p, azar):
    cx, cy = 300, 300 + azar.randint(-20, 20)
    arcos = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{40 + i * 38}" fill="none" stroke="{p["acento"] if i == 2 else p["tinta"]}" '
        f'stroke-width="{10 if i == 2 else 3}" stroke-dasharray="{"" if i % 2 else "2 10"}" opacity="{1 - i * 0.1}"/>'
        for i in range(7)
    )
    return f'{arcos}<circle cx="{cx}" cy="{cy}" r="20" fill="{p["acento"]}"/>'


def _lluvia(p, azar):
    lineas = "".join(
        f'<line x1="{x}" y1="{y}" x2="{x - 30}" y2="{y + 90}" stroke="{p["tinta"]}" stroke-width="2" opacity=".55"/>'
        for x, y in ((azar.randint(40, 620), azar.randint(-40, 500)) for _ in range(34))
    )
    return (
        f'{lineas}<path d="M300 170 C 360 260, 380 300, 380 340 A 80 80 0 0 1 220 340 C 220 300, 240 260, 300 170 Z" '
        f'fill="{p["acento"]}"/>'
    )


def _mar(p, azar):
    fase = azar.random() * math.pi
    olas = []
    for i in range(7):
        y = 250 + i * 42
        puntos = " ".join(
            f"{x},{y + 16 * math.sin(x / 55 + fase + i * 0.8):.1f}" for x in range(0, TAM + 20, 20)
        )
        color = p["acento"] if i == 2 else p["tinta"]
        olas.append(f'<polyline points="{puntos}" fill="none" stroke="{color}" stroke-width="{7 if i == 2 else 3}"/>')
    return f'<circle cx="{azar.choice([170, 430])}" cy="150" r="46" fill="{p["acento"]}"/>' + "".join(olas)


def _grilla(p, azar):
    celdas = []
    encendida = (azar.randint(0, 5), azar.randint(0, 6))
    for col in range(6):
        for fila in range(7):
            color = p["acento"] if (col, fila) == encendida else p["tinta"]
            opacidad = 1 if (col, fila) == encendida else 0.12 + azar.random() * 0.2
            celdas.append(
                f'<rect x="{90 + col * 72}" y="{70 + fila * 60}" width="46" height="34" rx="3" fill="{color}" opacity="{opacidad:.2f}"/>'
            )
    return "".join(celdas)


def _llama(p, azar):
    return (
        f'<path d="M300 110 C 390 220, 430 300, 400 390 A 110 110 0 0 1 200 390 C 170 300, 250 250, 300 110 Z" fill="{p["acento"]}"/>'
        f'<path d="M300 250 C 345 310, 360 350, 345 400 A 50 50 0 0 1 255 400 C 245 350, 275 320, 300 250 Z" fill="{p["fondo"]}"/>'
    )


def _montana(p, azar):
    pico = 150 + azar.randint(-30, 30)
    return (
        f'<circle cx="{azar.choice([160, 440])}" cy="150" r="40" fill="{p["acento"]}"/>'
        f'<polygon points="60,460 250,{pico} 440,460" fill="{p["tinta"]}"/>'
        f'<polygon points="260,460 400,{pico + 90} 540,460" fill="{p["tinta"]}" opacity=".55"/>'
        f'<polygon points="215,{pico + 60} 250,{pico} 285,{pico + 60} 265,{pico + 50} 250,{pico + 64} 235,{pico + 50}" fill="{p["fondo"]}"/>'
    )


def _orbita(p, azar):
    giro = azar.randint(-30, 30)
    return (
        f'<ellipse cx="300" cy="280" rx="220" ry="70" fill="none" stroke="{p["tinta"]}" stroke-width="2" transform="rotate({giro} 300 280)" opacity=".6"/>'
        f'<circle cx="300" cy="280" r="96" fill="{p["acento"]}"/>'
        f'<circle cx="{300 + int(220 * math.cos(math.radians(giro)))}" cy="{280 + int(220 * math.sin(math.radians(giro)))}" r="14" fill="{p["tinta"]}"/>'
    )


def _flor(p, azar):
    petalos = "".join(
        f'<ellipse cx="300" cy="200" rx="46" ry="92" fill="{p["acento"]}" opacity=".9" transform="rotate({i * 60} 300 290)"/>'
        for i in range(6)
    )
    return f'{petalos}<circle cx="300" cy="290" r="38" fill="{p["tinta"]}"/>'


def _bauhaus(p, azar):
    formas = []
    for _ in range(3):
        tipo = azar.choice(["circulo", "cuadrado", "triangulo", "medio"])
        x, y = azar.choice([150, 300, 450]), azar.choice([160, 290, 400])
        t = azar.choice([90, 120, 160])
        color = azar.choice([p["acento"], p["tinta"]])
        if tipo == "circulo":
            formas.append(f'<circle cx="{x}" cy="{y}" r="{t // 2 + 20}" fill="{color}"/>')
        elif tipo == "cuadrado":
            formas.append(f'<rect x="{x - t // 2}" y="{y - t // 2}" width="{t}" height="{t}" fill="{color}" transform="rotate({azar.choice([0, 15, 45])} {x} {y})"/>')
        elif tipo == "triangulo":
            formas.append(f'<polygon points="{x},{y - t // 2} {x + t // 2},{y + t // 2} {x - t // 2},{y + t // 2}" fill="{color}"/>')
        else:
            formas.append(f'<path d="M{x - t // 2} {y} A {t // 2} {t // 2} 0 0 1 {x + t // 2} {y} Z" fill="{color}"/>')
    return "".join(formas)


DIBUJOS = {
    "sol": _sol, "luna": _luna, "ruta": _ruta, "ondas": _ondas, "lluvia": _lluvia,
    "mar": _mar, "grilla": _grilla, "llama": _llama, "montana": _montana,
    "orbita": _orbita, "flor": _flor, "bauhaus": _bauhaus,
}


def portada_svg(titulo, artista=""):
    """SVG cuadrado (600×600) con el motivo, el título y el artista."""
    p = paleta_de(titulo)
    azar = _azar(titulo)
    dibujo = DIBUJOS[p["motivo"]](p, azar)
    nombre = escape((titulo or "").upper())
    firma = escape((artista or "").lower())
    tamano = 34 if len(nombre) < 16 else 26
    grano = (
        '<filter id="g"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>'
        '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .08 0"/></filter>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TAM} {TAM}" width="{TAM}" height="{TAM}">'
        f'<defs>{grano}</defs>'
        f'<rect width="{TAM}" height="{TAM}" fill="{p["fondo"]}"/>'
        f"{dibujo}"
        f'<rect width="{TAM}" height="{TAM}" filter="url(#g)"/>'
        # Franja de etiqueta: el nombre siempre se lee, pase lo que pase atrás.
        f'<rect y="{TAM - 118}" width="{TAM}" height="118" fill="{p["fondo"]}"/>'
        f'<line x1="44" y1="{TAM - 118}" x2="{TAM - 44}" y2="{TAM - 118}" stroke="{p["tinta"]}" stroke-width="1.5" opacity=".35"/>'
        f'<circle cx="{TAM - 58}" cy="{TAM - 58}" r="14" fill="none" stroke="{p["acento"]}" stroke-width="3"/>'
        f'<circle cx="{TAM - 58}" cy="{TAM - 58}" r="3" fill="{p["acento"]}"/>'
        f'<text x="44" y="{TAM - 64}" font-family="Syne, Helvetica, Arial, sans-serif" font-weight="800" '
        f'font-size="{tamano}" letter-spacing="1" fill="{p["tinta"]}">{nombre}</text>'
        f'<text x="44" y="{TAM - 36}" font-family="Nunito, Helvetica, Arial, sans-serif" font-size="18" '
        f'fill="{p["tinta"]}" opacity=".7">{firma}</text>'
        "</svg>"
    )

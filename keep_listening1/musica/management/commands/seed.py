"""Carga datos de ejemplo: administrador, usuarios, generos, canciones y albumes.

Uso:
    python manage.py seed            # crea lo que falte
    python manage.py seed --reset    # borra el contenido de ejemplo y lo vuelve a crear
"""

import math
import random
import struct
import wave
from datetime import date, timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from musica.models import Album, Cancion, Favorito, Genero, Reproduccion
from tienda.models import Carrito, Formato, Pago, Pedido, PedidoItem
from usuarios.models import Usuario

ADMIN = {"username": "admin", "email": "admin@keeplistening.local", "password": "Admin1234"}
USUARIO = {"username": "sophia", "email": "sophia@keeplistening.local", "password": "Usuario1234"}

ARTISTAS = [
    ("ali", "ali@keeplistening.local", "Usuario1234", "Productor de electrónica desde Buenos Aires."),
    ("lunaverde", "luna@keeplistening.local", "Usuario1234", "Duo de indie rock rosarino."),
    ("timbre", "timbre@keeplistening.local", "Usuario1234", "Jazz instrumental y experimentación."),
]

GENEROS = [
    ("Rock", "Guitarras, batería y actitud."),
    ("Pop", "Melodías directas y estribillos memorables."),
    ("Electrónica", "Sintetizadores, cajas de ritmo y clubes."),
    ("Jazz", "Improvisación y armonías abiertas."),
    ("Hip Hop", "Rimas, samples y groove."),
    ("Folklore", "Raíces y tradición latinoamericana."),
    ("Indie", "Producción independiente y sonidos propios."),
    ("Lo-fi", "Texturas cálidas para acompañar el día."),
]

PALETAS = [
    ((55, 84, 56), (168, 193, 162)),
    ((185, 105, 74), (245, 230, 205)),
    ((34, 54, 38), (217, 154, 78)),
    ((68, 107, 71), (253, 247, 236)),
    ((91, 133, 96), (198, 215, 189)),
    ((164, 68, 58), (237, 220, 191)),
]

CANCIONES = [
    # (titulo, genero, artista, album, pista, frecuencia base)
    ("Amanecer en la ruta", "Rock", "lunaverde", "Ruta 9", 1, 220.0),
    ("Kilómetro cero", "Rock", "lunaverde", "Ruta 9", 2, 246.9),
    ("Faros", "Indie", "lunaverde", "Ruta 9", 3, 261.6),
    ("Circuito nocturno", "Electrónica", "ali", "Modo Nocturno", 1, 293.7),
    ("Neón", "Electrónica", "ali", "Modo Nocturno", 2, 329.6),
    ("Sintonía", "Electrónica", "ali", "Modo Nocturno", 3, 349.2),
    ("Café a las siete", "Jazz", "timbre", "Sesiones de Timbre", 1, 174.6),
    ("Lluvia sobre el asfalto", "Jazz", "timbre", "Sesiones de Timbre", 2, 196.0),
    ("Ventanas abiertas", "Lo-fi", "timbre", None, 1, 207.7),
    ("Primer verano", "Pop", "sophia", "Primer verano", 1, 261.6),
    ("Carta abierta", "Pop", "sophia", "Primer verano", 2, 293.7),
    ("Todo lo que quedó", "Folklore", "sophia", None, 1, 233.1),
    ("Bloque 4", "Hip Hop", "ali", None, 1, 185.0),
    ("Silencio en la sala", "Indie", "lunaverde", None, 1, 220.0),
]

# La tienda vende vinilos. Las portadas no se guardan: se generan con el título
# (tienda/portadas.py), así cada nombre tiene su imagen.
def _album(artista, genero, descripcion, digital, fisico, stock, temas):
    return {
        "artista": artista, "genero": genero, "descripcion": descripcion, "tipo_disco": "VINILO",
        "precio_digital": digital, "precio_fisico": fisico, "stock": stock, "temas": temas,
    }


ALBUMES = {
    "Ruta 9": _album("lunaverde", "Rock", "Disco debut grabado en tres noches de verano, con las ventanas bajas.", 8500, 35000, 12, [
        ["Kilómetro cero", "3:41"], ["Faros", "4:02"], ["Amanecer en la ruta", "3:18"], ["Estación de servicio", "2:57"],
        ["Banquina", "3:33"], ["Peaje", "4:15"], ["Doble línea amarilla", "3:49"], ["Llegar", "5:06"],
    ]),
    "Modo Nocturno": _album("ali", "Electrónica", "Ocho pistas pensadas para la madrugada, cuando la ciudad baja el volumen.", 6000, 30000, 25, [
        ["Circuito nocturno", "5:12"], ["Neón", "4:30"], ["03:14", "3:58"], ["Insomnio", "6:01"],
        ["Luz de heladera", "4:44"], ["Ascensor", "3:27"], ["Luna de terraza", "5:35"], ["Primer colectivo", "4:10"],
    ]),
    "Sesiones de Timbre": _album("timbre", "Jazz", "Grabación en vivo, sin cortes ni ediciones: se oye la sala.", 9000, 42000, 4, [
        ["Toma uno", "6:12"], ["Contrabajo en la cocina", "5:40"], ["Eco", "7:03"], ["Timbre", "4:55"],
        ["Aplausos cortos", "2:10"], ["Última ronda", "8:21"],
    ]),
    "Primer verano": _album("sophia", "Pop", "Canciones sobre mudanzas, playas y despedidas.", 5500, 28000, 18, [
        ["Primer verano", "3:05"], ["Protector solar", "2:58"], ["Mudanza", "3:40"], ["Café a las siete", "3:12"],
        ["Ventanas abiertas", "3:27"], ["Despedida en la terminal", "4:01"], ["Carta abierta", "3:33"],
    ]),
    "Lluvia sobre el asfalto": _album("lunaverde", "Indie", "Guitarras mojadas y un bajo que no para, grabado en un garaje de Rosario.", 7000, 33000, 9, [
        ["Paraguas roto", "3:22"], ["Charcos", "3:47"], ["Lluvia sobre el asfalto", "4:30"], ["Tormenta de verano", "3:05"],
        ["Limpiaparabrisas", "3:58"], ["Gris", "4:12"], ["Sale el sol", "3:36"],
    ]),
    "Marea baja": _album("sophia", "Pop", "Un disco de costa: sal en el pelo y estribillos para gritar con el viento.", 6500, 31000, 15, [
        ["Marea baja", "3:18"], ["Arena", "2:59"], ["Faro", "3:44"], ["Caracoles", "3:11"],
        ["Ola número siete", "3:52"], ["Puerto", "4:05"], ["Volver en micro", "3:29"], ["Mar de fondo", "4:40"],
    ]),
    "Ciudad de neón": _album("ali", "Electrónica", "House de pista chica: luces de colores, humo y un bombo que no afloja.", 7500, 36000, 20, [
        ["Ciudad de neón", "5:48"], ["Subte", "4:22"], ["Kiosco 24 horas", "5:05"], ["Terraza", "6:10"],
        ["Semáforo", "4:37"], ["After", "7:12"],
    ]),
    "Fuego lento": _album("timbre", "Jazz", "Baladas para la sobremesa: saxo grave, piano y escobillas.", 8800, 40000, 6, [
        ["Fuego lento", "6:44"], ["Brasa", "5:20"], ["Sobremesa", "7:31"], ["Humo de cigarro", "4:48"],
        ["Leña", "5:55"], ["Ceniza", "6:02"],
    ]),
    "Cerro abajo": _album("lunaverde", "Folklore", "Chacareras eléctricas y zambas lentas grabadas al pie de la montaña.", 6800, 34000, 10, [
        ["Cerro abajo", "3:50"], ["Viento zonda", "4:12"], ["Piedra y cardón", "3:34"], ["Zamba del regreso", "5:01"],
        ["Quebrada", "3:47"], ["Coplas de la cumbre", "4:25"], ["Bajar al pueblo", "3:59"],
    ]),
    "Órbita": _album("ali", "Lo-fi", "Beats tibios para estudiar mirando por la ventana.", 4500, 26000, 30, [
        ["Despegue", "2:31"], ["Órbita", "2:58"], ["Satélite", "2:44"], ["Gravedad cero", "3:12"],
        ["Luz de estrella", "2:39"], ["Planeta lejano", "3:05"], ["Aterrizaje", "2:50"], ["Cometa", "2:22"],
    ]),
    "Jardín de invierno": _album("sophia", "Indie", "Canciones chiquitas escritas en un invernadero: piano, voz y plantas.", 6000, 30000, 8, [
        ["Jardín de invierno", "3:25"], ["Maceta", "2:48"], ["Primavera tarde", "3:41"], ["Regar de noche", "3:15"],
        ["Pétalos", "2:57"], ["Semilla", "4:02"],
    ]),
    "Geometría": _album("timbre", "Jazz", "Composiciones en compases raros: cuadrados, triángulos y un círculo de bronce.", 9500, 45000, 5, [
        ["Cuadrado", "5:10"], ["Triángulo equilátero", "6:22"], ["Círculo", "4:48"], ["Diagonal", "5:35"],
        ["Rombo", "4:57"], ["Punto de fuga", "7:40"],
    ]),
}


class Command(BaseCommand):
    help = "Carga datos de ejemplo para Keep Listening (admin, usuario, música y tienda)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra el contenido antes de cargar.")
        parser.add_argument(
            "--con-canciones", action="store_true",
            help="Genera también los temas de prueba en audio. Por defecto la música "
                 "es la selección de hip hop y pop con adelantos de Apple (musica/seleccion.py).",
        )

    # -- Generadores de archivos -----------------------------------------
    def portada(self, texto, subtexto, semilla):
        """Genera una portada PNG con degradado y el nombre del tema."""
        random.seed(semilla)
        inicio, fin = random.choice(PALETAS)
        tamano = 600
        imagen = Image.new("RGB", (tamano, tamano), inicio)
        dibujo = ImageDraw.Draw(imagen)

        for y in range(tamano):
            proporcion = y / tamano
            color = tuple(int(inicio[i] + (fin[i] - inicio[i]) * proporcion) for i in range(3))
            dibujo.line([(0, y), (tamano, y)], fill=color)

        # Circulos decorativos
        for _ in range(3):
            radio = random.randint(80, 220)
            cx, cy = random.randint(0, tamano), random.randint(0, tamano)
            dibujo.ellipse(
                [cx - radio, cy - radio, cx + radio, cy + radio],
                outline=(255, 255, 255),
                width=3,
            )

        try:
            fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", 46)
            fuente_chica = ImageFont.truetype("DejaVuSans.ttf", 28)
        except OSError:
            fuente = ImageFont.load_default()
            fuente_chica = ImageFont.load_default()

        dibujo.rectangle([0, tamano - 190, tamano, tamano], fill=(34, 54, 38))
        dibujo.text((40, tamano - 150), texto[:22], font=fuente, fill=(246, 241, 230))
        dibujo.text((40, tamano - 85), subtexto[:28], font=fuente_chica, fill=(198, 215, 189))

        buffer = BytesIO()
        imagen.save(buffer, format="PNG", optimize=True)
        return ContentFile(buffer.getvalue())

    def audio(self, frecuencia, segundos=14, semilla=0):
        """Genera un WAV corto (acorde simple) para que el reproductor funcione."""
        random.seed(semilla)
        tasa = 22050
        buffer = BytesIO()
        with wave.open(buffer, "wb") as onda:
            onda.setnchannels(1)
            onda.setsampwidth(2)
            onda.setframerate(tasa)
            total = int(tasa * segundos)
            armonicos = [(1.0, 0.5), (1.5, 0.22), (2.0, 0.16), (2.51, 0.08)]
            cuadros = bytearray()
            for i in range(total):
                t = i / tasa
                # Envolvente de entrada y salida
                ataque = min(1.0, t / 0.6)
                salida = min(1.0, (segundos - t) / 1.2)
                pulso = 0.85 + 0.15 * math.sin(2 * math.pi * 1.6 * t)
                muestra = 0.0
                for multiplicador, peso in armonicos:
                    muestra += peso * math.sin(2 * math.pi * frecuencia * multiplicador * t)
                muestra *= ataque * salida * pulso * 0.5
                valor = max(-1.0, min(1.0, muestra))
                cuadros += struct.pack("<h", int(valor * 32000))
            onda.writeframes(bytes(cuadros))
        return ContentFile(buffer.getvalue()), segundos

    # -- Comando ----------------------------------------------------------
    @transaction.atomic
    def handle(self, *args, **opciones):
        if opciones["reset"]:
            self.stdout.write("Borrando contenido anterior...")
            Reproduccion.objects.all().delete()
            Favorito.objects.all().delete()
            Pago.objects.all().delete()
            PedidoItem.objects.all().delete()
            Pedido.objects.all().delete()
            Carrito.objects.all().delete()
            Cancion.objects.all().delete()
            Album.objects.all().delete()
            Genero.objects.all().delete()
            Usuario.objects.exclude(is_superuser=True).delete()

        # --- Usuarios ---
        admin, creado = Usuario.objects.get_or_create(
            username=ADMIN["username"],
            defaults={
                "email": ADMIN["email"],
                "rol": Usuario.Rol.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Ali",
                "last_name": "Pérez",
            },
        )
        if creado:
            admin.set_password(ADMIN["password"])
            admin.save()
            self.stdout.write(self.style.SUCCESS(f"Administrador creado: {ADMIN['username']} / {ADMIN['password']}"))

        usuario, creado = Usuario.objects.get_or_create(
            username=USUARIO["username"],
            defaults={
                "email": USUARIO["email"],
                "first_name": "Sophia",
                "last_name": "Benítez",
                "biografia": "Compongo canciones de pop luminoso en Buenos Aires.",
            },
        )
        if creado:
            usuario.set_password(USUARIO["password"])
            usuario.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario creado: {USUARIO['username']} / {USUARIO['password']}"))

        artistas = {"sophia": usuario, "admin": admin}
        for username, email, password, bio in ARTISTAS:
            artista, creado = Usuario.objects.get_or_create(
                username=username, defaults={"email": email, "biografia": bio}
            )
            if creado:
                artista.set_password(password)
                artista.save()
            artistas[username] = artista

        # --- Generos ---
        generos = {}
        for nombre, descripcion in GENEROS:
            genero, _ = Genero.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})
            generos[nombre] = genero

        # --- Albumes ---
        albumes = {}
        for indice, (titulo, datos) in enumerate(ALBUMES.items()):
            album, creado = Album.objects.get_or_create(
                titulo=titulo,
                artista=artistas[datos["artista"]],
                defaults={
                    "genero": generos[datos["genero"]],
                    "descripcion": datos["descripcion"],
                    "fecha_lanzamiento": date.today() - timedelta(days=45 * (indice + 1)),
                    "tipo_disco": datos["tipo_disco"],
                    "precio_digital": datos["precio_digital"],
                    "precio_fisico": datos["precio_fisico"],
                    "stock_fisico": datos["stock"],
                    "lista_temas": datos["temas"],
                },
            )
            if not creado and not album.lista_temas:
                # Datos de ejemplo de versiones anteriores (sin lista de temas): se
                # ponen al día. Un disco ya completo no se toca: el seed corre en
                # cada arranque de la demo y pisaría lo editado desde el panel.
                cambios = {"lista_temas": datos["temas"], "tipo_disco": datos["tipo_disco"]}
                for campo, valor in cambios.items():
                    setattr(album, campo, valor)
                # La vieja portada PNG generada se descarta: ahora se genera con el título.
                if album.portada and album.portada.name.startswith(f"albumes/{album.slug}"):
                    album.portada = None
                album.save()
            albumes[titulo] = album

        # --- Canciones (solo con --con-canciones) ---
        canciones_demo = CANCIONES if opciones["con_canciones"] else []
        for indice, (titulo, genero, artista, album, pista, frecuencia) in enumerate(canciones_demo):
            if Cancion.objects.filter(titulo=titulo, artista=artistas[artista]).exists():
                continue
            archivo_audio, duracion = self.audio(frecuencia, semilla=indice)
            cancion = Cancion(
                titulo=titulo,
                artista=artistas[artista],
                genero=generos[genero],
                tipo=Cancion.Tipo.ALBUM if album else Cancion.Tipo.SENCILLO,
                album=albumes.get(album) if album else None,
                numero_pista=pista,
                duracion_segundos=duracion,
                estado=Cancion.Estado.APROBADA,
                revisada_por=admin,
                fecha_revision=timezone.now(),
            )
            cancion.archivo_audio.save(f"{titulo.lower().replace(' ', '-')}.wav", archivo_audio, save=False)
            cancion.portada.save(
                f"{titulo.lower().replace(' ', '-')}.png",
                self.portada(titulo, artistas[artista].username, indice),
                save=False,
            )
            cancion.reproducciones = random.randint(4, 320)
            cancion.save()

        # --- Dos canciones pendientes de revision (para probar el panel) ---
        pendientes = [
            ("Demo sin mezclar", "Indie", "lunaverde", 261.6),
            ("Prueba de micrófono", "Lo-fi", "ali", 196.0),
        ] if opciones["con_canciones"] else []
        for indice, (titulo, genero, artista, frecuencia) in enumerate(pendientes):
            if Cancion.objects.filter(titulo=titulo).exists():
                continue
            archivo_audio, duracion = self.audio(frecuencia, segundos=8, semilla=50 + indice)
            cancion = Cancion(
                titulo=titulo,
                artista=artistas[artista],
                genero=generos[genero],
                tipo=Cancion.Tipo.SENCILLO,
                duracion_segundos=duracion,
                estado=Cancion.Estado.PENDIENTE,
            )
            cancion.archivo_audio.save(f"{titulo.lower().replace(' ', '-')}.wav", archivo_audio, save=False)
            cancion.portada.save(
                f"{titulo.lower().replace(' ', '-')}.png",
                self.portada(titulo, artistas[artista].username, 50 + indice),
                save=False,
            )
            cancion.save()

        # --- Favoritos e historial del usuario de prueba ---
        aprobadas = list(Cancion.objects.aprobadas())
        random.seed(7)
        # Solo la primera vez: si después los quitó, no vuelven en el próximo arranque.
        if not Favorito.objects.filter(usuario=usuario).exists():
            for cancion in random.sample(aprobadas, min(5, len(aprobadas))):
                Favorito.objects.get_or_create(usuario=usuario, cancion=cancion)
        if not Reproduccion.objects.filter(usuario=usuario).exists():
            for cancion in random.sample(aprobadas, min(8, len(aprobadas))):
                Reproduccion.objects.create(usuario=usuario, cancion=cancion)

        # --- Un pedido pagado de ejemplo ---
        if not Pedido.objects.filter(usuario=usuario).exists() and albumes:
            album = albumes["Modo Nocturno"]
            pedido = Pedido.objects.create(
                usuario=usuario, total=album.precio_digital, estado=Pedido.Estado.PAGADO
            )
            PedidoItem.objects.create(
                pedido=pedido,
                album=album,
                nombre_album=album.titulo,
                artista=album.artista.username,
                formato=Formato.DIGITAL,
                cantidad=1,
                precio_unitario=album.precio_digital,
            )
            Pago.objects.create(
                pedido=pedido,
                nombre_titular="Sophia Benitez",
                ultimos_digitos="1111",
                marca="Visa",
                vencimiento="12/29",
                monto_total=pedido.total,
                estado=Pago.Estado.APROBADO,
            )

        self.stdout.write(self.style.SUCCESS("\nDatos de ejemplo cargados."))
        self.stdout.write(f"  Administrador : {ADMIN['username']} / {ADMIN['password']}")
        self.stdout.write(f"  Usuario       : {USUARIO['username']} / {USUARIO['password']}")
        self.stdout.write("  Otros artistas: ali, lunaverde, timbre (contraseña Usuario1234)")
        self.stdout.write(
            f"  {Cancion.objects.count()} canciones · {Album.objects.count()} álbumes · "
            f"{Genero.objects.count()} géneros"
        )

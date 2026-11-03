"""Modelos del nucleo musical: generos, albumes, canciones, favoritos e historial.

Basado en el diagrama entidad-relacion y en los casos de uso 3, 4, 5 y 7.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify

from .utilidades import slug_unico


class Genero(models.Model):
    """Género musical. Permite explorar por género (mapa de navegación)."""

    nombre = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "genero"
        verbose_name_plural = "generos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('musica:explorar')}?genero={self.slug}"

    def total_canciones(self):
        return self.canciones.filter(estado=Cancion.Estado.APROBADA).count()


class Album(models.Model):
    """Álbum o sencillo publicado. Es también el producto de la tienda."""

    class Tipo(models.TextChoices):
        ALBUM = "ALBUM", "Álbum"
        SENCILLO = "SENCILLO", "Sencillo"

    class TipoDisco(models.TextChoices):
        CD = "CD", "CD"
        VINILO = "VINILO", "Vinilo"
        CASSETTE = "CASSETTE", "Cassette"

    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    artista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="albumes"
    )
    genero = models.ForeignKey(
        Genero, on_delete=models.SET_NULL, null=True, blank=True, related_name="albumes"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ALBUM)
    descripcion = models.TextField(blank=True, max_length=800)
    fecha_lanzamiento = models.DateField()
    portada = models.ImageField(upload_to="albumes/", blank=True, null=True)

    # --- Datos de tienda (formato fisico / digital) ---
    tipo_disco = models.CharField(
        max_length=10, choices=TipoDisco.choices, default=TipoDisco.CD,
        help_text="Formato del soporte físico.",
    )
    disponible_digital = models.BooleanField(default=True)
    disponible_fisico = models.BooleanField(default=True)
    precio_digital = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    precio_fisico = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    stock_fisico = models.PositiveIntegerField(default=0)
    publicado = models.BooleanField(default=True)

    # --- Presentación en la tienda ---
    class EstiloVinilo(models.IntegerChoices):
        NEGRO = 0, "Negro clásico"
        COLOR = 1, "Color translúcido"
        MARMOLADO = 2, "Marmolado"
        SALPICADO = 3, "Salpicado"
        PICTURE = 4, "Picture disc"
        NEON = 5, "Neón"

    estilo_vinilo = models.PositiveSmallIntegerField(
        "edición del vinilo", choices=EstiloVinilo.choices, null=True, blank=True,
        help_text="Vacío: se elige según el título.",
    )
    lista_temas = models.JSONField(
        "lista de temas", default=list, blank=True,
        help_text='Para la contratapa: [["Título", "3:41"], ...]. Si el álbum tiene canciones publicadas, se usan esas.',
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "album"
        verbose_name_plural = "albumes"
        ordering = ["-fecha_lanzamiento"]
        # La disquería y el inicio listan lo publicado, lo más nuevo primero.
        indexes = [models.Index(fields=["publicado", "-fecha_lanzamiento"], name="album_publicado_fecha")]

    def __str__(self):
        return f"{self.titulo} - {self.artista.username}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(self, f"{self.titulo}-{self.artista_id or ''}", "album")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("tienda:detalle_album", args=[self.slug])

    # -- Helpers ----------------------------------------------------------
    @property
    def portada_url(self):
        if self.portada:
            return self.portada.url
        # Sin portada subida: la minimalista que se genera con el título.
        from tienda.portadas import VERSION

        return f'{reverse("tienda:portada", args=[self.slug])}?v={VERSION}'

    @property
    def paleta(self):
        from tienda.portadas import paleta_de, rgb

        p = paleta_de(self.titulo)
        return {**p, "fondo_rgb": rgb(p["fondo"]), "tinta_rgb": rgb(p["tinta"]), "acento_rgb": rgb(p["acento"])}

    @property
    def estilo_de_vinilo(self):
        if self.estilo_vinilo is not None:
            return self.estilo_vinilo
        # Mismo título, misma edición: un número estable a partir del slug.
        return sum(ord(c) for c in (self.slug or self.titulo)) % len(self.EstiloVinilo.choices)

    @property
    def nombre_estilo_vinilo(self):
        return self.EstiloVinilo(self.estilo_de_vinilo).label

    def temas_para_mostrar(self, canciones=None):
        """Temas de la contratapa: las canciones publicadas o la lista cargada a mano.
        Si la vista ya cargó las canciones aprobadas, se pasan y no se vuelven a pedir."""
        propias = list(self.canciones_aprobadas()) if canciones is None else canciones
        if propias:
            return [(c.titulo, c.duracion) for c in propias]
        temas = []
        for tema in self.lista_temas or []:
            if isinstance(tema, (list, tuple)) and tema:
                temas.append((str(tema[0]), str(tema[1]) if len(tema) > 1 else ""))
            elif tema:
                temas.append((str(tema), ""))
        return temas

    def canciones_aprobadas(self):
        return self.canciones.filter(estado=Cancion.Estado.APROBADA).order_by("numero_pista", "id")

    def precio_desde(self):
        precios = []
        if self.disponible_digital:
            precios.append(self.precio_digital)
        if self.disponible_fisico:
            precios.append(self.precio_fisico)
        return min(precios) if precios else None

    def hay_stock(self, formato, cantidad=1):
        if formato == "DIGITAL":
            return self.disponible_digital
        return self.disponible_fisico and self.stock_fisico >= cantidad

    def precio_por_formato(self, formato):
        return self.precio_digital if formato == "DIGITAL" else self.precio_fisico


class CancionQuerySet(models.QuerySet):
    def aprobadas(self):
        return self.filter(estado=Cancion.Estado.APROBADA)

    def pendientes(self):
        return self.filter(estado=Cancion.Estado.PENDIENTE)

    def con_relaciones(self):
        return self.select_related("artista", "genero", "album")


class Cancion(models.Model):
    """Canción publicada por un usuario. Requiere aprobación del administrador."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de revisión"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    class Tipo(models.TextChoices):
        SENCILLO = "SENCILLO", "Sencillo"
        ALBUM = "ALBUM", "Pertenece a un álbum"

    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    artista = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="canciones"
    )
    genero = models.ForeignKey(
        Genero, on_delete=models.SET_NULL, null=True, related_name="canciones"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.SENCILLO)
    album = models.ForeignKey(
        Album, on_delete=models.SET_NULL, null=True, blank=True, related_name="canciones"
    )
    numero_pista = models.PositiveSmallIntegerField(default=1)
    portada = models.ImageField(upload_to="portadas/", blank=True, null=True)
    archivo_audio = models.FileField(upload_to="canciones/")
    duracion_segundos = models.PositiveIntegerField(default=0)

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo_rechazo = models.CharField(max_length=250, blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisiones",
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    reproducciones = models.PositiveIntegerField(default=0)

    objects = CancionQuerySet.as_manager()

    class Meta:
        verbose_name = "cancion"
        verbose_name_plural = "canciones"
        ordering = ["-fecha_subida"]
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["-reproducciones"]),
            # Listados de lo aprobado: por fecha (inicio, Explorar) y por escuchas (panel).
            models.Index(fields=["estado", "-fecha_subida"], name="cancion_estado_fecha"),
            models.Index(fields=["estado", "-reproducciones"], name="cancion_estado_escuchas"),
        ]

    def __str__(self):
        return f"{self.titulo} - {self.artista.username}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unico(self, f"{self.titulo}-{self.artista_id or ''}", "cancion")
        if self.tipo == self.Tipo.SENCILLO:
            self.album = None
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("musica:detalle_cancion", args=[self.slug])

    def recorrido(self):
        """Etapas de la publicación, con el mismo surco que los pedidos.

        Una prueba devuelta termina en "Devuelta" en vez de llegar a la sala.
        """
        final = "Devuelta" if self.estado == self.Estado.RECHAZADA else "En la sala"
        actual = {self.Estado.PENDIENTE: 1}.get(self.estado, 2)
        return [
            {"nombre": nombre, "hecha": i <= actual, "actual": i == actual}
            for i, nombre in enumerate(("Subida", "En revisión", final))
        ]

    # -- Helpers usados por el reproductor y los templates ----------------
    @property
    def portada_url(self):
        if self.portada:
            return self.portada.url
        if self.album and self.album.portada:
            return self.album.portada.url
        return static("img/portada-default.svg")

    @property
    def audio_url(self):
        return self.archivo_audio.url if self.archivo_audio else ""

    @property
    def duracion(self):
        minutos, segundos = divmod(self.duracion_segundos or 0, 60)
        return f"{minutos}:{segundos:02d}"

    @property
    def aprobada(self):
        return self.estado == self.Estado.APROBADA

    def es_favorita_de(self, usuario):
        if not usuario or not usuario.is_authenticated:
            return False
        return Favorito.objects.filter(usuario=usuario, cancion=self).exists()

    def como_pista(self):
        """Diccionario que consume el reproductor en el front."""
        return {
            "id": self.id,
            "titulo": self.titulo,
            "artista": self.artista.username,
            "artistaUrl": reverse("usuarios:perfil_publico", args=[self.artista.username]),
            "portada": self.portada_url,
            "audio": self.audio_url,
            "url": self.get_absolute_url(),
            "duracion": self.duracion_segundos,
            "genero": self.genero.nombre if self.genero else "",
        }


class Favorito(models.Model):
    """Caso de uso 4: guardar canciones en la lista personal."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favoritos"
    )
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="favoritos")
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "favorito"
        verbose_name_plural = "favoritos"
        unique_together = ("usuario", "cancion")
        ordering = ["-fecha_agregado"]

    def __str__(self):
        return f"{self.usuario.username} guardó {self.cancion.titulo}"


class MeGusta(models.Model):
    """Un tema de afuera (adelanto de Apple Music) que el usuario marcó con me gusta.

    No hay registro local de esos temas: se guarda la ficha mínima para
    volver a mostrarlo y reproducirlo sin consultar a Apple.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="me_gusta"
    )
    pista_id = models.CharField("id de la pista", max_length=64)
    titulo = models.CharField(max_length=200)
    artista = models.CharField(max_length=200, blank=True)
    portada = models.URLField(max_length=500, blank=True)
    preview = models.URLField("adelanto", max_length=500)
    ficha = models.URLField(max_length=500, blank=True)
    duracion = models.PositiveIntegerField(default=0)
    genero = models.CharField(max_length=60, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "me gusta"
        verbose_name_plural = "me gusta"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "pista_id"], name="me_gusta_unico"),
        ]
        # El ranking de la sala agrupa por tema; el panel cuenta por fecha.
        indexes = [
            models.Index(fields=["pista_id"], name="me_gusta_pista"),
            models.Index(fields=["fecha"], name="me_gusta_fecha"),
        ]

    def __str__(self):
        return f"A {self.usuario.username} le gusta {self.titulo}"

    def como_pista(self):
        from .catalogo import _pista
        from .seleccion import con_desfase

        pista = _pista(
            ident=self.pista_id, titulo=self.titulo, artista=self.artista, portada=self.portada,
            preview=self.preview, ficha=self.ficha, duracion=self.duracion, genero=self.genero,
            fuente="Apple Music",
        )
        return con_desfase([pista])[0]


class Reproduccion(models.Model):
    """Historial de reproducción (alimenta 'escuchados recientes' y recomendaciones)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reproducciones",
        null=True,
        blank=True,
    )
    cancion = models.ForeignKey(Cancion, on_delete=models.CASCADE, related_name="historial")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "reproduccion"
        verbose_name_plural = "reproducciones"
        ordering = ["-fecha"]
        # El historial de cada usuario y la actividad del panel.
        indexes = [
            models.Index(fields=["usuario", "-fecha"], name="reproduccion_usuario_fecha"),
            models.Index(fields=["fecha"], name="reproduccion_fecha"),
        ]

    def __str__(self):
        return f"{self.cancion.titulo} ({self.fecha:%d/%m/%Y %H:%M})"

"""Formularios de publicación de música (caso de uso 5)."""

from pathlib import Path

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .models import Album, Cancion, Genero
from .utilidades import validar_imagen


def _es_audio_real(archivo):
    """Comprueba la firma del archivo, no la extension que trae el nombre.

    La extension la elige quien sube: por si sola no dice nada sobre el
    contenido. Estas son las cabeceras de los formatos que aceptamos.
    """
    try:
        archivo.seek(0)
        cabecera = archivo.read(12)
    finally:
        archivo.seek(0)

    if len(cabecera) < 12:
        return False
    # MP3 sin etiqueta arranca con el frame sync 0xFF Ex/Fx.
    if cabecera[0] == 0xFF and (cabecera[1] & 0xE0) == 0xE0:
        return True
    return (
        cabecera[:3] == b"ID3"                                      # MP3 etiquetado
        or (cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WAVE")  # WAV
        or cabecera[:4] == b"OggS"                                  # OGG
        or cabecera[:4] == b"fLaC"                                  # FLAC
        or cabecera[4:8] == b"ftyp"                                 # M4A / MP4
    )


class SubirCancionForm(forms.ModelForm):
    """Datos solicitados por el manual: nombre, género, álbum o sencillo, portada y audio."""

    class Meta:
        model = Cancion
        fields = ("titulo", "genero", "tipo", "album", "numero_pista", "portada", "archivo_audio")
        labels = {
            "titulo": "Nombre de la canción",
            "genero": "Género",
            "tipo": "Álbum o sencillo",
            "album": "Álbum al que pertenece",
            "numero_pista": "Número de pista",
            "portada": "Portada",
            "archivo_audio": "Archivo de audio",
        }
        widgets = {
            "titulo": forms.TextInput(
                attrs={"class": "kl-input", "placeholder": "Nombre del tema"}
            ),
            "genero": forms.Select(attrs={"class": "kl-input"}),
            "tipo": forms.Select(attrs={"class": "kl-input", "id": "id_tipo_publicacion"}),
            "album": forms.Select(attrs={"class": "kl-input"}),
            "numero_pista": forms.NumberInput(attrs={"class": "kl-input", "min": 1}),
            "portada": forms.ClearableFileInput(
                attrs={"class": "kl-input", "accept": "image/*", "data-preview": "portada"}
            ),
            "archivo_audio": forms.ClearableFileInput(
                attrs={"class": "kl-input", "accept": "audio/*", "data-audio": "1"}
            ),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields["genero"].queryset = Genero.objects.all()
        self.fields["genero"].empty_label = "Elegí un género"
        if usuario is not None:
            self.fields["album"].queryset = Album.objects.filter(artista=usuario)
        self.fields["album"].required = False
        self.fields["album"].empty_label = "Sin álbum (sencillo)"

    def clean_archivo_audio(self):
        archivo = self.cleaned_data.get("archivo_audio")
        if not archivo or not hasattr(archivo, "size"):
            return archivo

        limite = settings.MAX_AUDIO_MB * 1024 * 1024
        if archivo.size > limite:
            raise forms.ValidationError(
                f"El audio supera el límite de {settings.MAX_AUDIO_MB} MB."
            )

        extension = Path(archivo.name).suffix.lower()
        if extension not in settings.AUDIO_EXTENSIONES:
            raise forms.ValidationError("Formato no soportado. Usa mp3, wav, ogg, m4a o flac.")

        # Solo se inspecciona lo recién subido: un archivo ya guardado (edición
        # sin reemplazar) es un FieldFile, que también tiene read().
        if isinstance(archivo, UploadedFile) and not _es_audio_real(archivo):
            raise forms.ValidationError(
                "El archivo no parece ser audio. Subí un mp3, wav, ogg, m4a o flac válido."
            )
        return archivo

    def clean_portada(self):
        return validar_imagen(self.cleaned_data.get("portada"), "La portada")

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo")
        album = datos.get("album")
        if tipo == Cancion.Tipo.ALBUM and not album:
            self.add_error("album", "Elegí el álbum al que pertenece o publicála como sencillo.")
        if tipo == Cancion.Tipo.SENCILLO:
            datos["album"] = None
        return datos


class EditarCancionForm(SubirCancionForm):
    """Al editar, el archivo de audio es opcional."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["archivo_audio"]
        campo.required = False
        # Sin la casilla "limpiar": una canción no puede quedar sin audio.
        campo.widget = forms.FileInput(attrs=campo.widget.attrs)

    def clean_archivo_audio(self):
        archivo = super().clean_archivo_audio()
        if not archivo and self.instance.pk:
            return self.instance.archivo_audio
        return archivo


class AlbumForm(forms.ModelForm):
    """Alta y edición de álbumes (usuario artista y panel de administración)."""

    class Meta:
        model = Album
        fields = (
            "titulo", "genero", "tipo", "descripcion", "fecha_lanzamiento", "portada",
            "tipo_disco", "disponible_digital", "precio_digital",
            "disponible_fisico", "precio_fisico", "stock_fisico", "publicado",
        )
        labels = {
            "titulo": "Nombre del álbum",
            "genero": "Género",
            "tipo": "Tipo",
            "descripcion": "Descripción",
            "fecha_lanzamiento": "Fecha de lanzamiento",
            "portada": "Portada",
            "tipo_disco": "Formato de disco",
            "disponible_digital": "Disponible en digital",
            "precio_digital": "Precio digital",
            "disponible_fisico": "Disponible en físico",
            "precio_fisico": "Precio físico",
            "stock_fisico": "Stock físico",
            "publicado": "Visible en la tienda",
        }
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "kl-input"}),
            "genero": forms.Select(attrs={"class": "kl-input"}),
            "tipo": forms.Select(attrs={"class": "kl-input"}),
            "descripcion": forms.Textarea(attrs={"class": "kl-input", "rows": 3}),
            "fecha_lanzamiento": forms.DateInput(
                attrs={"class": "kl-input", "type": "date"}, format="%Y-%m-%d"
            ),
            "portada": forms.ClearableFileInput(
                attrs={"class": "kl-input", "accept": "image/*", "data-preview": "portada"}
            ),
            "tipo_disco": forms.Select(attrs={"class": "kl-input"}),
            "precio_digital": forms.NumberInput(attrs={"class": "kl-input", "step": "0.01", "min": 0}),
            "precio_fisico": forms.NumberInput(attrs={"class": "kl-input", "step": "0.01", "min": 0}),
            "stock_fisico": forms.NumberInput(attrs={"class": "kl-input", "min": 0}),
            "disponible_digital": forms.CheckboxInput(attrs={"class": "kl-check"}),
            "disponible_fisico": forms.CheckboxInput(attrs={"class": "kl-check"}),
            "publicado": forms.CheckboxInput(attrs={"class": "kl-check"}),
        }

    def clean_portada(self):
        return validar_imagen(self.cleaned_data.get("portada"), "La portada")

    def clean(self):
        datos = super().clean()
        for campo in ("precio_digital", "precio_fisico"):
            if datos.get(campo) is not None and datos[campo] < 0:
                self.add_error(campo, "El precio no puede ser negativo.")
        if datos.get("disponible_digital") and not datos.get("precio_digital"):
            self.add_error("precio_digital", "Indicá el precio de la versión digital.")
        if datos.get("disponible_fisico") and not datos.get("precio_fisico"):
            self.add_error("precio_fisico", "Indicá el precio de la versión física.")
        if not datos.get("disponible_digital") and not datos.get("disponible_fisico"):
            raise forms.ValidationError("El álbum debe estar disponible en al menos un formato.")
        return datos


class AlbumArtistaForm(AlbumForm):
    """El mismo formulario para quien sube su álbum, sin "Visible en la tienda":
    lo publica el equipo desde el panel, como pasa con las canciones."""

    class Meta(AlbumForm.Meta):
        fields = tuple(f for f in AlbumForm.Meta.fields if f != "publicado")

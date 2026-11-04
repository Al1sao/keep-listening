"""Formulario de pago (caso de uso 6)."""

import re
from datetime import date

from django import forms


def _luhn(numero: str) -> bool:
    """Validación estandar de número de tarjeta."""
    total, alterno = 0, False
    for digito in reversed(numero):
        n = int(digito)
        if alterno:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alterno = not alterno
    return total % 10 == 0


def marca_tarjeta(numero: str) -> str:
    if numero.startswith("4"):
        return "Visa"
    if numero[:2] in {"51", "52", "53", "54", "55"}:
        return "Mastercard"
    if numero[:2] in {"34", "37"}:
        return "American Express"
    return "Tarjeta"


class PagoForm(forms.Form):
    """Datos solicitados en el mockup: titular, apellido, número, vencimiento y PIN."""

    nombre_titular = forms.CharField(
        label="Nombre del titular",
        max_length=60,
        widget=forms.TextInput(attrs={"class": "kl-input", "placeholder": "Sophia", "autocomplete": "cc-given-name"}),
    )
    apellido_titular = forms.CharField(
        label="Apellido del titular",
        max_length=60,
        widget=forms.TextInput(attrs={"class": "kl-input", "placeholder": "Benitez", "autocomplete": "cc-family-name"}),
    )
    numero_tarjeta = forms.CharField(
        label="Número de tarjeta",
        max_length=23,
        widget=forms.TextInput(
            attrs={
                "class": "kl-input",
                "placeholder": "0000 0000 0000 0000",
                "inputmode": "numeric",
                "data-mask": "tarjeta",
                "autocomplete": "cc-number",
            }
        ),
    )
    vencimiento = forms.CharField(
        label="Fecha de vencimiento",
        max_length=5,
        widget=forms.TextInput(
            attrs={
                "class": "kl-input",
                "placeholder": "MM/AA",
                "inputmode": "numeric",
                "data-mask": "vencimiento",
                "autocomplete": "cc-exp",
            }
        ),
    )
    codigo_seguridad = forms.CharField(
        label="Código de seguridad (CVV)",
        max_length=4,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "class": "kl-input",
                "placeholder": "123",
                "inputmode": "numeric",
                "data-mask": "cvv",
                "autocomplete": "cc-csc",
            }
        ),
    )

    def clean_numero_tarjeta(self):
        numero = re.sub(r"\D", "", self.cleaned_data["numero_tarjeta"])
        if not 13 <= len(numero) <= 19:
            raise forms.ValidationError("El número de tarjeta debe tener entre 13 y 19 digitos.")
        if not _luhn(numero):
            raise forms.ValidationError("El número de tarjeta no es válido.")
        return numero

    def clean_vencimiento(self):
        valor = self.cleaned_data["vencimiento"].strip()
        if not re.fullmatch(r"\d{2}/\d{2}", valor):
            raise forms.ValidationError("Usa el formato MM/AA.")
        mes, anio = int(valor[:2]), int(valor[3:])
        if not 1 <= mes <= 12:
            raise forms.ValidationError("El mes debe estar entre 01 y 12.")
        hoy = date.today()
        vence = date(2000 + anio, mes, 1)
        if vence < date(hoy.year, hoy.month, 1):
            raise forms.ValidationError("La tarjeta está vencida.")
        return valor

    def clean_codigo_seguridad(self):
        cvv = self.cleaned_data["codigo_seguridad"].strip()
        if not re.fullmatch(r"\d{3,4}", cvv):
            raise forms.ValidationError("El código de seguridad debe tener 3 o 4 digitos.")
        return cvv

    @property
    def titular_completo(self):
        # Nombre (60) + espacio + apellido (60) = 121: Pago.nombre_titular admite 120
        # y PostgreSQL, a diferencia de SQLite, rechaza el texto largo.
        completo = f"{self.cleaned_data['nombre_titular']} {self.cleaned_data['apellido_titular']}".strip()
        return completo[:120]

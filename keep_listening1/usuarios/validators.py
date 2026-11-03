"""Validadores propios.

El mockup de registro indica: "Debe incluir al menos una mayúscula y un número".
"""

import re

from django.core.exceptions import ValidationError


class ComplejidadValidator:
    """Exige al menos una mayúscula y un número en la contraseña."""

    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                "La contraseña debe incluir al menos una letra mayúscula.",
                code="password_sin_mayuscula",
            )
        if not re.search(r"\d", password):
            raise ValidationError(
                "La contraseña debe incluir al menos un número.",
                code="password_sin_numero",
            )

    def get_help_text(self):
        return "La contraseña debe incluir al menos una mayúscula y un número."

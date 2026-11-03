"""Cómo se crea la cuenta de quien entra por primera vez con una plataforma."""

import re

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AdaptadorSocial(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        """Nombre y usuario a partir de lo que manda la plataforma.

        El usuario se arma con el nombre o con la parte del correo antes de la
        @ (solo letras, números y _ . -); allauth lo hace único si ya existe.
        """
        usuario = super().populate_user(request, sociallogin, data)
        if not usuario.username:
            base = data.get("username") or (data.get("email") or "").split("@")[0] or data.get("first_name") or "oyente"
            usuario.username = re.sub(r"[^\w.\-]", "", base)[:30] or "oyente"
        return usuario

    def is_open_for_signup(self, request, sociallogin):
        # Cualquiera puede crear su cuenta con una plataforma, como con el formulario.
        return True

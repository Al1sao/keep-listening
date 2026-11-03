"""Formularios de registro, inicio de sesión y perfil."""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from musica.utilidades import validar_imagen

from .models import Usuario


class RegistroForm(UserCreationForm):
    """Caso de uso 1: Registro de usuario (nombre de usuario, correo, contraseña)."""

    username = forms.CharField(
        label="Usuario",
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "kl-input", "placeholder": "Tu nombre de usuario",
                   "autocomplete": "username"}
        ),
    )
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={"class": "kl-input", "placeholder": "tucorreo@ejemplo.com",
                   "autocomplete": "email"}
        ),
    )
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={"class": "kl-input", "placeholder": "********",
                   "autocomplete": "new-password", "data-password": "1"}
        ),
        help_text="Mínimo 8 caracteres, al menos una mayúscula y un número.",
    )
    password2 = forms.CharField(
        label="Repetir contraseña",
        widget=forms.PasswordInput(
            attrs={"class": "kl-input", "placeholder": "********",
                   "autocomplete": "new-password", "data-password": "1"}
        ),
    )

    class Meta:
        model = Usuario
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo electrónico.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if Usuario.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ese nombre de usuario ya está en uso.")
        return username

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.email = self.cleaned_data["email"]
        usuario.rol = Usuario.Rol.USUARIO
        if commit:
            usuario.save()
        return usuario


class LoginForm(AuthenticationForm):
    """Caso de uso 2: Inicio de sesión. Acepta usuario o correo electrónico."""

    username = forms.CharField(
        label="Usuario o correo",
        widget=forms.TextInput(
            attrs={"class": "kl-input", "placeholder": "usuario o correo@ejemplo.com",
                   "autocomplete": "username", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={"class": "kl-input", "placeholder": "********",
                   "autocomplete": "current-password", "data-password": "1"}
        ),
    )

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta está desactivada.",
    }

    def clean(self):
        identificador = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if identificador and password:
            # Permite iniciar sesion con el correo electronico.
            if "@" in identificador:
                usuario = Usuario.objects.filter(email__iexact=identificador).first()
                if usuario:
                    identificador = usuario.username
            self.user_cache = authenticate(
                self.request, username=identificador, password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"], code="invalid_login"
                )
            if self.user_cache.bloqueado:
                raise forms.ValidationError(
                    "Tu cuenta fue bloqueada por un administrador. "
                    f"Motivo: {self.user_cache.motivo_bloqueo or 'no especificado'}.",
                    code="bloqueado",
                )
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class PerfilForm(forms.ModelForm):
    """Edición de datos de la cuenta."""

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "biografia", "avatar")
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "biografia": "Biografia",
            "avatar": "Foto de perfil",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "kl-input", "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"class": "kl-input", "autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"class": "kl-input", "autocomplete": "email"}),
            "biografia": forms.Textarea(attrs={"class": "kl-input", "rows": 3}),
            "avatar": forms.ClearableFileInput(attrs={"class": "kl-input", "accept": "image/*"}),
        }

    def clean_avatar(self):
        return validar_imagen(self.cleaned_data.get("avatar"), "La foto")

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        existe = Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Ese correo ya está registrado en otra cuenta.")
        return email

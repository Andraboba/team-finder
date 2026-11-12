from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password

from .validators import normalize_phone, validate_github_url

User = get_user_model()


class RegisterForm(forms.ModelForm):
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("name", "surname", "email", "password")
        labels = {"name": "Имя", "surname": "Фамилия", "email": "Email"}

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    error_messages = {"invalid_login": "Неверный имейл или пароль"}

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if email and password:
            self.user = authenticate(
                self.request, username=email, password=password
            )
            if self.user is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"], code="invalid_login"
                )
        return cleaned_data

    def get_user(self):
        return self.user


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("name", "surname", "avatar", "about", "phone", "github_url")
        labels = {
            "name": "Имя",
            "surname": "Фамилия",
            "avatar": "Аватар",
            "about": "О себе",
            "phone": "Телефон",
            "github_url": "GitHub",
        }
        widgets = {
            "avatar": forms.FileInput(attrs={"accept": "image/*"}),
            "about": forms.Textarea(attrs={"rows": 4, "maxlength": 256}),
            "phone": forms.TextInput(attrs={"placeholder": "+7XXXXXXXXXX"}),
            "github_url": forms.URLInput(
                attrs={"placeholder": "https://github.com/username"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Новый аватар можно не загружать — останется текущий.
        self.fields["avatar"].required = False

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if phone:
            # Номера в БД хранятся в формате +7..., поэтому 8... и +7...
            # одного и того же номера считаются совпадающими.
            duplicates = User.objects.filter(phone=phone).exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError(
                    "Этот номер телефона уже используется другим пользователем."
                )
        return phone

    def clean_github_url(self):
        url = (self.cleaned_data.get("github_url") or "").strip()
        validate_github_url(url)
        return url


class ChangePasswordForm(PasswordChangeForm):
    """Стандартная форма смены пароля (old_password, new_password1, new_password2)."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q

from .avatars import generate_avatar


class UserManager(BaseUserManager):
    """Менеджер пользователей, у которых логином служит email."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Необходимо указать адрес электронной почты")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        # Вход по email не зависит от регистра букв.
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("У суперпользователя должно быть is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("У суперпользователя должно быть is_superuser=True")
        return self._create_user(email, password, **extra_fields)


def avatar_upload_to(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"avatars/avatar_{uuid.uuid4()}.{extension}"


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("Email", unique=True)
    name = models.CharField("Имя", max_length=124)
    surname = models.CharField("Фамилия", max_length=124)
    avatar = models.ImageField("Аватар", upload_to=avatar_upload_to)
    # Телефон не запрашивается при регистрации, поэтому в БД допускается
    # пустая строка; уникальность непустых номеров гарантирует
    # условное ограничение ниже.
    phone = models.CharField("Телефон", max_length=12, blank=True)
    github_url = models.URLField("GitHub", blank=True)
    about = models.TextField("О себе", max_length=256, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    is_staff = models.BooleanField("Администратор", default=False)
    date_joined = models.DateTimeField("Дата регистрации", auto_now_add=True)
    favorites = models.ManyToManyField(
        "projects.Project",
        verbose_name="Избранные проекты",
        related_name="interested_users",
        blank=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name", "surname"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("phone",),
                condition=~Q(phone=""),
                name="unique_non_empty_phone",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.surname} <{self.email}>"

    def get_full_name(self):
        return f"{self.name} {self.surname}".strip()

    def get_short_name(self):
        return self.name

    def save(self, *args, **kwargs):
        # Аватар генерируется один раз — перед первым сохранением в БД.
        if not self.avatar:
            self.avatar.save(
                f"avatar_{uuid.uuid4()}.png", generate_avatar(self.name), save=False
            )
        super().save(*args, **kwargs)

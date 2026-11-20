"""Настройки Django-проекта TeamFinder.

Все чувствительные значения читаются из переменных окружения / файла .env
(см. .env_example) при помощи python-decouple.
"""
import sys
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="django-insecure-dev-only-key")

DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1,[::1]", cast=Csv()
)
CSRF_TRUSTED_ORIGINS = config("DJANGO_CSRF_TRUSTED_ORIGINS", default="", cast=Csv())


# Приложения

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Приложения проекта
    "users.apps.UsersConfig",
    "projects.apps.ProjectsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# В боевом режиме статику (после collectstatic) раздаёт WhiteNoise.
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "team_finder.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Используются шаблоны варианта 3 (перенесены из templates_var3).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "team_finder.wsgi.application"


# База данных: основной вариант — PostgreSQL. Если POSTGRES_DB не задан,
# используется SQLite (удобно для быстрого локального запуска без Docker).

if config("POSTGRES_DB", default=""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB"),
            "USER": config("POSTGRES_USER", default="postgres"),
            "PASSWORD": config("POSTGRES_PASSWORD", default=""),
            "HOST": config("POSTGRES_HOST", default="localhost"),
            "PORT": config("POSTGRES_PORT", default=5432, cast=int),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/projects/list/"
LOGOUT_REDIRECT_URL = "/projects/list/"


# Валидаторы паролей включаются только в боевом режиме,
# чтобы при разработке можно было использовать простые пароли.

AUTH_PASSWORD_VALIDATORS = []
if not DEBUG:
    AUTH_PASSWORD_VALIDATORS.extend(
        [
            {
                "NAME": "django.contrib.auth.password_validation."
                "UserAttributeSimilarityValidator",
            },
            {
                "NAME": "django.contrib.auth.password_validation."
                "MinimumLengthValidator",
            },
            {
                "NAME": "django.contrib.auth.password_validation."
                "CommonPasswordValidator",
            },
            {
                "NAME": "django.contrib.auth.password_validation."
                "NumericPasswordValidator",
            },
        ]
    )


# При запуске тестов используем быстрый хешер паролей — тесты идут в разы быстрее.
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Интернационализация

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


# Статика и медиа

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Отдавать ли медиафайлы средствами Django (нужно при запуске в Docker
# без отдельного веб-сервера). В режиме DEBUG медиа отдаётся всегда.
SERVE_MEDIA = config("SERVE_MEDIA", default=DEBUG, cast=bool)

# Путь к TTF-шрифту для генерации аватаров (необязательно).
AVATAR_FONT_PATH = config("AVATAR_FONT_PATH", default="")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Количество элементов на странице для списков проектов и пользователей
PAGINATE_BY = 12

"""Общие валидаторы и нормализаторы полей."""
import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

PHONE_RE = re.compile(r"^(?:8|\+7)\d{10}$")
GITHUB_HOSTS = {"github.com", "www.github.com"}


def normalize_phone(value):
    """Проверяет формат 8XXXXXXXXXX / +7XXXXXXXXXX и приводит номер к +7XXXXXXXXXX."""
    value = (value or "").strip()
    if not value:
        return ""
    # Допускаем пробелы, дефисы и скобки, которые пользователь мог ввести.
    compact = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.match(compact):
        raise ValidationError(
            "Номер телефона должен быть в формате 8XXXXXXXXXX или +7XXXXXXXXXX."
        )
    if compact.startswith("8"):
        compact = "+7" + compact[1:]
    return compact


def validate_github_url(value):
    """Ссылка должна быть корректным URL и вести именно на github.com."""
    if not value:
        return
    URLValidator(message="Введите корректную ссылку.")(value)
    host = (urlparse(value).hostname or "").lower()
    if host not in GITHUB_HOSTS:
        raise ValidationError("Ссылка должна вести на GitHub (github.com).")

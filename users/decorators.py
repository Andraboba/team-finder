from functools import wraps

from django.conf import settings
from django.http import JsonResponse


def login_required_json(view):
    """Для AJAX-эндпоинтов: анониму возвращаем 401 с JSON вместо редиректа."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Войдите или зарегистрируйтесь",
                    "login_url": settings.LOGIN_URL,
                },
                status=401,
            )
        return view(request, *args, **kwargs)

    return wrapper

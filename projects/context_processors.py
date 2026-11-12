from django.utils.functional import SimpleLazyObject


def favorite_ids(request):
    """Множество id избранных проектов текущего пользователя.

    Позволяет шаблонам проверять «в избранном ли проект» без отдельного
    SQL-запроса на каждую карточку. Вычисляется лениво — только если
    шаблон действительно обращается к переменной.
    """

    def _load():
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return set()
        return set(user.favorites.values_list("id", flat=True))

    return {"favorite_ids": SimpleLazyObject(_load)}

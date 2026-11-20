import json
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .decorators import login_required_json
from .forms import ChangePasswordForm, LoginForm, ProfileEditForm, RegisterForm
from .models import Skill

User = get_user_model()

SKILL_SUGGESTIONS_LIMIT = 10
SKILL_NAME_MAX_LENGTH = Skill._meta.get_field("name").max_length


def user_list(request):
    participants = User.objects.filter(is_active=True).order_by("-id")
    all_skills = Skill.objects.order_by("name")
    active_skill = None
    query_prefix = ""

    skill_name = request.GET.get("skill", "").strip()
    if skill_name:
        # Точное совпадение по названию навыка. В контекст кладём сам
        # объект навыка (шаблон сравнивает active_skill == skill); если
        # такого навыка нет, — строку, чтобы показать «Сбросить»
        # и пустой список.
        active_skill = Skill.objects.filter(name=skill_name).first() or skill_name
        participants = participants.filter(skills__name=skill_name)
        query_prefix = f"skill={quote(skill_name)}&"

    paginator = Paginator(participants, settings.PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "participants": participants,
        "all_skills": all_skills,
        "active_skill": active_skill,
        "page_obj": page_obj,
        "query_prefix": query_prefix,
    }
    return render(request, "users/participants.html", context)


@ensure_csrf_cookie
def user_detail(request, user_id):
    profile_user = get_object_or_404(
        User.objects.prefetch_related("skills", "owned_projects__participants"),
        pk=user_id,
    )
    # Шаблон ожидает профиль под именем "user"; текущий пользователь
    # доступен в шаблоне как request.user. ensure_csrf_cookie нужен,
    # чтобы skills.js мог взять CSRF-токен из cookie.
    return render(request, "users/user-details.html", {"user": profile_user})


@require_GET
def skill_autocomplete(request):
    """GET /users/skills/?q=<начало названия> — до 10 навыков по алфавиту."""
    query = request.GET.get("q", "").strip()
    skills = (
        Skill.objects.filter(name__istartswith=query)
        .order_by("name")
        .values("id", "name")[:SKILL_SUGGESTIONS_LIMIT]
    )
    return JsonResponse(list(skills), safe=False)


def _json_error(message, status):
    return JsonResponse({"status": "error", "message": message}, status=status)


def _request_data(request):
    """Параметры POST-запроса: skills.js шлёт JSON, обычная форма — form-data."""
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None
    return request.POST


@require_POST
@login_required_json
def skill_add(request, user_id):
    """POST /users/<id>/skills/add — добавить навык по skill_id или name."""
    profile_user = User.objects.filter(pk=user_id).first()
    if profile_user is None:
        return _json_error("Пользователь не найден.", 404)
    if profile_user.pk != request.user.pk:
        return _json_error("Изменять навыки может только владелец профиля.", 403)

    data = _request_data(request)
    if data is None:
        return _json_error("Некорректное тело запроса.", 400)

    skill_id = data.get("skill_id")
    name = str(data.get("name") or "").strip()
    created = False
    if skill_id not in (None, ""):
        try:
            skill_id = int(skill_id)
        except (TypeError, ValueError):
            return _json_error("Некорректный skill_id.", 400)
        skill = Skill.objects.filter(pk=skill_id).first()
        if skill is None:
            return _json_error("Навык не найден.", 404)
    elif name:
        if len(name) > SKILL_NAME_MAX_LENGTH:
            return _json_error(
                f"Название навыка длиннее {SKILL_NAME_MAX_LENGTH} символов.", 400
            )
        # Навыки, отличающиеся только регистром, не плодим.
        skill = Skill.objects.filter(name__iexact=name).first()
        if skill is None:
            try:
                with transaction.atomic():
                    skill = Skill.objects.create(name=name)
                created = True
            except IntegrityError:
                # Тот же навык успел создать параллельный запрос.
                skill = Skill.objects.get(name=name)
    else:
        return _json_error("Передайте skill_id или name.", 400)

    added = not profile_user.skills.filter(pk=skill.pk).exists()
    if added:
        profile_user.skills.add(skill)
    return JsonResponse(
        {
            "skill_id": skill.pk,
            "created": created,
            "added": added,
            # id и name нужны skills.js, чтобы сразу нарисовать тег.
            "id": skill.pk,
            "name": skill.name,
        }
    )


@require_POST
@login_required_json
def skill_remove(request, user_id, skill_id):
    """POST /users/<id>/skills/<skill_id>/remove/ — убрать навык у пользователя.

    Сам навык остаётся в БД и доступен другим пользователям.
    """
    profile_user = User.objects.filter(pk=user_id).first()
    if profile_user is None:
        return _json_error("Пользователь не найден.", 404)
    if profile_user.pk != request.user.pk:
        return _json_error("Изменять навыки может только владелец профиля.", 403)
    skill = Skill.objects.filter(pk=skill_id).first()
    if skill is None:
        return _json_error("Навык не найден.", 404)
    if not profile_user.skills.filter(pk=skill.pk).exists():
        return _json_error("У пользователя нет этого навыка.", 400)
    profile_user.skills.remove(skill)
    return JsonResponse({"status": "ok", "skill_id": skill.pk, "removed": True})


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("projects:project_list")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("projects:project_list")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        next_url = request.GET.get("next")
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect("projects:project_list")
    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("projects:project_list")


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    user = request.user
    form = ProfileEditForm(
        request.POST or None, request.FILES or None, instance=user
    )
    if request.method == "POST":
        if form.is_valid():
            form.save()
            return redirect("users:user_detail", user_id=user.id)
        # Не даём невалидным данным формы попасть в шапку страницы.
        user.refresh_from_db()
    return render(request, "users/edit_profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return redirect("users:user_detail", user_id=user.id)
    return render(request, "users/change_password.html", {"form": form})

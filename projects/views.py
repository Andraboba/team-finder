import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ProjectForm
from .models import Project, Skill

AUTOCOMPLETE_LIMIT = 10


def _projects_queryset():
    return (
        Project.objects.select_related("owner")
        .prefetch_related("participants")
        .order_by("-created_at", "-id")
    )


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
                json_dumps_params={"ensure_ascii": False},
            )
        return view(request, *args, **kwargs)

    return wrapper


@ensure_csrf_cookie
def project_list(request):
    projects = _projects_queryset()
    # Фильтр по необходимому навыку: ?skill=<название навыка>,
    # точное совпадение по названию.
    active_skill = request.GET.get("skill", "").strip() or None
    if active_skill:
        projects = projects.filter(skills__name=active_skill).distinct()
    paginator = Paginator(projects, settings.PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page"))
    # В "projects" кладём проекты текущей страницы: шаблон проверяет
    # {% if projects %}, и так не приходится загружать из БД все проекты.
    context = {
        "projects": page_obj.object_list,
        "page_obj": page_obj,
        # Шаблон выводит {{ skill }} и сравнивает его с active_skill,
        # поэтому передаём названия навыков (строки) по алфавиту.
        "all_skills": Skill.objects.order_by("name").values_list("name", flat=True),
        "active_skill": active_skill,
        # Пагинация сохраняет выбранный фильтр.
        "query_prefix": (
            urlencode({"skill": active_skill}) + "&" if active_skill else ""
        ),
    }
    return render(request, "projects/project_list.html", context)


@ensure_csrf_cookie
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related(
            "participants", "skills"
        ),
        pk=project_id,
    )
    return render(request, "projects/project-details.html", {"project": project})


@login_required
@require_http_methods(["GET", "POST"])
def create_project(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        # Автор автоматически становится участником своего проекта.
        project.participants.add(request.user)
        return redirect("projects:project_detail", project_id=project.id)
    return render(
        request, "projects/create-project.html", {"form": form, "is_edit": False}
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.owner_id != request.user.id:
        return HttpResponseForbidden("Редактировать проект может только его автор.")
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("projects:project_detail", project_id=project.id)
    return render(
        request, "projects/create-project.html", {"form": form, "is_edit": True}
    )


@require_POST
@login_required_json
def complete_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if project.owner_id != request.user.id:
        return JsonResponse(
            {"status": "error", "message": "Завершить проект может только автор."},
            status=403,
        )
    if project.status != Project.STATUS_OPEN:
        return JsonResponse(
            {"status": "error", "message": "Проект уже завершён."}, status=400
        )
    project.status = Project.STATUS_CLOSED
    project.save(update_fields=["status"])
    return JsonResponse({"status": "ok", "project_status": project.status})


@require_POST
@login_required_json
def toggle_participate(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    user = request.user
    if project.participants.filter(pk=user.pk).exists():
        project.participants.remove(user)
        participant = False
    else:
        project.participants.add(user)
        participant = True
    return JsonResponse(
        {
            "status": "ok",
            "participant": participant,
            "participants_count": project.participants.count(),
        }
    )


@require_GET
def skill_autocomplete(request):
    """Первые 10 навыков (по алфавиту), название которых начинается с q.

    Фильтрация, сортировка и ограничение выполняются в SQL, из БД
    выбираются только поля id и name.
    """
    query = request.GET.get("q", "").strip()
    skills = (
        Skill.objects.filter(name__istartswith=query)
        .order_by("name")
        .values("id", "name")[:AUTOCOMPLETE_LIMIT]
    )
    return JsonResponse(
        list(skills), safe=False, json_dumps_params={"ensure_ascii": False}
    )


def _request_data(request):
    """Параметры запроса: skills.js шлёт JSON, но поддерживаем и форму."""
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None
    return request.POST


def _json_error(message, status):
    return JsonResponse(
        {"status": "error", "message": message},
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def _owned_project_or_error(request, project_id):
    """Возвращает (project, None) или (None, JSON-ответ с ошибкой)."""
    project = get_object_or_404(Project, pk=project_id)
    if project.owner_id != request.user.id:
        return None, _json_error(
            "Управлять навыками может только автор проекта.", 403
        )
    return project, None


@require_POST
@login_required_json
def add_skill(request, project_id):
    project, error = _owned_project_or_error(request, project_id)
    if error:
        return error
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
        if len(name) > Skill._meta.get_field("name").max_length:
            return _json_error("Слишком длинное название навыка.", 400)
        # Если такой навык уже есть (без учёта регистра), используем его,
        # чтобы в БД не появлялись дубликаты вида «Python» и «python».
        skill = Skill.objects.filter(name__iexact=name).first()
        if skill is None:
            skill = Skill.objects.create(name=name)
            created = True
    else:
        return _json_error("Передайте skill_id или name.", 400)

    added = not project.skills.filter(pk=skill.pk).exists()
    if added:
        project.skills.add(skill)
    return JsonResponse(
        {
            "skill_id": skill.id,
            "created": created,
            "added": added,
            # id и name нужны static/js/skills.js, чтобы нарисовать тег.
            "id": skill.id,
            "name": skill.name,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_POST
@login_required_json
def remove_skill(request, project_id, skill_id):
    project, error = _owned_project_or_error(request, project_id)
    if error:
        return error
    skill = Skill.objects.filter(pk=skill_id).first()
    if skill is None:
        return _json_error("Навык не найден.", 404)
    if not project.skills.filter(pk=skill.pk).exists():
        return _json_error("У проекта нет такого навыка.", 400)
    # Удаляется только связь: сам навык остаётся в БД для других проектов.
    project.skills.remove(skill)
    return JsonResponse({"status": "ok", "skill_id": skill.id, "removed": True})

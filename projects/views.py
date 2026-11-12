from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ProjectForm
from .models import Project


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
            )
        return view(request, *args, **kwargs)

    return wrapper


@ensure_csrf_cookie
def project_list(request):
    projects = _projects_queryset()
    paginator = Paginator(projects, settings.PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page"))
    # В "projects" кладём проекты текущей страницы: шаблон проверяет
    # {% if projects %}, и так не приходится загружать из БД все проекты.
    context = {
        "projects": page_obj.object_list,
        "page_obj": page_obj,
        "query_prefix": "",
    }
    return render(request, "projects/project_list.html", context)


@ensure_csrf_cookie
@login_required
def favorite_projects(request):
    projects = _projects_queryset().filter(interested_users=request.user)
    return render(request, "projects/favorite_projects.html", {"projects": projects})


@ensure_csrf_cookie
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related("participants"),
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


@require_POST
@login_required_json
def toggle_favorite(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    user = request.user
    if user.favorites.filter(pk=project.pk).exists():
        user.favorites.remove(project)
        favorited = False
    else:
        user.favorites.add(project)
        favorited = True
    return JsonResponse({"status": "ok", "favorited": favorited})

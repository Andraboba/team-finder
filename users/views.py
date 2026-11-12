from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ChangePasswordForm, LoginForm, ProfileEditForm, RegisterForm

User = get_user_model()

# Значения параметра ?filter= берутся из шаблона users/participants.html.
FILTER_FAVORITE_OWNERS = "owners-of-favorite-projects"
FILTER_PARTICIPATING_OWNERS = "owners-of-participating-projects"
FILTER_INTERESTED = "interested-in-my-projects"
FILTER_MY_PARTICIPANTS = "participants-of-my-projects"


def filter_users(queryset, user, filter_name):
    """Фильтрует пользователей по одному из четырёх критериев варианта 1.

    Текущий пользователь из результата исключается: он является автором
    и участником собственных проектов, и показывать его самому себе
    в таких подборках бессмысленно.
    """
    if filter_name == FILTER_FAVORITE_OWNERS:
        # Авторы проектов, которые я добавил в избранное.
        queryset = queryset.filter(owned_projects__interested_users=user)
    elif filter_name == FILTER_PARTICIPATING_OWNERS:
        # Авторы проектов, в которых я участвую.
        queryset = queryset.filter(owned_projects__participants=user)
    elif filter_name == FILTER_INTERESTED:
        # Пользователи, добавившие мои проекты в избранное.
        queryset = queryset.filter(favorites__owner=user)
    elif filter_name == FILTER_MY_PARTICIPANTS:
        # Участники моих проектов.
        queryset = queryset.filter(participated_projects__owner=user)
    else:
        return queryset, None
    return queryset.exclude(pk=user.pk).distinct(), filter_name


def user_list(request):
    participants = User.objects.filter(is_active=True).order_by("-id")
    active_filter = None
    if request.user.is_authenticated:
        participants, active_filter = filter_users(
            participants, request.user, request.GET.get("filter")
        )
    paginator = Paginator(participants, settings.PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "participants": participants,
        "page_obj": page_obj,
        "active_filter": active_filter,
        "query_prefix": f"filter={active_filter}&" if active_filter else "",
    }
    return render(request, "users/participants.html", context)


def user_detail(request, user_id):
    profile_user = get_object_or_404(
        User.objects.prefetch_related("owned_projects__participants"), pk=user_id
    )
    # Шаблон ожидает профиль под именем "user"; текущий пользователь
    # доступен в шаблоне как request.user.
    return render(request, "users/user-details.html", {"user": profile_user})


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

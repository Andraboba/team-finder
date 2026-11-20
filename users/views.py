from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ChangePasswordForm, LoginForm, ProfileEditForm, RegisterForm

User = get_user_model()


def user_list(request):
    participants = User.objects.filter(is_active=True).order_by("-id")
    paginator = Paginator(participants, settings.PAGINATE_BY)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "participants": participants,
        "page_obj": page_obj,
        "query_prefix": "",
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

from django.urls import path, re_path

from . import views

app_name = "users"

urlpatterns = [
    path("list/", views.user_list, name="user_list"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    path("change-password/", views.change_password, name="change_password"),
    path("<int:user_id>/", views.user_detail, name="user_detail"),
    # Навыки (вариант 2). В задании пути указаны то со слэшем на конце,
    # то без, а skills.js всегда ставит слэш, — принимаем оба варианта.
    re_path(r"^skills/?$", views.skill_autocomplete, name="skill_autocomplete"),
    re_path(
        r"^(?P<user_id>\d+)/skills/add/?$", views.skill_add, name="skill_add"
    ),
    re_path(
        r"^(?P<user_id>\d+)/skills/(?P<skill_id>\d+)/remove/?$",
        views.skill_remove,
        name="skill_remove",
    ),
]

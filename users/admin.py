from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Skill, User


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name", "surname")


class AdminUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админка пользователей: создание, блокировка (is_active), смена пароля."""

    form = AdminUserChangeForm
    add_form = AdminUserCreationForm

    list_display = ("id", "email", "name", "surname", "phone", "is_active", "is_staff")
    list_display_links = ("id", "email")
    list_filter = ("is_active", "is_staff", "is_superuser")
    list_editable = ("is_active",)
    search_fields = ("email", "name", "surname", "phone")
    ordering = ("-id",)
    readonly_fields = ("date_joined", "last_login")
    filter_horizontal = ("skills", "groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Личные данные",
            {"fields": ("name", "surname", "avatar", "phone", "github_url", "about")},
        ),
        ("Навыки", {"fields": ("skills",)}),
        (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "surname", "password1", "password2"),
            },
        ),
    )


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_display_links = ("id", "name")
    search_fields = ("name",)

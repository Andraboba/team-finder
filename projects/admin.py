from django.contrib import admin

from .models import Project, Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_display_links = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "status", "created_at")
    list_display_links = ("id", "name")
    list_filter = ("status", "created_at", "skills")
    list_editable = ("status",)
    search_fields = ("name", "description", "owner__email", "owner__surname")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)
    filter_horizontal = ("participants", "skills")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

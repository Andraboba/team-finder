from django.urls import path, re_path

from . import views

app_name = "projects"

urlpatterns = [
    path("list/", views.project_list, name="project_list"),
    path("skills/", views.skill_autocomplete, name="skill_autocomplete"),
    path("create-project/", views.create_project, name="create_project"),
    path("<int:project_id>/", views.project_detail, name="project_detail"),
    path("<int:project_id>/edit/", views.edit_project, name="edit_project"),
    path("<int:project_id>/complete/", views.complete_project, name="complete"),
    path(
        "<int:project_id>/toggle-participate/",
        views.toggle_participate,
        name="toggle_participate",
    ),
    # В задании адрес указан без завершающего слэша, а skills.js шлёт
    # запрос со слэшем; поддерживаются оба варианта.
    re_path(
        r"^(?P<project_id>[0-9]+)/skills/add/?$",
        views.add_skill,
        name="add_skill",
    ),
    path(
        "<int:project_id>/skills/<int:skill_id>/remove/",
        views.remove_skill,
        name="remove_skill",
    ),
]

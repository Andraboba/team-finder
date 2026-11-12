from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    path("", RedirectView.as_view(url="/projects/list/", permanent=False)),
    path("admin/", admin.site.urls),
    path("projects/", include("projects.urls")),
    path("users/", include("users.urls")),
]

if settings.SERVE_MEDIA:
    # Отдача загруженных аватаров средствами Django (режим разработки / Docker).
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}
        ),
    ]

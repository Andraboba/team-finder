import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Project

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProjectTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="password", name="Автор", surname="А"
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="password", name="Другой", surname="Б"
        )
        self.project = Project.objects.create(
            name="Проект", description="Описание", owner=self.owner
        )
        self.project.participants.add(self.owner)


class ProjectPagesTests(ProjectTestCase):
    def test_root_redirects_to_list(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/projects/list/")

    def test_project_list(self):
        response = self.client.get(reverse("projects:project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Проект")
        self.assertTemplateUsed(response, "projects/project_list.html")

    def test_project_list_order_and_pagination(self):
        for i in range(13):
            Project.objects.create(name=f"P{i}", owner=self.owner)
        response = self.client.get(reverse("projects:project_list"))
        page = list(response.context["page_obj"])
        self.assertEqual(len(page), 12)
        self.assertEqual(page[0].name, "P12")
        response = self.client.get(reverse("projects:project_list"), {"page": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)

    def test_project_detail(self):
        response = self.client.get(
            reverse("projects:project_detail", args=[self.project.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["project"], self.project)

    def test_project_detail_404(self):
        response = self.client.get(reverse("projects:project_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_no_favorites_in_variant_2(self):
        # В варианте 2 нет «Избранного»: ни сердечка, ни ссылки в меню.
        self.client.force_login(self.other)
        response = self.client.get(reverse("projects:project_list"))
        self.assertNotContains(response, "project-fav-icon")
        self.assertNotContains(response, "/projects/favorites")
        self.assertEqual(self.client.get("/projects/favorites/").status_code, 404)


class CreateEditProjectTests(ProjectTestCase):
    def test_create_requires_login(self):
        response = self.client.get(reverse("projects:create_project"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_create_get(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("projects:create_project"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_edit"])

    def test_create_project_sets_owner_and_participant(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("projects:create_project"),
            {
                "name": "Новый",
                "description": "Текст",
                "github_url": "https://github.com/other/new",
                "status": "open",
            },
        )
        project = Project.objects.get(name="Новый")
        self.assertRedirects(
            response, reverse("projects:project_detail", args=[project.id])
        )
        self.assertEqual(project.owner, self.other)
        self.assertIn(self.other, project.participants.all())

    def test_create_project_invalid(self):
        self.client.force_login(self.other)
        for data in (
            {"name": "", "status": "open"},
            {"name": "X", "status": "unknown"},
            {"name": "X", "status": "open", "github_url": "https://gitlab.com/x"},
        ):
            with self.subTest(data=data):
                response = self.client.post(reverse("projects:create_project"), data)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.count(), 1)

    def test_edit_by_owner(self):
        self.client.force_login(self.owner)
        url = reverse("projects:edit_project", args=[self.project.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_edit"])
        self.assertEqual(response.context["form"].initial["name"], "Проект")
        response = self.client.post(
            url, {"name": "Переименован", "description": "", "status": "closed"}
        )
        self.assertRedirects(
            response, reverse("projects:project_detail", args=[self.project.id])
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Переименован")
        self.assertEqual(self.project.status, "closed")

    def test_edit_forbidden_for_other_user(self):
        self.client.force_login(self.other)
        url = reverse("projects:edit_project", args=[self.project.id])
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(url, {"name": "Взлом", "status": "open"})
        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Проект")

    def test_edit_requires_login(self):
        url = reverse("projects:edit_project", args=[self.project.id])
        self.assertEqual(self.client.get(url).status_code, 302)


class CompleteProjectTests(ProjectTestCase):
    def url(self):
        return reverse("projects:complete", args=[self.project.id])

    def test_owner_completes_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"status": "ok", "project_status": "closed"}
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "closed")

    def test_cannot_complete_closed_project(self):
        self.project.status = "closed"
        self.project.save()
        self.client.force_login(self.owner)
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 400)

    def test_other_user_cannot_complete(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "open")

    def test_anonymous_cannot_complete(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 401)

    def test_get_not_allowed(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url()).status_code, 405)


class ToggleParticipateTests(ProjectTestCase):
    def url(self):
        return reverse("projects:toggle_participate", args=[self.project.id])

    def test_toggle(self):
        self.client.force_login(self.other)
        response = self.client.post(self.url())
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.json()["participant"])
        self.assertIn(self.other, self.project.participants.all())

        response = self.client.post(self.url())
        self.assertFalse(response.json()["participant"])
        self.assertNotIn(self.other, self.project.participants.all())

    def test_anonymous(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.project.participants.count(), 1)

import json
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse, reverse_lazy

from .models import Project, Skill

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

    def test_no_favorites_in_variant_3(self):
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


class SkillTestCase(ProjectTestCase):
    def setUp(self):
        super().setUp()
        self.python = Skill.objects.create(name="Python")
        self.django = Skill.objects.create(name="Django")
        self.docker = Skill.objects.create(name="Docker")

    def add_url(self, project=None):
        return reverse("projects:add_skill", args=[(project or self.project).id])

    def remove_url(self, skill, project=None):
        return reverse(
            "projects:remove_skill", args=[(project or self.project).id, skill.id]
        )

    def post_json(self, url, data):
        return self.client.post(
            url, json.dumps(data), content_type="application/json"
        )


class SkillAutocompleteTests(SkillTestCase):
    url = reverse_lazy("projects:skill_autocomplete")

    def test_startswith_and_alphabetical(self):
        Skill.objects.create(name="Dart")
        Skill.objects.create(name="Go")
        response = self.client.get(self.url, {"q": "D"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [s["name"] for s in response.json()], ["Dart", "Django", "Docker"]
        )

    def test_response_format(self):
        response = self.client.get(self.url, {"q": "pyt"})
        self.assertEqual(response.json(), [{"id": self.python.id, "name": "Python"}])

    def test_only_startswith_not_contains(self):
        response = self.client.get(self.url, {"q": "ython"})
        self.assertEqual(response.json(), [])

    def test_limit_10(self):
        for i in range(15):
            Skill.objects.create(name=f"Skill {i:02d}")
        response = self.client.get(self.url, {"q": "Skill"})
        names = [s["name"] for s in response.json()]
        self.assertEqual(len(names), 10)
        self.assertEqual(names, sorted(names))
        self.assertEqual(names[0], "Skill 00")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)


class AddSkillTests(SkillTestCase):
    def test_add_existing_by_id(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["skill_id"], self.python.id)
        self.assertFalse(data["created"])
        self.assertTrue(data["added"])
        self.assertEqual(data["name"], "Python")
        self.assertIn(self.python, self.project.skills.all())
        self.assertIn(self.project, self.python.projects.all())

    def test_add_new_by_name(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"name": "  Kotlin "})
        skill = Skill.objects.get(name="Kotlin")
        self.assertEqual(
            response.json(),
            {
                "skill_id": skill.id,
                "created": True,
                "added": True,
                "id": skill.id,
                "name": "Kotlin",
            },
        )
        self.assertIn(skill, self.project.skills.all())

    def test_add_by_name_reuses_existing_skill(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"name": "python"})
        data = response.json()
        self.assertEqual(data["skill_id"], self.python.id)
        self.assertFalse(data["created"])
        self.assertTrue(data["added"])
        self.assertEqual(Skill.objects.filter(name__iexact="python").count(), 1)

    def test_repeat_add_returns_added_false(self):
        self.project.skills.add(self.python)
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["added"])
        self.assertFalse(response.json()["created"])
        self.assertEqual(self.project.skills.count(), 1)

    def test_add_with_form_data_and_url_without_slash(self):
        self.client.force_login(self.owner)
        url = f"/projects/{self.project.id}/skills/add"
        response = self.client.post(url, {"skill_id": self.docker.id})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["added"])
        self.assertIn(self.docker, self.project.skills.all())

    def test_add_invalid_requests(self):
        self.client.force_login(self.owner)
        for data, status in (
            ({}, 400),
            ({"name": "   "}, 400),
            ({"skill_id": "abc"}, 400),
            ({"skill_id": 99999}, 404),
            ({"name": "x" * 125}, 400),
        ):
            with self.subTest(data=data):
                response = self.post_json(self.add_url(), data)
                self.assertEqual(response.status_code, status)
        self.assertEqual(self.project.skills.count(), 0)

    def test_not_owner_forbidden(self):
        self.client.force_login(self.other)
        response = self.post_json(self.add_url(), {"name": "Hack"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Skill.objects.filter(name="Hack").exists())
        self.assertEqual(self.project.skills.count(), 0)

    def test_anonymous_unauthorized(self):
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.project.skills.count(), 0)

    def test_project_404(self):
        self.client.force_login(self.owner)
        response = self.post_json(
            reverse("projects:add_skill", args=[99999]), {"name": "X"}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_not_allowed(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.add_url()).status_code, 405)


class RemoveSkillTests(SkillTestCase):
    def setUp(self):
        super().setUp()
        self.project.skills.add(self.python, self.django)

    def test_owner_removes_skill_but_skill_stays_in_db(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn(self.python, self.project.skills.all())
        self.assertIn(self.django, self.project.skills.all())
        self.assertTrue(Skill.objects.filter(pk=self.python.pk).exists())

    def test_not_owner_forbidden(self):
        self.client.force_login(self.other)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 403)
        self.assertIn(self.python, self.project.skills.all())

    def test_anonymous_unauthorized(self):
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.project.skills.count(), 2)

    def test_skill_not_in_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(self.docker))
        self.assertEqual(response.status_code, 400)

    def test_missing_skill_and_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:remove_skill", args=[self.project.id, 99999])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse("projects:remove_skill", args=[99999, self.python.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_not_allowed(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(self.remove_url(self.python)).status_code, 405
        )


class ProjectSkillsPageTests(SkillTestCase):
    def setUp(self):
        super().setUp()
        self.project.skills.add(self.python)

    def detail(self):
        return self.client.get(
            reverse("projects:project_detail", args=[self.project.id])
        )

    def test_owner_sees_controls(self):
        self.client.force_login(self.owner)
        response = self.detail()
        self.assertContains(response, "Необходимые навыки")
        self.assertContains(response, "Python")
        self.assertContains(response, 'id="add-skill-btn"')
        self.assertContains(response, "remove-skill-btn")

    def test_other_user_and_anonymous_only_see_list(self):
        for user in (self.other, None):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                response = self.detail()
                self.assertContains(response, "Python")
                self.assertNotContains(response, 'id="add-skill-btn"')
                self.assertNotContains(response, "remove-skill-btn")

    def test_empty_skills(self):
        self.project.skills.clear()
        self.assertContains(self.detail(), "Навыки не указаны")


class ProjectSkillFilterTests(SkillTestCase):
    def setUp(self):
        super().setUp()
        self.project.skills.add(self.python, self.django)
        self.second = Project.objects.create(name="Второй", owner=self.other)
        self.second.skills.add(self.docker)
        self.cpp = Skill.objects.create(name="C++")
        self.third = Project.objects.create(name="Третий", owner=self.other)
        self.third.skills.add(self.cpp, self.python)

    def get(self, params=None):
        response = self.client.get(reverse("projects:project_list"), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    def test_without_filter(self):
        response = self.get()
        self.assertEqual(len(response.context["page_obj"]), 3)
        self.assertIsNone(response.context["active_skill"])
        self.assertEqual(
            list(response.context["all_skills"]),
            ["C++", "Django", "Docker", "Python"],
        )
        self.assertContains(response, "Фильтр по необходимым навыкам")
        self.assertNotContains(response, "filter-reset")

    def test_filter_by_skill(self):
        response = self.get({"skill": "Python"})
        self.assertEqual(
            list(response.context["page_obj"]), [self.third, self.project]
        )
        self.assertEqual(response.context["active_skill"], "Python")
        self.assertContains(response, 'class="filter-chip active"')
        self.assertContains(response, 'href="/projects/list" class="filter-reset"')

    def test_filter_exact_match(self):
        response = self.get({"skill": "Pyth"})
        self.assertEqual(len(response.context["page_obj"]), 0)
        response = self.get({"skill": "python"})
        self.assertEqual(len(response.context["page_obj"]), 0)

    def test_filter_link_is_urlencoded(self):
        response = self.get()
        self.assertContains(response, 'href="?skill=C%2B%2B"')
        response = self.get({"skill": "C++"})
        self.assertEqual(list(response.context["page_obj"]), [self.third])

    def test_pagination_keeps_filter(self):
        for i in range(13):
            Project.objects.create(name=f"P{i}", owner=self.owner).skills.add(
                self.docker
            )
        response = self.get({"skill": "Docker"})
        self.assertEqual(len(response.context["page_obj"]), 12)
        self.assertEqual(response.context["query_prefix"], "skill=Docker&")
        self.assertContains(response, 'href="?skill=Docker&amp;page=2"')
        response = self.get({"skill": "Docker", "page": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)

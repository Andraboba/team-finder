import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projects.models import Project
from users.forms import ProfileEditForm
from users.models import Skill
from users.validators import normalize_phone

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BaseTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @staticmethod
    def make_user(email, name="Тест", surname="Тестов", password="password", **kw):
        return User.objects.create_user(
            email=email, password=password, name=name, surname=surname, **kw
        )


class UserModelTests(BaseTestCase):
    def test_avatar_generated_on_create(self):
        user = self.make_user("a@example.com", name="Анна")
        self.assertTrue(user.avatar)
        self.assertTrue(user.avatar.name.startswith("avatars/"))
        self.assertTrue(user.avatar.name.endswith(".png"))

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com", password="x", name="A", surname="B"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_email_is_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, "email")


class RegisterLoginTests(BaseTestCase):
    def test_register_creates_user_and_redirects_to_login(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "name": "Иван",
                "surname": "Петров",
                "email": "ivan@example.com",
                "password": "secret123",
            },
        )
        self.assertRedirects(response, reverse("users:login"))
        user = User.objects.get(email="ivan@example.com")
        self.assertTrue(user.check_password("secret123"))
        self.assertTrue(user.avatar)

    def test_register_duplicate_email(self):
        self.make_user("ivan@example.com")
        response = self.client.post(
            reverse("users:register"),
            {
                "name": "Иван",
                "surname": "Петров",
                "email": "IVAN@example.com",
                "password": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_register_requires_fields(self):
        response = self.client.post(reverse("users:register"), {"email": "x@x.ru"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_login_success(self):
        self.make_user("u@example.com", password="pass12345")
        response = self.client.post(
            reverse("users:login"), {"email": "u@example.com", "password": "pass12345"}
        )
        self.assertRedirects(response, reverse("projects:project_list"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_wrong_password(self):
        self.make_user("u@example.com", password="pass12345")
        response = self.client.post(
            reverse("users:login"), {"email": "u@example.com", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный имейл или пароль")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_redirects_to_projects(self):
        user = self.make_user("u@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("users:logout"))
        self.assertRedirects(response, reverse("projects:project_list"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_change_password(self):
        user = self.make_user("u@example.com", password="old_pass_1")
        self.client.force_login(user)
        response = self.client.post(
            reverse("users:change_password"),
            {
                "old_password": "old_pass_1",
                "new_password1": "new_pass_2",
                "new_password2": "new_pass_2",
            },
        )
        self.assertRedirects(response, reverse("users:user_detail", args=[user.id]))
        user.refresh_from_db()
        self.assertTrue(user.check_password("new_pass_2"))

    def test_change_password_requires_login(self):
        response = self.client.get(reverse("users:change_password"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)


class PhoneAndGithubValidationTests(BaseTestCase):
    def setUp(self):
        self.user = self.make_user("u@example.com")

    def form(self, **data):
        base = {"name": "Имя", "surname": "Фамилия", "about": "", "phone": "",
                "github_url": ""}
        base.update(data)
        return ProfileEditForm(data=base, instance=self.user)

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("89001234567"), "+79001234567")
        self.assertEqual(normalize_phone("+79001234567"), "+79001234567")
        self.assertEqual(normalize_phone(""), "")

    def test_invalid_phone_formats(self):
        for phone in ("12345", "79001234567", "+7900123456", "8900123456a",
                      "+89001234567", "890012345678"):
            with self.subTest(phone=phone):
                self.assertFalse(self.form(phone=phone).is_valid())

    def test_phone_saved_in_plus7_format(self):
        form = self.form(phone="89001234567")
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+79001234567")

    def test_phone_unique_across_formats(self):
        self.make_user("other@example.com", phone="+79001234567")
        form = self.form(phone="89001234567")
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_own_phone_is_not_duplicate(self):
        self.user.phone = "+79001234567"
        self.user.save()
        self.assertTrue(self.form(phone="89001234567").is_valid())

    def test_github_url_validation(self):
        self.assertTrue(self.form(github_url="https://github.com/user").is_valid())
        self.assertTrue(self.form(github_url="").is_valid())
        for url in ("https://gitlab.com/user", "not a url",
                    "https://github.com.evil.ru/user", "https://notgithub.com/u"):
            with self.subTest(url=url):
                form = self.form(github_url=url)
                self.assertFalse(form.is_valid())
                self.assertIn("github_url", form.errors)

    def test_edit_profile_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:edit_profile"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("users:edit_profile"),
            {"name": "Новое", "surname": "Имя", "about": "Обо мне",
             "phone": "+79990001122", "github_url": "https://github.com/new"},
        )
        self.assertRedirects(
            response, reverse("users:user_detail", args=[self.user.id])
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Новое")
        self.assertEqual(self.user.phone, "+79990001122")

    def test_edit_profile_invalid_shows_errors(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("users:edit_profile"),
            {"name": "Имя", "surname": "Фамилия", "phone": "123",
             "github_url": "https://gitlab.com/x"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-errors")


class UserListSkillFilterTests(BaseTestCase):
    """Страница /users/list/ и фильтр ?skill=<название навыка>."""

    def setUp(self):
        self.python = Skill.objects.create(name="Python")
        self.django = Skill.objects.create(name="Django")
        self.cpp = Skill.objects.create(name="C++")
        self.alice = self.make_user("alice@example.com", name="Алиса")
        self.bob = self.make_user("bob@example.com", name="Боб")
        self.carol = self.make_user("carol@example.com", name="Кэрол")
        self.alice.skills.add(self.python, self.django)
        self.bob.skills.add(self.python, self.cpp)
        project = Project.objects.create(name="Mine", owner=self.alice)
        project.participants.add(self.alice)

    def get(self, skill=None, **params):
        if skill is not None:
            params["skill"] = skill
        response = self.client.get(reverse("users:user_list"), params)
        self.assertEqual(response.status_code, 200)
        return response

    @staticmethod
    def ids(response):
        return {u.id for u in response.context["page_obj"]}

    def test_list_without_filter(self):
        response = self.get()
        self.assertTemplateUsed(response, "users/participants.html")
        self.assertEqual(
            self.ids(response), set(User.objects.values_list("id", flat=True))
        )
        self.assertIsNone(response.context["active_skill"])
        # Список участников — от новых к старым (по id).
        ids = [u.id for u in response.context["participants"]]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_all_skills_sorted_alphabetically(self):
        response = self.get()
        names = [s.name for s in response.context["all_skills"]]
        self.assertEqual(names, ["C++", "Django", "Python"])
        self.assertContains(response, "Фильтр по навыкам")
        # Название с «+» должно попасть в ссылку закодированным.
        self.assertContains(response, 'href="?skill=C%2B%2B"')

    def test_filter_by_skill(self):
        response = self.get("Python")
        self.assertEqual(self.ids(response), {self.alice.id, self.bob.id})
        self.assertEqual(response.context["active_skill"], self.python)
        self.assertContains(response, 'href="/users/list" class="filter-reset"')
        self.assertContains(response, "filter-chip active")

    def test_filter_by_skill_with_special_chars(self):
        response = self.get("C++")
        self.assertEqual(self.ids(response), {self.bob.id})

    def test_filter_exact_match_only(self):
        # Фильтр — по точному совпадению названия, а не по подстроке.
        response = self.get("Pyth")
        self.assertEqual(self.ids(response), set())
        response = self.get("python")
        self.assertEqual(self.ids(response), set())

    def test_unknown_skill_shows_empty_list_and_reset(self):
        response = self.get("Haskell")
        self.assertEqual(self.ids(response), set())
        self.assertEqual(response.context["active_skill"], "Haskell")
        self.assertContains(response, "Пока нет участников")
        self.assertContains(response, 'class="filter-reset"')

    def test_filter_keeps_skill_in_pagination_links(self):
        for i in range(13):
            self.make_user(f"py{i}@example.com").skills.add(self.python)
        response = self.get("Python")
        self.assertEqual(len(response.context["page_obj"]), 12)
        self.assertContains(response, "?skill=Python&amp;page=2")
        response = self.get("Python", page=2)
        self.assertEqual(len(response.context["page_obj"]), 3)

    def test_pagination_12_per_page(self):
        for i in range(10):
            self.make_user(f"extra{i}@example.com")
        response = self.get()
        self.assertEqual(len(response.context["page_obj"]), 12)
        response = self.get(page=2)
        self.assertEqual(len(response.context["page_obj"]), 1)

    def test_user_detail(self):
        response = self.client.get(reverse("users:user_detail", args=[self.alice.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.alice)
        self.assertContains(response, "Mine")
        self.assertContains(response, "Python")
        self.assertContains(response, "Django")
        # Аноним видит навыки, но не элементы управления ими.
        self.assertNotContains(response, "add-skill-btn")
        self.assertNotContains(response, "remove-skill-btn")
        self.assertIn("csrftoken", response.cookies)

    def test_user_detail_owner_sees_skill_controls(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("users:user_detail", args=[self.alice.id]))
        self.assertContains(response, "+ Добавить навык")
        self.assertContains(response, "remove-skill-btn")

    def test_user_detail_other_user_cannot_manage_skills(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("users:user_detail", args=[self.alice.id]))
        self.assertNotContains(response, "add-skill-btn")
        self.assertNotContains(response, "remove-skill-btn")

    def test_user_without_skills(self):
        response = self.client.get(reverse("users:user_detail", args=[self.carol.id]))
        self.assertContains(response, "Навыки не указаны")

    def test_user_detail_404(self):
        response = self.client.get(reverse("users:user_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)


class SkillModelTests(BaseTestCase):
    def test_skill_users_related_name(self):
        skill = Skill.objects.create(name="Go")
        user = self.make_user("go@example.com")
        user.skills.add(skill)
        self.assertEqual(list(skill.users.all()), [user])
        self.assertEqual(str(skill), "Go")

    def test_skill_stays_after_user_deleted(self):
        skill = Skill.objects.create(name="Rust")
        user = self.make_user("rust@example.com")
        user.skills.add(skill)
        user.delete()
        self.assertTrue(Skill.objects.filter(name="Rust").exists())


class SkillAutocompleteTests(BaseTestCase):
    url = "/users/skills/"

    def test_returns_matches_alphabetically(self):
        for name in ["Django", "Docker", "DRF", "Python", "Dart"]:
            Skill.objects.create(name=name)
        response = self.client.get(self.url, {"q": "d"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            [s["name"] for s in data], ["Dart", "Django", "Docker", "DRF"]
        )
        self.assertEqual(set(data[0]), {"id", "name"})
        self.assertEqual(data[1]["id"], Skill.objects.get(name="Django").id)

    def test_startswith_not_contains(self):
        Skill.objects.create(name="JavaScript")
        Skill.objects.create(name="TypeScript")
        response = self.client.get(self.url, {"q": "Script"})
        self.assertEqual(response.json(), [])

    def test_limit_10(self):
        for i in range(15):
            Skill.objects.create(name=f"Skill {i:02d}")
        response = self.client.get(self.url, {"q": "Skill"})
        names = [s["name"] for s in response.json()]
        self.assertEqual(names, [f"Skill {i:02d}" for i in range(10)])

    def test_url_without_trailing_slash(self):
        Skill.objects.create(name="Python")
        response = self.client.get("/users/skills", {"q": "Py"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "Python")

    def test_post_not_allowed(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class SkillAddRemoveTests(BaseTestCase):
    def setUp(self):
        self.owner = self.make_user("owner@example.com", name="Владелец")
        self.other = self.make_user("other@example.com", name="Другой")
        self.python = Skill.objects.create(name="Python")

    def add_url(self, user=None, slash=True):
        url = f"/users/{(user or self.owner).id}/skills/add"
        return url + "/" if slash else url

    def remove_url(self, skill, user=None):
        return f"/users/{(user or self.owner).id}/skills/{skill.id}/remove/"

    def post_json(self, url, data):
        return self.client.post(url, data, content_type="application/json")

    def test_add_existing_skill_by_id(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["skill_id"], self.python.id)
        self.assertIs(data["created"], False)
        self.assertIs(data["added"], True)
        self.assertEqual(data["name"], "Python")
        self.assertIn(self.python, self.owner.skills.all())

    def test_add_new_skill_by_name(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"name": "  Kotlin "})
        data = response.json()
        skill = Skill.objects.get(name="Kotlin")
        self.assertEqual(data["skill_id"], skill.id)
        self.assertIs(data["created"], True)
        self.assertIs(data["added"], True)
        self.assertIn(skill, self.owner.skills.all())

    def test_add_by_name_of_existing_skill_does_not_duplicate(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.add_url(), {"name": "python"})
        data = response.json()
        self.assertEqual(data["skill_id"], self.python.id)
        self.assertIs(data["created"], False)
        self.assertIs(data["added"], True)
        self.assertEqual(Skill.objects.count(), 1)

    def test_add_twice_returns_added_false(self):
        self.client.force_login(self.owner)
        self.post_json(self.add_url(), {"skill_id": self.python.id})
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {k: response.json()[k] for k in ("skill_id", "created", "added")},
            {"skill_id": self.python.id, "created": False, "added": False},
        )
        self.assertEqual(self.owner.skills.count(), 1)

    def test_add_with_form_data_and_without_trailing_slash(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.add_url(slash=False), {"skill_id": self.python.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["added"], True)

    def test_add_validation_errors(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.post_json(self.add_url(), {}).status_code, 400)
        self.assertEqual(
            self.post_json(self.add_url(), {"name": "   "}).status_code, 400
        )
        self.assertEqual(
            self.post_json(self.add_url(), {"name": "x" * 125}).status_code, 400
        )
        self.assertEqual(
            self.post_json(self.add_url(), {"skill_id": "abc"}).status_code, 400
        )
        self.assertEqual(
            self.post_json(self.add_url(), {"skill_id": 9999}).status_code, 404
        )
        response = self.client.post(
            self.add_url(), "not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.owner.skills.count(), 0)

    def test_add_to_other_user_forbidden(self):
        self.client.force_login(self.other)
        response = self.post_json(self.add_url(), {"name": "Hacking"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.owner.skills.count(), 0)
        self.assertFalse(Skill.objects.filter(name="Hacking").exists())

    def test_add_anonymous(self):
        response = self.post_json(self.add_url(), {"skill_id": self.python.id})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.owner.skills.count(), 0)

    def test_add_unknown_user(self):
        self.client.force_login(self.owner)
        response = self.post_json("/users/99999/skills/add/", {"name": "Go"})
        self.assertEqual(response.status_code, 404)

    def test_add_get_not_allowed(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.add_url()).status_code, 405)

    def test_remove_skill(self):
        self.owner.skills.add(self.python)
        self.other.skills.add(self.python)
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertNotIn(self.python, self.owner.skills.all())
        # Сам навык остаётся в БД и у других пользователей.
        self.assertTrue(Skill.objects.filter(pk=self.python.pk).exists())
        self.assertIn(self.python, self.other.skills.all())

    def test_remove_without_trailing_slash(self):
        self.owner.skills.add(self.python)
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(self.python).rstrip("/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.owner.skills.count(), 0)

    def test_remove_other_users_skill_forbidden(self):
        self.owner.skills.add(self.python)
        self.client.force_login(self.other)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 403)
        self.assertIn(self.python, self.owner.skills.all())

    def test_remove_anonymous(self):
        self.owner.skills.add(self.python)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 401)
        self.assertIn(self.python, self.owner.skills.all())

    def test_remove_skill_not_owned(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url(self.python))
        self.assertEqual(response.status_code, 400)

    def test_remove_unknown_skill(self):
        self.client.force_login(self.owner)
        response = self.client.post(f"/users/{self.owner.id}/skills/9999/remove/")
        self.assertEqual(response.status_code, 404)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(
            self.add_url(), {"skill_id": self.python.id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.owner.skills.count(), 0)

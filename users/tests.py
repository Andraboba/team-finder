import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from projects.models import Project
from users.forms import ProfileEditForm
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


class UserListFilterTests(BaseTestCase):
    """me: избранное и участия; проверяем все четыре фильтра."""

    def setUp(self):
        self.me = self.make_user("me@example.com", name="Я")
        self.fav_owner = self.make_user("fav@example.com", name="Автор-избранного")
        self.part_owner = self.make_user("part@example.com", name="Автор-участия")
        self.fan = self.make_user("fan@example.com", name="Поклонник")
        self.member = self.make_user("member@example.com", name="Участник")
        self.stranger = self.make_user("stranger@example.com", name="Чужой")

        fav_project = Project.objects.create(name="Fav", owner=self.fav_owner)
        part_project = Project.objects.create(name="Part", owner=self.part_owner)
        my_project = Project.objects.create(name="Mine", owner=self.me)
        my_project.participants.add(self.me, self.member)
        part_project.participants.add(self.part_owner, self.me)
        self.me.favorites.add(fav_project, my_project)
        self.fan.favorites.add(my_project)

    def get_ids(self, filter_name=None):
        params = {"filter": filter_name} if filter_name else {}
        response = self.client.get(reverse("users:user_list"), params)
        self.assertEqual(response.status_code, 200)
        return {u.id for u in response.context["page_obj"]}, response

    def test_list_without_filter(self):
        ids, _ = self.get_ids()
        self.assertEqual(ids, set(User.objects.values_list("id", flat=True)))

    def test_filter_ignored_for_anonymous(self):
        ids, response = self.get_ids("owners-of-favorite-projects")
        self.assertEqual(len(ids), User.objects.count())
        self.assertIsNone(response.context["active_filter"])

    def test_owners_of_favorite_projects(self):
        self.client.force_login(self.me)
        ids, response = self.get_ids("owners-of-favorite-projects")
        self.assertEqual(ids, {self.fav_owner.id})
        self.assertEqual(response.context["active_filter"],
                         "owners-of-favorite-projects")

    def test_owners_of_participating_projects(self):
        self.client.force_login(self.me)
        ids, _ = self.get_ids("owners-of-participating-projects")
        self.assertEqual(ids, {self.part_owner.id})

    def test_interested_in_my_projects(self):
        self.client.force_login(self.me)
        ids, _ = self.get_ids("interested-in-my-projects")
        self.assertEqual(ids, {self.fan.id})

    def test_participants_of_my_projects(self):
        self.client.force_login(self.me)
        ids, _ = self.get_ids("participants-of-my-projects")
        self.assertEqual(ids, {self.member.id})

    def test_unknown_filter_shows_all(self):
        self.client.force_login(self.me)
        ids, response = self.get_ids("something-else")
        self.assertEqual(len(ids), User.objects.count())
        self.assertIsNone(response.context["active_filter"])

    def test_pagination_12_per_page(self):
        for i in range(10):
            self.make_user(f"extra{i}@example.com")
        response = self.client.get(reverse("users:user_list"))
        self.assertEqual(len(response.context["page_obj"]), 12)
        response = self.client.get(reverse("users:user_list"), {"page": 2})
        self.assertEqual(len(response.context["page_obj"]), 4)

    def test_user_detail(self):
        response = self.client.get(reverse("users:user_detail", args=[self.me.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user"], self.me)
        self.assertContains(response, "Mine")

    def test_user_detail_404(self):
        response = self.client.get(reverse("users:user_detail", args=[99999]))
        self.assertEqual(response.status_code, 404)

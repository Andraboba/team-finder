"""Наполнение БД тестовыми данными.

Использование:
    python manage.py seed_data          # создать недостающие данные
    python manage.py seed_data --reset  # удалить тестовых пользователей и создать заново

Команда идемпотентна: повторный запуск не создаёт дубликатов.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from projects.models import Project
from users.models import Skill

User = get_user_model()

SUPERUSER = {
    "email": "admin@teamfinder.local",
    "password": "admin12345",
    "name": "Админ",
    "surname": "Администраторов",
}

USERS = [
    {
        "email": "maria@yandex.ru",
        "password": "password",
        "name": "Мария",
        "surname": "Иванова",
        "phone": "+79001112233",
        "github_url": "https://github.com/maria-ivanova",
        "about": "Python-разработчица, люблю Django и чистый код.",
    },
    {
        "email": "ivan@example.com",
        "password": "password",
        "name": "Иван",
        "surname": "Петров",
        "phone": "+79002223344",
        "github_url": "https://github.com/ivan-petrov",
        "about": "Фронтенд-разработчик: React, TypeScript, немного дизайна.",
    },
    {
        "email": "olga@example.com",
        "password": "password",
        "name": "Ольга",
        "surname": "Смирнова",
        "phone": "",
        "github_url": "",
        "about": "UX/UI-дизайнер, ищу интересные pet-проекты.",
    },
    {
        "email": "petr@example.com",
        "password": "password",
        "name": "Пётр",
        "surname": "Кузнецов",
        "phone": "+79004445566",
        "github_url": "https://github.com/petr-kuznetsov",
        "about": "DevOps-инженер: Docker, CI/CD, Linux.",
    },
]

# (email автора, название, описание, github, статус)
PROJECTS = [
    (
        "maria@yandex.ru",
        "Трекер привычек",
        "Веб-приложение для отслеживания полезных привычек с напоминаниями "
        "и статистикой. Ищем фронтендера и дизайнера.",
        "https://github.com/maria-ivanova/habit-tracker",
        "open",
    ),
    (
        "maria@yandex.ru",
        "Бот для книжного клуба",
        "Telegram-бот, который помогает выбирать книгу месяца и собирать отзывы.",
        "",
        "closed",
    ),
    (
        "ivan@example.com",
        "Портфолио-конструктор",
        "Сервис, позволяющий за пару минут собрать сайт-портфолио из шаблонов.",
        "https://github.com/ivan-petrov/portfolio-builder",
        "open",
    ),
    (
        "olga@example.com",
        "Дизайн-система для НКО",
        "Открытая библиотека компонентов для сайтов некоммерческих организаций.",
        "",
        "open",
    ),
    (
        "petr@example.com",
        "Домашний CI-сервер",
        "Лёгкий self-hosted CI на Docker для небольших команд и pet-проектов.",
        "https://github.com/petr-kuznetsov/home-ci",
        "open",
    ),
]

# email участника -> названия проектов, в которых он участвует
PARTICIPATIONS = {
    "ivan@example.com": ["Трекер привычек", "Домашний CI-сервер"],
    "olga@example.com": ["Трекер привычек", "Портфолио-конструктор"],
    "maria@yandex.ru": ["Дизайн-система для НКО"],
    "petr@example.com": ["Портфолио-конструктор"],
}

# email пользователя -> навыки (навыки, которых нет в БД, создаются)
SKILLS = {
    "maria@yandex.ru": ["Python", "Django", "PostgreSQL", "Git"],
    "ivan@example.com": ["JavaScript", "React", "TypeScript", "Git"],
    "olga@example.com": ["Figma", "UX/UI", "HTML/CSS"],
    "petr@example.com": ["Docker", "Linux", "CI/CD", "Python", "PostgreSQL"],
}


class Command(BaseCommand):
    help = "Создаёт суперпользователя, тестовых пользователей, проекты, участия и навыки."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Удалить тестовых пользователей (и их проекты) перед созданием.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        emails = [SUPERUSER["email"]] + [u["email"] for u in USERS]
        if options["reset"]:
            deleted, _ = User.objects.filter(email__in=emails).delete()
            self.stdout.write(f"Удалено объектов: {deleted}")

        if not User.objects.filter(email=SUPERUSER["email"]).exists():
            User.objects.create_superuser(**SUPERUSER)
            self.stdout.write(f"Создан суперпользователь {SUPERUSER['email']}")

        users = {}
        for data in USERS:
            data = dict(data)
            password = data.pop("password")
            user = User.objects.filter(email=data["email"]).first()
            if user is None:
                user = User.objects.create_user(password=password, **data)
                self.stdout.write(f"Создан пользователь {user.email}")
            users[user.email] = user

        projects = {}
        for email, name, description, github_url, status in PROJECTS:
            owner = users[email]
            project, created = Project.objects.get_or_create(
                owner=owner,
                name=name,
                defaults={
                    "description": description,
                    "github_url": github_url,
                    "status": status,
                },
            )
            # Автор всегда участник своего проекта.
            project.participants.add(owner)
            projects[name] = project
            if created:
                self.stdout.write(f"Создан проект «{name}»")

        for email, names in PARTICIPATIONS.items():
            for name in names:
                projects[name].participants.add(users[email])

        for email, names in SKILLS.items():
            skills = [Skill.objects.get_or_create(name=name)[0] for name in names]
            users[email].skills.add(*skills)

        self.stdout.write(self.style.SUCCESS("Тестовые данные загружены."))

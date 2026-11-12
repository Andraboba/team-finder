from django import forms

from users.validators import validate_github_url

from .models import Project

STATUS_LABELS = [
    (Project.STATUS_OPEN, "Открыт"),
    (Project.STATUS_CLOSED, "Закрыт"),
]


class ProjectForm(forms.ModelForm):
    status = forms.ChoiceField(label="Статус", choices=STATUS_LABELS)

    class Meta:
        model = Project
        fields = ("name", "description", "github_url", "status")
        labels = {
            "name": "Название проекта",
            "description": "Описание проекта",
            "github_url": "Ссылка на GitHub",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "github_url": forms.URLInput(
                attrs={"placeholder": "https://github.com/username/repo"}
            ),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Укажите название проекта.")
        return name

    def clean_github_url(self):
        url = (self.cleaned_data.get("github_url") or "").strip()
        validate_github_url(url)
        return url

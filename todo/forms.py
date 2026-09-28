from django import forms

from .models import Category, Note, Priority, SubTask, Task

# every widget gets the same "field-input" class so one CSS rule styles them all

INPUT = "field-input"
TEXTAREA = "field-input field-textarea"


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "deadline", "status", "category", "priority"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Finish the quarterly report",
                "autofocus": True,
            }),
            "description": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 4,
                "placeholder": "Any extra detail worth remembering…",
            }),
            "deadline": forms.DateTimeInput(
                attrs={"class": INPUT, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "status": forms.Select(attrs={"class": INPUT}),
            "category": forms.Select(attrs={"class": INPUT}),
            "priority": forms.Select(attrs={"class": INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deadline"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["description"].required = False
        self.fields["deadline"].required = False
        self.fields["category"].required = False
        self.fields["category"].empty_label = "No category"
        self.fields["priority"].required = False
        self.fields["priority"].empty_label = "No priority"


class SubTaskForm(forms.ModelForm):
    class Meta:
        model = SubTask
        fields = ["parent_task", "title", "status"]
        widgets = {
            "parent_task": forms.Select(attrs={"class": INPUT}),
            "title": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Draft the outline", "autofocus": True,
            }),
            "status": forms.Select(attrs={"class": INPUT}),
        }
        labels = {"parent_task": "Part of"}


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["task", "content"]
        widgets = {
            "task": forms.Select(attrs={"class": INPUT}),
            "content": forms.Textarea(attrs={
                "class": TEXTAREA, "rows": 5,
                "placeholder": "Write it down before you forget…", "autofocus": True,
            }),
        }
        labels = {"task": "Attached to"}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. Work", "autofocus": True,
            }),
        }


class PriorityForm(forms.ModelForm):
    class Meta:
        model = Priority
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": INPUT, "placeholder": "e.g. High", "autofocus": True,
            }),
        }

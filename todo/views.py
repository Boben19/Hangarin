from django import forms
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView,
)

from .forms import CategoryForm, NoteForm, PriorityForm, SubTaskForm, TaskForm
from .models import Category, Note, Priority, SubTask, Task


class HomePageView(TemplateView):
    """
    Landing page / dashboard. Shows quick counts so the user has
    an at-a-glance view of their workload as soon as they land,
    plus a fast way to drop in a new task without digging for it.
    """
    template_name = "todo/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_tasks"] = Task.objects.count()
        context["pending_tasks"] = Task.objects.filter(
            status=Task.Status.PENDING
        ).count()
        context["completed_tasks"] = Task.objects.filter(
            status=Task.Status.COMPLETED
        ).count()
        context["total_categories"] = Category.objects.count()
        context["upcoming_tasks"] = (
            Task.objects.exclude(status=Task.Status.COMPLETED)
            .exclude(deadline__isnull=True)
            .order_by("deadline")[:5]
        )
        return context


# ----------------------------------------------------------------
# Shared bits for the create/edit pages. One template renders all
# of them — a title, a cancel link, and whatever fields the form
# class defines — so a new field on a model doesn't need a new
# template to go with it.
# ----------------------------------------------------------------

class FormPageMixin:
    template_name = "todo/form_page.html"
    form_title = "Save"
    submit_label = "Save"
    form_hint = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = self.form_title
        context["submit_label"] = self.submit_label
        context["form_hint"] = self.form_hint
        context["cancel_url"] = self.get_cancel_url()
        return context

    def get_cancel_url(self):
        return reverse("home")


class DeletePageMixin:
    template_name = "todo/confirm_delete.html"
    object_label = "this item"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_label"] = self.get_object_label()
        context["cancel_url"] = self.get_cancel_url()
        return context

    def get_object_label(self):
        return self.object_label

    def get_cancel_url(self):
        return reverse("home")


# ----------------------------------------------------------------
# Task
# ----------------------------------------------------------------

class TaskListView(ListView):
    model = Task
    context_object_name = "tasks"
    template_name = "todo/task_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related("category", "priority")
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )
        status = self.request.GET.get("status")
        if status in dict(Task.Status.choices):
            qs = qs.filter(status=status)
        return qs

    def get_ordering(self):
        allowed = [
            "title", "-title",
            "deadline", "-deadline",
            "priority__name", "-priority__name",
            "category__name", "-category__name",
        ]
        sort_by = self.request.GET.get("sort_by")
        if sort_by in allowed:
            return sort_by
        return "-created_at"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        context["status"] = self.request.GET.get("status", "")
        return context


class TaskDetailView(DetailView):
    model = Task
    template_name = "todo/task_detail.html"
    context_object_name = "task"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subtasks"] = self.object.subtasks.all().order_by("title")
        context["notes"] = self.object.notes.all().order_by("-created_at")
        context["subtask_form"] = SubTaskForm(initial={
            "parent_task": self.object.pk,
            "status": SubTask.Status.PENDING,
        })
        context["subtask_form"].fields["parent_task"].widget = forms.HiddenInput()
        context["subtask_form"].fields["status"].widget = forms.HiddenInput()
        context["note_form"] = NoteForm(initial={"task": self.object.pk})
        context["note_form"].fields["task"].widget = forms.HiddenInput()
        return context


class TaskCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = Task
    form_class = TaskForm
    form_title = "New task"
    submit_label = "Add task"
    form_hint = "Plant something new on your list."
    success_message = '"%(title)s" was added to your tasks.'

    def get_success_url(self):
        next_url = self.request.POST.get("next")
        if next_url and next_url.startswith("/"):
            return next_url
        return reverse("task-detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("task-list")


class TaskUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Task
    form_class = TaskForm
    form_title = "Edit task"
    submit_label = "Save changes"
    success_message = '"%(title)s" was updated.'

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.pk])


class TaskDeleteView(DeletePageMixin, DeleteView):
    model = Task

    def get_object_label(self):
        task = self.get_object()
        extras = []
        if task.subtasks.exists():
            extras.append(f"{task.subtasks.count()} subtask{'s' if task.subtasks.count() != 1 else ''}")
        if task.notes.exists():
            extras.append(f"{task.notes.count()} note{'s' if task.notes.count() != 1 else ''}")
        label = f'the task "{task.title}"'
        if extras:
            label += f" — this also removes its {' and '.join(extras)}"
        return label

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.pk])

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.title}" was deleted.')
        return reverse("task-list")


@require_POST
def toggle_task_status(request, pk):
    """Click-to-cycle: Pending -> In Progress -> Completed -> Pending."""
    task = get_object_or_404(Task, pk=pk)
    order = [Task.Status.PENDING, Task.Status.IN_PROGRESS, Task.Status.COMPLETED]
    current = order.index(task.status) if task.status in order else 0
    task.status = order[(current + 1) % len(order)]
    task.save(update_fields=["status", "updated_at"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": task.status,
            "slug": slugify(task.status),
            "label": task.get_status_display(),
        })

    messages.success(request, f'"{task.title}" is now {task.status}.')
    return redirect(request.META.get("HTTP_REFERER") or reverse("task-list"))


# ----------------------------------------------------------------
# SubTask
# ----------------------------------------------------------------

class SubTaskListView(ListView):
    model = SubTask
    context_object_name = "subtasks"
    template_name = "todo/subtask_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related("parent_task")
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(
                Q(title__icontains=query) | Q(parent_task__title__icontains=query)
            )
        return qs

    def get_ordering(self):
        allowed = [
            "title", "-title",
            "parent_task__title", "-parent_task__title",
            "status", "-status",
        ]
        sort_by = self.request.GET.get("sort_by")
        if sort_by in allowed:
            return sort_by
        return "title"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


class SubTaskCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = SubTask
    form_class = SubTaskForm
    form_title = "New subtask"
    submit_label = "Add subtask"
    success_message = '"%(title)s" was added.'

    def get_initial(self):
        initial = super().get_initial()
        task_id = self.request.GET.get("task")
        if task_id:
            initial["parent_task"] = task_id
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.GET.get("task"):
            form.fields["parent_task"].widget = forms.HiddenInput()
        return form

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])

    def get_cancel_url(self):
        task_id = self.request.GET.get("task")
        if task_id:
            return reverse("task-detail", args=[task_id])
        return reverse("subtask-list")


class SubTaskUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = SubTask
    form_class = SubTaskForm
    form_title = "Edit subtask"
    submit_label = "Save changes"
    success_message = '"%(title)s" was updated.'

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])


class SubTaskDeleteView(DeletePageMixin, DeleteView):
    model = SubTask

    def get_object_label(self):
        return f'the subtask "{self.get_object().title}"'

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.title}" was deleted.')
        return reverse("task-detail", args=[self.object.parent_task_id])


@require_POST
def toggle_subtask_status(request, pk):
    subtask = get_object_or_404(SubTask, pk=pk)
    order = [SubTask.Status.PENDING, SubTask.Status.IN_PROGRESS, SubTask.Status.COMPLETED]
    current = order.index(subtask.status) if subtask.status in order else 0
    subtask.status = order[(current + 1) % len(order)]
    subtask.save(update_fields=["status", "updated_at"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": subtask.status,
            "slug": slugify(subtask.status),
            "label": subtask.status,
        })

    messages.success(request, f'"{subtask.title}" is now {subtask.status}.')
    return redirect(request.META.get("HTTP_REFERER") or reverse("subtask-list"))


# ----------------------------------------------------------------
# Note
# ----------------------------------------------------------------

class NoteListView(ListView):
    model = Note
    context_object_name = "notes"
    template_name = "todo/note_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related("task")
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(
                Q(content__icontains=query) | Q(task__title__icontains=query)
            )
        return qs

    def get_ordering(self):
        allowed = ["created_at", "-created_at", "task__title", "-task__title"]
        sort_by = self.request.GET.get("sort_by")
        if sort_by in allowed:
            return sort_by
        return "-created_at"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


class NoteCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = Note
    form_class = NoteForm
    form_title = "New note"
    submit_label = "Add note"
    success_message = "Note added."

    def get_initial(self):
        initial = super().get_initial()
        task_id = self.request.GET.get("task")
        if task_id:
            initial["task"] = task_id
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.GET.get("task"):
            form.fields["task"].widget = forms.HiddenInput()
        return form

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.task_id])

    def get_cancel_url(self):
        task_id = self.request.GET.get("task")
        if task_id:
            return reverse("task-detail", args=[task_id])
        return reverse("note-list")


class NoteUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Note
    form_class = NoteForm
    form_title = "Edit note"
    submit_label = "Save changes"
    success_message = "Note updated."

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.task_id])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.task_id])


class NoteDeleteView(DeletePageMixin, DeleteView):
    model = Note
    object_label = "this note"

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.task_id])

    def get_success_url(self):
        messages.success(self.request, "Note deleted.")
        return reverse("task-detail", args=[self.object.task_id])


# ----------------------------------------------------------------
# Category
# ----------------------------------------------------------------

class CategoryListView(ListView):
    model = Category
    context_object_name = "categories"
    template_name = "todo/category_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(Q(name__icontains=query))
        return qs

    def get_ordering(self):
        allowed = ["name", "-name"]
        sort_by = self.request.GET.get("sort_by")
        if sort_by in allowed:
            return sort_by
        return "name"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


class CategoryCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    form_title = "New category"
    submit_label = "Add category"
    success_message = '"%(name)s" was added.'
    success_url = reverse_lazy("category-list")

    def get_cancel_url(self):
        return reverse("category-list")


class CategoryUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    form_title = "Edit category"
    submit_label = "Save changes"
    success_message = '"%(name)s" was updated.'
    success_url = reverse_lazy("category-list")

    def get_cancel_url(self):
        return reverse("category-list")


class CategoryDeleteView(DeletePageMixin, DeleteView):
    model = Category
    success_url = reverse_lazy("category-list")

    def get_object_label(self):
        category = self.get_object()
        count = category.tasks.count()
        label = f'the category "{category.name}"'
        if count:
            label += f" — {count} task{'s' if count != 1 else ''} will keep their other details, just without this category"
        return label

    def get_cancel_url(self):
        return reverse("category-list")

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.name}" was deleted.')
        return reverse("category-list")


# ----------------------------------------------------------------
# Priority
# ----------------------------------------------------------------

class PriorityListView(ListView):
    model = Priority
    context_object_name = "priorities"
    template_name = "todo/priority_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(Q(name__icontains=query))
        return qs

    def get_ordering(self):
        allowed = ["name", "-name"]
        sort_by = self.request.GET.get("sort_by")
        if sort_by in allowed:
            return sort_by
        return "name"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "")
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


class PriorityCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = Priority
    form_class = PriorityForm
    form_title = "New priority"
    submit_label = "Add priority"
    success_message = '"%(name)s" was added.'
    success_url = reverse_lazy("priority-list")

    def get_cancel_url(self):
        return reverse("priority-list")


class PriorityUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Priority
    form_class = PriorityForm
    form_title = "Edit priority"
    submit_label = "Save changes"
    success_message = '"%(name)s" was updated.'
    success_url = reverse_lazy("priority-list")

    def get_cancel_url(self):
        return reverse("priority-list")


class PriorityDeleteView(DeletePageMixin, DeleteView):
    model = Priority
    success_url = reverse_lazy("priority-list")

    def get_object_label(self):
        priority = self.get_object()
        count = priority.tasks.count()
        label = f'the priority "{priority.name}"'
        if count:
            label += f" — {count} task{'s' if count != 1 else ''} will keep their other details, just without this priority"
        return label

    def get_cancel_url(self):
        return reverse("priority-list")

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.name}" was deleted.')
        return reverse("priority-list")

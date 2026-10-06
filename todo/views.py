import csv
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Case, Count, F, IntegerField, Q, When
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView,
)

from .forms import (
    CategoryForm, DeleteAccountForm, NoteForm, PriorityForm, ProfileForm,
    SubTaskForm, TaskForm,
)
from .models import Category, Note, Priority, Profile, SubTask, Task
from .stats import ensure_profile, level_for, progress_summary, today_progress, xp_for


def safe_url(request, candidate, fallback):
    """Only ever bounce people to a page on this site."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------
# Home
# ----------------------------------------------------------------

def _greeting(name):
    hour = timezone.localtime().hour
    if hour < 5:
        return f"Still up, {name}?"
    if hour < 12:
        return f"Good morning, {name}."
    if hour < 18:
        return f"Good afternoon, {name}."
    return f"Good evening, {name}."


def _hero_line(summary):
    today = summary["today"]
    if summary["total"] == 0:
        return "Your list is empty. Add your first task below."
    if summary["overdue"]:
        n = summary["overdue"]
        return f"{n} task{'s are' if n != 1 else ' is'} overdue."
    if today["hit"]:
        return "You've reached today's goal."
    if today["done"]:
        return f"{today['left']} more to reach today's goal of {today['goal']}."
    if summary["open"] == 0:
        return "Everything on your list is done."
    return f"You have {summary['open']} task{'s' if summary['open'] != 1 else ''} open."


class HomePageView(TemplateView):
    """Dashboard: today's goal, counts, and what's due next."""
    template_name = "todo/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = ensure_profile(user)
        summary = progress_summary(user)
        my_tasks = Task.objects.filter(owner=user)

        context.update({
            "summary": summary,
            "greeting": _greeting(profile.user.first_name or user.get_username()),
            "hero_line": _hero_line(summary),
            "upcoming_tasks": (
                my_tasks.exclude(status=Task.Status.COMPLETED)
                .exclude(deadline__isnull=True)
                .select_related("priority")
                .order_by("deadline")[:5]
            ),
        })
        return context


# ----------------------------------------------------------------
# Shared view pieces
# ----------------------------------------------------------------

class UserFormMixin:
    """Hands the logged-in user to the form so it can limit its dropdowns."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


# one template for all create/edit forms, one for all delete confirmations

class FormPageMixin(UserFormMixin):
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


def _next_status(obj):
    order = [obj.Status.PENDING, obj.Status.IN_PROGRESS, obj.Status.COMPLETED]
    current = order.index(obj.status) if obj.status in order else 0
    return order[(current + 1) % len(order)]


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


# ----------------------------------------------------------------
# Task
# ----------------------------------------------------------------

PRIORITY_RANK = Case(
    When(priority__name__iexact="critical", then=0),
    When(priority__name__iexact="high", then=1),
    When(priority__name__iexact="medium", then=2),
    When(priority__name__iexact="low", then=3),
    When(priority__name__iexact="optional", then=4),
    default=5,
    output_field=IntegerField(),
)

TASK_SORTS = {
    "": lambda: [F("created_at").desc()],
    "deadline": lambda: [F("deadline").asc(nulls_last=True)],
    "-deadline": lambda: [F("deadline").desc(nulls_last=True)],
    "title": lambda: [F("title").asc()],
    "-title": lambda: [F("title").desc()],
    "priority": lambda: [PRIORITY_RANK.asc(), F("deadline").asc(nulls_last=True)],
    "category": lambda: [F("category__name").asc(nulls_last=True)],
}


def filtered_tasks(request):
    """The current user's tasks with the search/filter/sort from the URL
    applied. The list page and the CSV export both use this."""
    user = request.user
    params = request.GET
    qs = (
        Task.objects.filter(owner=user)
        .select_related("category", "priority")
        .annotate(
            n_sub=Count("subtasks", distinct=True),
            n_sub_done=Count(
                "subtasks",
                filter=Q(subtasks__status=SubTask.Status.COMPLETED),
                distinct=True,
            ),
            n_notes=Count("notes", distinct=True),
        )
    )

    query = params.get("q", "").strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))

    status = params.get("status", "")
    if status in dict(Task.Status.choices):
        qs = qs.filter(status=status)

    category_id = _int_or_none(params.get("category"))
    if category_id is not None:
        qs = qs.filter(category_id=category_id)

    priority_id = _int_or_none(params.get("priority"))
    if priority_id is not None:
        qs = qs.filter(priority_id=priority_id)

    due = params.get("due", "")
    now = timezone.now()
    if due == "overdue":
        qs = qs.exclude(status=Task.Status.COMPLETED).filter(deadline__lt=now)
    elif due == "today":
        start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = qs.filter(deadline__gte=start, deadline__lt=start + timedelta(days=1))
    elif due == "week":
        qs = qs.exclude(status=Task.Status.COMPLETED).filter(
            deadline__gte=now, deadline__lt=now + timedelta(days=7)
        )

    sort_by = params.get("sort_by", "")
    order = TASK_SORTS.get(sort_by, TASK_SORTS[""])()
    return qs.order_by(*order, "-pk")


class TaskListView(ListView):
    context_object_name = "tasks"
    template_name = "todo/task_list.html"
    paginate_by = 9

    def get_queryset(self):
        return filtered_tasks(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        user = self.request.user
        context.update({
            "query": params.get("q", "").strip(),
            "sort_by": params.get("sort_by", ""),
            "status": params.get("status", ""),
            "due": params.get("due", ""),
            "category_id": _int_or_none(params.get("category")),
            "priority_id": _int_or_none(params.get("priority")),
            "categories": Category.objects.visible_to(user).order_by("name"),
            "priorities": Priority.objects.visible_to(user).order_by("name"),
            "status_choices": Task.Status.choices,
            "is_filtered": any(
                params.get(k) for k in ("q", "status", "category", "priority", "due", "sort_by")
            ),
        })
        return context


def _csv_safe(value):
    """Stop a spreadsheet from running a cell that starts like a formula."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def export_tasks_csv(request):
    """Download whatever the task list is currently showing as a spreadsheet."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.localdate().isoformat()
    response["Content-Disposition"] = f'attachment; filename="hangarin-tasks-{stamp}.csv"'
    response.write("\ufeff")  # so Excel reads the accents and emoji right

    writer = csv.writer(response)
    writer.writerow([
        "Title", "Description", "Status", "Priority", "Category",
        "Deadline", "Created", "Completed", "Subtasks done", "Subtasks total", "Notes",
    ])

    def fmt(dt):
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M") if dt else ""

    for task in filtered_tasks(request).iterator():
        writer.writerow([
            _csv_safe(task.title),
            _csv_safe(task.description),
            task.status,
            _csv_safe(task.priority.name if task.priority else ""),
            _csv_safe(task.category.name if task.category else ""),
            fmt(task.deadline),
            fmt(task.created_at),
            fmt(task.completed_at),
            task.n_sub_done,
            task.n_sub,
            task.n_notes,
        ])
    return response


class TaskDetailView(DetailView):
    template_name = "todo/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user).select_related("category", "priority")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        subtasks = list(self.object.subtasks.order_by("created_at", "pk"))
        done = sum(1 for s in subtasks if s.status == SubTask.Status.COMPLETED)

        context["subtasks"] = subtasks
        context["subtask_count"] = len(subtasks)
        context["subtasks_done"] = done
        context["subtask_pct"] = round(done * 100 / len(subtasks)) if subtasks else 0
        context["notes"] = self.object.notes.order_by("-created_at")

        subtask_form = SubTaskForm(
            user=user,
            initial={"parent_task": self.object.pk, "status": SubTask.Status.PENDING},
        )
        subtask_form.fields["parent_task"].widget = forms.HiddenInput()
        subtask_form.fields["status"].widget = forms.HiddenInput()
        note_form = NoteForm(user=user, initial={"task": self.object.pk})
        note_form.fields["task"].widget = forms.HiddenInput()
        context["subtask_form"] = subtask_form
        context["note_form"] = note_form
        return context


class TaskCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = Task
    form_class = TaskForm
    form_title = "New task"
    submit_label = "Add task"
    form_hint = "What do you need to get done?"
    success_message = '"%(title)s" was added to your tasks.'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        fallback = reverse("task-detail", args=[self.object.pk])
        return safe_url(self.request, self.request.POST.get("next"), fallback)

    def get_cancel_url(self):
        return reverse("task-list")


class TaskUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Task
    form_class = TaskForm
    form_title = "Edit task"
    submit_label = "Save changes"
    success_message = '"%(title)s" was updated.'

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.pk])


class TaskDeleteView(DeletePageMixin, DeleteView):
    model = Task

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def get_object_label(self):
        task = self.object
        extras = []
        subs = task.subtasks.count()
        notes = task.notes.count()
        if subs:
            extras.append(f"{subs} subtask{'s' if subs != 1 else ''}")
        if notes:
            extras.append(f"{notes} note{'s' if notes != 1 else ''}")
        label = f'the task "{task.title}"'
        if extras:
            label += f" and its {' and '.join(extras)}"
        return label

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.pk])

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.title}" was deleted.')
        return reverse("task-list")


def _toggle_payload(request, obj, parent=None, level_before=None):
    payload = {
        "status": obj.status,
        "slug": slugify(obj.status),
        "label": obj.status,
        "celebrate": obj.status == obj.Status.COMPLETED,
    }
    if payload["celebrate"]:
        today = today_progress(request.user)
        payload["goal_hit"] = today["done"] == today["goal"]
        payload["goal"] = today["goal"]
        if level_before is not None:
            now = level_for(xp_for(request.user))
            if now["level"] > level_before:
                payload["level_up"] = {"level": now["level"], "title": now["title"]}
    if parent is not None:
        subs = parent.subtasks.all()
        total = subs.count()
        done = subs.filter(status=SubTask.Status.COMPLETED).count()
        payload["parent"] = parent.pk
        payload["progress"] = {
            "done": done,
            "total": total,
            "pct": round(done * 100 / total) if total else 0,
        }
    return payload


@require_POST
def toggle_task_status(request, pk):
    """Click to cycle: Pending -> In Progress -> Completed -> Pending."""
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    level_before = level_for(xp_for(request.user))["level"]
    task.status = _next_status(task)
    task.save(update_fields=["status", "updated_at"])

    if _wants_json(request):
        return JsonResponse(_toggle_payload(request, task, level_before=level_before))

    messages.success(request, f'"{task.title}" is now {task.status}.')
    return redirect(safe_url(request, request.META.get("HTTP_REFERER"), reverse("task-list")))


# ----------------------------------------------------------------
# SubTask
# ----------------------------------------------------------------

SUBTASK_SORTS = {
    "title": ["title"],
    "-title": ["-title"],
    "parent_task__title": ["parent_task__title", "title"],
    "status": ["status", "title"],
}


class SubTaskListView(ListView):
    context_object_name = "subtasks"
    template_name = "todo/subtask_list.html"
    paginate_by = 12

    def get_queryset(self):
        qs = SubTask.objects.select_related("parent_task").filter(
            parent_task__owner=self.request.user
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(title__icontains=query) | Q(parent_task__title__icontains=query)
            )
        status = self.request.GET.get("status", "")
        if status in dict(SubTask.Status.choices):
            qs = qs.filter(status=status)
        order = SUBTASK_SORTS.get(self.request.GET.get("sort_by", ""), ["title"])
        return qs.order_by(*order, "pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["sort_by"] = self.request.GET.get("sort_by", "")
        context["status"] = self.request.GET.get("status", "")
        context["status_choices"] = SubTask.Status.choices
        return context


class SubTaskCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    model = SubTask
    form_class = SubTaskForm
    form_title = "New subtask"
    submit_label = "Add subtask"
    success_message = '"%(title)s" was added.'

    def get_initial(self):
        initial = super().get_initial()
        task_id = _int_or_none(self.request.GET.get("task"))
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
        task_id = _int_or_none(self.request.GET.get("task"))
        if task_id:
            return reverse("task-detail", args=[task_id])
        return reverse("subtask-list")


class SubTaskUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = SubTask
    form_class = SubTaskForm
    form_title = "Edit subtask"
    submit_label = "Save changes"
    success_message = '"%(title)s" was updated.'

    def get_queryset(self):
        return SubTask.objects.filter(parent_task__owner=self.request.user)

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])


class SubTaskDeleteView(DeletePageMixin, DeleteView):
    model = SubTask

    def get_queryset(self):
        return SubTask.objects.filter(parent_task__owner=self.request.user)

    def get_object_label(self):
        return f'the subtask "{self.object.title}"'

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.parent_task_id])

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.title}" was deleted.')
        return reverse("task-detail", args=[self.object.parent_task_id])


@require_POST
def toggle_subtask_status(request, pk):
    subtask = get_object_or_404(
        SubTask.objects.select_related("parent_task"),
        pk=pk, parent_task__owner=request.user,
    )
    level_before = level_for(xp_for(request.user))["level"]
    subtask.status = _next_status(subtask)
    subtask.save(update_fields=["status", "updated_at"])

    if _wants_json(request):
        return JsonResponse(_toggle_payload(
            request, subtask, parent=subtask.parent_task, level_before=level_before,
        ))

    messages.success(request, f'"{subtask.title}" is now {subtask.status}.')
    return redirect(safe_url(request, request.META.get("HTTP_REFERER"), reverse("subtask-list")))


# ----------------------------------------------------------------
# Note
# ----------------------------------------------------------------

NOTE_SORTS = {
    "created_at": ["created_at"],
    "-created_at": ["-created_at"],
    "task__title": ["task__title", "-created_at"],
}


class NoteListView(ListView):
    context_object_name = "notes"
    template_name = "todo/note_list.html"
    paginate_by = 12

    def get_queryset(self):
        qs = Note.objects.select_related("task").filter(task__owner=self.request.user)
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(content__icontains=query) | Q(task__title__icontains=query))
        order = NOTE_SORTS.get(self.request.GET.get("sort_by", ""), ["-created_at"])
        return qs.order_by(*order, "-pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
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
        task_id = _int_or_none(self.request.GET.get("task"))
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
        task_id = _int_or_none(self.request.GET.get("task"))
        if task_id:
            return reverse("task-detail", args=[task_id])
        return reverse("note-list")


class NoteUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    model = Note
    form_class = NoteForm
    form_title = "Edit note"
    submit_label = "Save changes"
    success_message = "Note updated."

    def get_queryset(self):
        return Note.objects.filter(task__owner=self.request.user)

    def get_success_url(self):
        return reverse("task-detail", args=[self.object.task_id])

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.task_id])


class NoteDeleteView(DeletePageMixin, DeleteView):
    model = Note
    object_label = "this note"

    def get_queryset(self):
        return Note.objects.filter(task__owner=self.request.user)

    def get_cancel_url(self):
        return reverse("task-detail", args=[self.object.task_id])

    def get_success_url(self):
        messages.success(self.request, "Note deleted.")
        return reverse("task-detail", args=[self.object.task_id])


# ----------------------------------------------------------------
# Category and Priority
#
# Both work the same way: the shared defaults (no owner) can be picked by
# everyone but only changed in the admin, and anything a person adds is
# theirs alone.
# ----------------------------------------------------------------

class _TagListView(ListView):
    """Base for the Category and Priority list pages."""
    model = None
    paginate_by = 12

    def get_queryset(self):
        user = self.request.user
        qs = (
            self.model.objects.visible_to(user)
            .annotate(n_tasks=Count("tasks", filter=Q(tasks__owner=user)))
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(name__icontains=query)
        order = "-name" if self.request.GET.get("sort_by") == "-name" else "name"
        return qs.order_by(order, "pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["sort_by"] = self.request.GET.get("sort_by", "")
        return context


class _TagCreateView(SuccessMessageMixin, FormPageMixin, CreateView):
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class _TagUpdateView(SuccessMessageMixin, FormPageMixin, UpdateView):
    def get_queryset(self):
        # shared defaults are not in here, so they can't be edited
        return self.model.objects.filter(owner=self.request.user)


class _TagDeleteView(DeletePageMixin, DeleteView):
    noun = "item"
    list_url_name = ""

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)

    def get_object_label(self):
        obj = self.object
        count = obj.tasks.filter(owner=self.request.user).count()
        label = f'the {self.noun} "{obj.name}"'
        if count:
            label += (
                f". {count} task{'s' if count != 1 else ''} will keep "
                f"their other details, just without this {self.noun}"
            )
        return label

    def get_cancel_url(self):
        return reverse(self.list_url_name)

    def get_success_url(self):
        messages.success(self.request, f'"{self.object.name}" was deleted.')
        return reverse(self.list_url_name)


class CategoryListView(_TagListView):
    model = Category
    context_object_name = "categories"
    template_name = "todo/category_list.html"


class CategoryCreateView(_TagCreateView):
    model = Category
    form_class = CategoryForm
    form_title = "New category"
    submit_label = "Add category"
    success_message = '"%(name)s" was added.'
    success_url = reverse_lazy("category-list")

    def get_cancel_url(self):
        return reverse("category-list")


class CategoryUpdateView(_TagUpdateView):
    model = Category
    form_class = CategoryForm
    form_title = "Edit category"
    submit_label = "Save changes"
    success_message = '"%(name)s" was updated.'
    success_url = reverse_lazy("category-list")

    def get_cancel_url(self):
        return reverse("category-list")


class CategoryDeleteView(_TagDeleteView):
    model = Category
    noun = "category"
    list_url_name = "category-list"


class PriorityListView(_TagListView):
    model = Priority
    context_object_name = "priorities"
    template_name = "todo/priority_list.html"


class PriorityCreateView(_TagCreateView):
    model = Priority
    form_class = PriorityForm
    form_title = "New priority"
    submit_label = "Add priority"
    success_message = '"%(name)s" was added.'
    success_url = reverse_lazy("priority-list")

    def get_cancel_url(self):
        return reverse("priority-list")


class PriorityUpdateView(_TagUpdateView):
    model = Priority
    form_class = PriorityForm
    form_title = "Edit priority"
    submit_label = "Save changes"
    success_message = '"%(name)s" was updated.'
    success_url = reverse_lazy("priority-list")

    def get_cancel_url(self):
        return reverse("priority-list")


class PriorityDeleteView(_TagDeleteView):
    model = Priority
    noun = "priority"
    list_url_name = "priority-list"


# ----------------------------------------------------------------
# Profile
# ----------------------------------------------------------------

class ProfileView(TemplateView):
    """The progress page: level, streak, weekly chart, badges."""
    template_name = "todo/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = ensure_profile(self.request.user)
        context["summary"] = progress_summary(self.request.user)
        return context


class ProfileEditView(SuccessMessageMixin, UpdateView):
    form_class = ProfileForm
    template_name = "todo/profile_edit.html"
    success_url = reverse_lazy("profile")
    success_message = "Your profile is saved."

    def get_object(self, queryset=None):
        return ensure_profile(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = self.object
        return context


class AccountDeleteView(FormView):
    """Lets someone remove their own account and everything in it."""
    template_name = "todo/account_delete.html"
    form_class = DeleteAccountForm
    success_url = reverse_lazy("account_login")

    def dispatch(self, request, *args, **kwargs):
        # An admin deleting themselves by accident could lock the whole site
        # out of its own admin, so that has to be done deliberately in /admin.
        if request.user.is_authenticated and request.user.is_superuser:
            messages.error(
                request,
                "Admin accounts can't be deleted from here. Use the admin site if you really mean it.",
            )
            return redirect("profile-edit")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update({
            "n_tasks": Task.objects.filter(owner=user).count(),
            "n_subtasks": SubTask.objects.filter(parent_task__owner=user).count(),
            "n_notes": Note.objects.filter(task__owner=user).count(),
        })
        return context

    def form_valid(self, form):
        user = self.request.user
        profile = ensure_profile(user)
        if profile.avatar:
            profile.avatar.delete(save=False)  # don't leave the picture behind
        logout(self.request)
        user.delete()
        messages.success(self.request, "Your account and everything in it has been deleted.")
        return super().form_valid(form)


@require_POST
def set_theme(request):
    """Called by the light/dark button so the choice follows you across devices."""
    choice = request.POST.get("theme", "")
    if choice not in dict(Profile.Theme.choices):
        return JsonResponse({"error": "unknown theme"}, status=400)
    profile = ensure_profile(request.user)
    profile.theme = choice
    profile.save(update_fields=["theme", "updated_at"])
    return JsonResponse({"theme": choice})


# ----------------------------------------------------------------
# Offline page (the service worker falls back to this)
# ----------------------------------------------------------------

def offline_page(request):
    # Plain on purpose: no messages, no csrf token, nothing about the user.
    # The service worker keeps a copy in the browser, and pulling it in must
    # not use up someone's pending "saved" message either.
    return _plain_page("offline.html", 200)


# ----------------------------------------------------------------
# Error pages
# ----------------------------------------------------------------

def _plain_page(template, status):
    # No request passed on purpose, so no context processors (and no database
    # lookups) run. These pages have to work even when everything else is down.
    return HttpResponse(render_to_string(template), status=status)


def not_found(request, exception=None):
    return _plain_page("404.html", 404)


def forbidden(request, exception=None):
    return _plain_page("403.html", 403)


def server_error(request):
    return _plain_page("500.html", 500)

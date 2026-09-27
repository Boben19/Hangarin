from django.db.models import Q
from django.views.generic import ListView, TemplateView

from .models import Category, Note, Priority, SubTask, Task


class HomePageView(TemplateView):
    """
    Landing page / dashboard. Shows quick counts so the user has
    an at-a-glance view of their workload as soon as they land.
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
        return context


class TaskListView(ListView):
    model = Task
    context_object_name = "tasks"
    template_name = "todo/task_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )
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
        return context


class SubTaskListView(ListView):
    model = SubTask
    context_object_name = "subtasks"
    template_name = "todo/subtask_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
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


class NoteListView(ListView):
    model = Note
    context_object_name = "notes"
    template_name = "todo/note_list.html"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
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
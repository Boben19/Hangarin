from django.contrib import admin

from .models import Category, Note, Priority, Profile, SubTask, Task

admin.site.site_header = "Hangarin Admin"
admin.site.site_title = "Hangarin"
admin.site.index_title = "Dashboard"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "deadline", "priority", "category", "owner")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description")
    readonly_fields = ("completed_at",)

    def save_model(self, request, obj, form, change):
        # a task made in the admin with no owner would be invisible to
        # everybody on the site, so default it to whoever is creating it
        if obj.owner_id is None:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(SubTask)
class SubTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "parent_task_name")
    list_filter = ("status",)
    search_fields = ("title",)
    list_select_related = ("parent_task",)

    @admin.display(description="Parent Task")
    def parent_task_name(self, obj):
        return obj.parent_task.title


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Priority)
class PriorityAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("task", "content", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content",)
    list_select_related = ("task",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_goal", "theme", "created_at")
    list_filter = ("theme",)
    search_fields = ("user__username", "user__email")

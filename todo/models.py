from django.db import models


class BaseModel(models.Model):
    """
    Abstract base class that all Hangarin models inherit from.
    Adds created_at / updated_at timestamps so we don't repeat
    ourselves in every model below.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Priority(BaseModel):
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Priority"
        verbose_name_plural = "Priorities"

    def __str__(self):
        return self.name


class Category(BaseModel):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Task(BaseModel):

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        IN_PROGRESS = "In Progress", "In Progress"
        COMPLETED = "Completed", "Completed"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    priority = models.ForeignKey(
        Priority,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return self.title


class SubTask(BaseModel):

    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        IN_PROGRESS = "In Progress", "In Progress"
        COMPLETED = "Completed", "Completed"

    parent_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="subtasks",
    )
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        verbose_name = "SubTask"
        verbose_name_plural = "SubTasks"

    def __str__(self):
        return self.title

    @property
    def parent_task_name(self):
        return self.parent_task.title


class Note(BaseModel):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField()

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"

    def __str__(self):
        return f"Note for {self.task.title}"

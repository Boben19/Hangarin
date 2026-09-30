from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base that every Hangarin model inherits from. It just adds the
    created_at / updated_at timestamps so they aren't repeated everywhere.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Shared defaults (no owner) plus whatever this user made themselves."""
        return self.filter(Q(owner__isnull=True) | Q(owner=user))


class Priority(BaseModel):
    name = models.CharField(max_length=50)
    # empty owner = a shared default that everybody can pick but nobody but
    # an admin can change. Otherwise it belongs to one person.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="priorities",
    )

    objects = OwnedQuerySet.as_manager()

    class Meta:
        verbose_name = "Priority"
        verbose_name_plural = "Priorities"

    def __str__(self):
        return self.name

    @property
    def is_shared(self):
        return self.owner_id is None


class Category(BaseModel):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="categories",
    )

    objects = OwnedQuerySet.as_manager()

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    @property
    def is_shared(self):
        return self.owner_id is None


class CompletionMixin:
    """
    Keeps completed_at in step with status, whichever way the status changes
    (toggle button, edit form, admin). That timestamp is what the streaks and
    weekly charts on the profile page are built from.
    """

    def _sync_completed_at(self):
        done = self.status == "Completed"
        if done and self.completed_at is None:
            self.completed_at = timezone.now()
            return True
        if not done and self.completed_at is not None:
            self.completed_at = None
            return True
        return False

    def save(self, *args, **kwargs):
        changed = self._sync_completed_at()
        update_fields = kwargs.get("update_fields")
        if changed and update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"completed_at"}
        super().save(*args, **kwargs)


class Task(CompletionMixin, BaseModel):

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
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tasks",
        help_text="Whoever's list this belongs to.",
    )

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "deadline"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return (
            self.deadline is not None
            and self.status != self.Status.COMPLETED
            and self.deadline < timezone.now()
        )

    @property
    def is_due_today(self):
        if self.deadline is None or self.status == self.Status.COMPLETED:
            return False
        return timezone.localtime(self.deadline).date() == timezone.localdate()


class SubTask(CompletionMixin, BaseModel):

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
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

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


class Profile(BaseModel):
    """Extra per-person settings that don't belong on the built-in User."""

    class Theme(models.TextChoices):
        SYSTEM = "system", "Match my device"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    bio = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    daily_goal = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="How many tasks or subtasks you'd like to finish each day.",
    )
    theme = models.CharField(
        max_length=10,
        choices=Theme.choices,
        default=Theme.SYSTEM,
    )

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        return f"{self.user}'s profile"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.get_username()

    @property
    def initial(self):
        return (self.display_name[:1] or "?").upper()

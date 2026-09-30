from django.conf import settings
from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Task = apps.get_model("todo", "Task")
    SubTask = apps.get_model("todo", "SubTask")
    Profile = apps.get_model("todo", "Profile")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    # things that were finished before we started recording when: use the last
    # time they were touched, which is the closest honest answer we have
    Task.objects.filter(status="Completed", completed_at__isnull=True).update(
        completed_at=F("updated_at")
    )
    SubTask.objects.filter(status="Completed", completed_at__isnull=True).update(
        completed_at=F("updated_at")
    )

    # new accounts start with something to pick from instead of empty dropdowns
    Priority = apps.get_model("todo", "Priority")
    Category = apps.get_model("todo", "Category")
    for name in ("Critical", "High", "Medium", "Low", "Optional"):
        Priority.objects.get_or_create(name=name, owner=None)
    for name in ("Work", "School", "Personal", "Finance", "Projects"):
        Category.objects.get_or_create(name=name, owner=None)

    have_profile = set(Profile.objects.values_list("user_id", flat=True))
    Profile.objects.bulk_create(
        [Profile(user_id=uid) for uid in User.objects.values_list("id", flat=True)
         if uid not in have_profile]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("todo", "0003_profiles_ownership_completion"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

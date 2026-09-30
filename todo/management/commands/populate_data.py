import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from faker import Faker

from todo.models import Category, Note, Priority, SubTask, Task

fake = Faker()

PRIORITY_NAMES = ["High", "Medium", "Low", "Critical", "Optional"]
CATEGORY_NAMES = ["Work", "School", "Personal", "Finance", "Projects"]

STATUS_VALUES = ["Pending", "In Progress", "Completed"]


class Command(BaseCommand):
    help = "Populates the database with Priority/Category records and fake Task, SubTask, and Note data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tasks",
            type=int,
            default=20,
            help="How many Task records to generate (default: 20).",
        )
        parser.add_argument(
            "--subtasks-per-task",
            type=int,
            default=3,
            help="Max SubTasks to generate per Task (default: 3).",
        )
        parser.add_argument(
            "--notes-per-task",
            type=int,
            default=2,
            help="Max Notes to generate per Task (default: 2).",
        )
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Who the generated tasks belong to. Defaults to the first superuser.",
        )

    @staticmethod
    def _shared(model, name):
        """The shared default with this name, made if it isn't there yet.
        Uses first() rather than get_or_create() so a duplicate someone added
        by hand in the admin doesn't crash the command."""
        found = model.objects.filter(name__iexact=name, owner__isnull=True).order_by("pk").first()
        return found or model.objects.create(name=name, owner=None)

    def handle(self, *args, **options):
        User = get_user_model()
        if options["username"]:
            try:
                owner = User.objects.get(username=options["username"])
            except User.DoesNotExist:
                raise CommandError(f'No user named "{options["username"]}". Sign up first.')
        else:
            owner = User.objects.filter(is_superuser=True).order_by("id").first()
            if owner is None:
                raise CommandError(
                    "No user to own the fake data yet. Sign up (or run "
                    "createsuperuser) and pass --username, then try again."
                )

        self.stdout.write("Setting up priorities and categories...")
        # owner=None makes these the shared defaults everybody can pick from
        priorities = [self._shared(Priority, name) for name in PRIORITY_NAMES]
        categories = [self._shared(Category, name) for name in CATEGORY_NAMES]

        task_count = options["tasks"]
        subtasks_per_task = options["subtasks_per_task"]
        notes_per_task = options["notes_per_task"]

        self.stdout.write(f"Generating {task_count} tasks for {owner}...")
        tasks = []
        for _ in range(task_count):
            task = Task.objects.create(
                title=fake.sentence(nb_words=5),
                description=fake.paragraph(nb_sentences=3),
                deadline=timezone.make_aware(fake.date_time_this_month()),
                status=fake.random_element(elements=STATUS_VALUES),
                category=random.choice(categories),
                priority=random.choice(priorities),
                owner=owner,
            )
            tasks.append(task)

        self.stdout.write("Generating subtasks...")
        subtask_total = 0
        for task in tasks:
            for _ in range(random.randint(0, subtasks_per_task)):
                SubTask.objects.create(
                    parent_task=task,
                    title=fake.sentence(nb_words=5),
                    status=fake.random_element(elements=STATUS_VALUES),
                )
                subtask_total += 1

        self.stdout.write("Generating notes...")
        note_total = 0
        for task in tasks:
            for _ in range(random.randint(0, notes_per_task)):
                Note.objects.create(
                    task=task,
                    content=fake.paragraph(nb_sentences=3),
                )
                note_total += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {len(priorities)} priorities, {len(categories)} categories, "
                f"{len(tasks)} tasks, {subtask_total} subtasks, {note_total} notes."
            )
        )

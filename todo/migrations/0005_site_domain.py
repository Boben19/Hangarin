import os

from django.conf import settings
from django.db import migrations

PLACEHOLDER = "example.com"


def _real_domain():
    explicit = os.environ.get("DJANGO_SITE_DOMAIN", "").strip()
    if explicit:
        return explicit
    for host in settings.ALLOWED_HOSTS:
        if host and host not in ("localhost", "127.0.0.1", "[::1]") and not host.startswith("."):
            return host
    return "localhost:8000"


def fix_site_domain(apps, schema_editor):
    """
    Django creates the Site record as "example.com". django-allauth builds the
    links in password-reset and confirmation emails from it, so every one of
    them pointed at example.com. Only the untouched placeholder is replaced,
    so a domain somebody set on purpose is left alone.
    """
    Site = apps.get_model("sites", "Site")
    for site in Site.objects.filter(pk=settings.SITE_ID, domain=PLACEHOLDER):
        site.domain = _real_domain()
        site.name = "Hangarin"
        site.save()


class Migration(migrations.Migration):

    dependencies = [
        ("todo", "0004_backfill_profiles_and_completion"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(fix_site_domain, migrations.RunPython.noop),
    ]

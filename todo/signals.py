from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def make_profile(sender, instance, created, **kwargs):
    # every new account, whether it came from the form, a social login or
    # createsuperuser, gets a profile row right away
    if created:
        Profile.objects.get_or_create(user=instance)

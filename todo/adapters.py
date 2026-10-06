from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse

from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.account.models import EmailAddress
from allauth.account.utils import user_username
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAdapter(DefaultSocialAccountAdapter):
    """
    Two jobs.

    1. Google, GitHub and Facebook don't hand over a username, so one is made
       from the email instead of stopping to ask for it.

    2. If somebody already has a Hangarin account and signs in with Google or
       GitHub using the same email, they go straight into that account.
       Without this, allauth sees "that email is taken", gives up on the
       automatic sign-up and drops the person on the sign-up form. That was
       the "it sends me to sign up even though I have an account" problem.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user_username(user):
            base = (data.get("email") or "").split("@")[0] or data.get("first_name") or "user"
            user_username(user, get_account_adapter().generate_unique_username([base, "user"]))
        return user

    def pre_social_login(self, request, sociallogin):
        # Already linked (the normal returning visit), or somebody who is
        # logged in and is linking a provider on purpose: nothing to do.
        if sociallogin.is_existing or request.user.is_authenticated:
            return

        provider_emails = [a for a in sociallogin.email_addresses if a.email]
        if not provider_emails:
            return

        every = {a.email.lower() for a in provider_emails}
        confirmed = {a.email.lower() for a in provider_emails if a.verified}

        users = self._accounts_with_email(every)
        if not users:
            return  # a new person, let the normal sign-up carry on

        provider = sociallogin.account.get_provider().name

        # Only attach when the provider itself vouches for the address.
        # Google and GitHub do. Facebook doesn't always, and attaching on an
        # address nobody has proven would let a stranger into someone's account.
        matching = {u for u in users if self._owns_any(u, confirmed)}
        if len(matching) == 1 and len(users) == 1:
            user = matching.pop()
            if not user.is_active:
                self._bounce(request, "That account has been turned off.")
            sociallogin.connect(request, user)
            self._mark_verified(user, confirmed)
            return

        if len(users) > 1:
            self._bounce(
                request,
                "That email is on more than one account, so I can't tell which one "
                "is yours. Log in with your username and password instead.",
            )
        self._bounce(
            request,
            f"You already have a Hangarin account with that email, but {provider} "
            "didn't confirm it. Log in with your username and password.",
        )

    # ---- helpers ----------------------------------------------------

    @staticmethod
    def _accounts_with_email(emails):
        User = get_user_model()
        found = set()
        for email in emails:
            found.update(User.objects.filter(email__iexact=email))
            found.update(
                address.user
                for address in EmailAddress.objects.filter(email__iexact=email).select_related("user")
            )
        return found

    @staticmethod
    def _owns_any(user, emails):
        if (user.email or "").lower() in emails:
            return True
        return EmailAddress.objects.filter(user=user, email__in=list(emails)).exists()

    @staticmethod
    def _mark_verified(user, emails):
        """The provider confirmed these addresses, so Hangarin can too."""
        for email in emails:
            address = EmailAddress.objects.filter(user=user, email__iexact=email).first()
            if address is None:
                if (user.email or "").lower() != email:
                    continue
                has_primary = EmailAddress.objects.filter(user=user, primary=True).exists()
                EmailAddress.objects.create(user=user, email=email, verified=True, primary=not has_primary)
            elif not address.verified:
                address.verified = True
                address.save(update_fields=["verified"])

    @staticmethod
    def _bounce(request, text):
        messages.error(request, text)
        raise ImmediateHttpResponse(redirect(reverse("account_login")))

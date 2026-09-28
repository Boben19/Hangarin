from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.account.utils import user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAdapter(DefaultSocialAccountAdapter):
    """Google/GitHub/Facebook don't hand over a username, so make one from
    the email instead of stopping to ask for it."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user_username(user):
            base = (data.get("email") or "").split("@")[0] or data.get("first_name") or "user"
            user_username(user, get_account_adapter().generate_unique_username([base, "user"]))
        return user

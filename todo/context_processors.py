from django.conf import settings

from .stats import ensure_profile

_PROVIDER_LABELS = {"google": "Google", "facebook": "Facebook", "github": "GitHub"}


def _configured_providers():
    """Only offer a social button when its keys are actually filled in,
    otherwise the button leads to an error page."""
    found = []
    for key, label in _PROVIDER_LABELS.items():
        app = settings.SOCIALACCOUNT_PROVIDERS.get(key, {}).get("APP", {})
        if app.get("client_id") and app.get("secret"):
            found.append({"id": key, "name": label})
    return found


def _nav_section(request):
    """Which sidebar entry to light up. Detail and edit pages count as part
    of their list (task-detail lights up Tasks, and so on)."""
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else ""
    if not name:
        return ""
    if name.startswith("account_") or name.startswith("socialaccount_"):
        return "profile"
    return name.split("-")[0]


def hangarin(request):
    context = {
        "social_providers": _configured_providers(),
        "nav": _nav_section(request),
        "ADMIN_URL": settings.ADMIN_URL,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        context["my_profile"] = ensure_profile(user)
    return context

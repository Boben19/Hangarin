from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    """Send anonymous visitors to the login page. Login, admin and static stay open."""

    OPEN_PREFIXES = ("/accounts/", "/admin/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        is_open = path.startswith(self.OPEN_PREFIXES)
        if is_open or request.user.is_authenticated:
            return self.get_response(request)

        login_url = reverse("account_login")
        return redirect(f"{login_url}?next={path}")

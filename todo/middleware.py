from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.utils.cache import patch_cache_control


class LoginRequiredMiddleware:
    """Send anonymous visitors to the login page. Login, admin, static files
    and profile pictures stay reachable without an account."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.open_prefixes = (
            "/accounts/",
            "/" + settings.ADMIN_URL.lstrip("/"),
            settings.STATIC_URL,
            settings.MEDIA_URL,
        )

    def __call__(self, request):
        if request.path.startswith(self.open_prefixes) or request.user.is_authenticated:
            return self.get_response(request)
        # keeps the query string and encodes it properly
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)


class SecurityHeadersMiddleware:
    """
    A Content-Security-Policy plus a couple of small headers Django doesn't
    send by default. The policy says pages may only run scripts from this
    site, which shuts the door on most cross-site scripting even if a bug
    ever lets some markup through.

    The Django admin is left alone, it has its own needs.
    """

    POLICY = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
    ])

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL.lstrip("/")

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(self.admin_prefix):
            response.headers.setdefault("Content-Security-Policy", self.POLICY)
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Pages with someone's tasks on them shouldn't be kept by shared
        # proxies or the browser cache. Otherwise, on a shared computer, the
        # Back button after logging out can still show the previous person's
        # list. Static files and pictures are left alone so they cache normally.
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not request.path.startswith((settings.STATIC_URL, settings.MEDIA_URL))
            and "Cache-Control" not in response.headers
        ):
            patch_cache_control(response, private=True, no_cache=True)
        return response

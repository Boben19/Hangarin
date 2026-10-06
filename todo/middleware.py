from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.utils.cache import patch_cache_control
from django.utils.crypto import salted_hmac


def user_marker(user):
    """
    A short, one-way tag for "who is logged in". The service worker keeps
    saved pages per person: when the tag changes (somebody else logged in on
    the same browser) it throws the old copies away. It reveals nothing about
    the account and can't be turned back into an id.
    """
    if user is None or not user.is_authenticated:
        return ""
    return salted_hmac("hangarin.offline.marker", str(user.pk)).hexdigest()[:16]


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
        # The browser asks for these on its own, and the manifest request
        # goes out without cookies. If they redirected to the login page the
        # app could never be installed. None of them hold anything personal.
        self.open_paths = ("/manifest.json", "/serviceworker.js", "/offline/")

    def __call__(self, request):
        if (
            request.path.startswith(self.open_prefixes)
            or request.path in self.open_paths
            or request.user.is_authenticated
        ):
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

    # No outside hosts at all: fonts are the system ones, so the site loads
    # (and works offline) without talking to anyone else.
    POLICY = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
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

        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not request.path.startswith((settings.STATIC_URL, settings.MEDIA_URL))
        ):
            # Tells the service worker this is a signed-in page it may keep
            # for offline use, and whose it is.
            response.headers["X-Hangarin-Uid"] = user_marker(user)

            # The browser's own cache must not keep someone's tasks, or the
            # Back button after logging out on a shared computer could show
            # the last person's list. (The service worker's copy is handled
            # separately: it is wiped on logout and when a different person
            # signs in.)
            if "Cache-Control" not in response.headers:
                patch_cache_control(response, private=True, no_cache=True)
        return response

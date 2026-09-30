"""
Django settings for the Hangarin project.

Anything that changes between your laptop and the live site is read from
environment variables (or from a .env file next to manage.py), so the same
code runs in both places without editing this file.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


# ----------------------------------------------------------------
# Core
# ----------------------------------------------------------------

# Off unless you turn it on. Put DJANGO_DEBUG=True in your local .env only.
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    if DEBUG:
        # fine for a laptop, never for the live site
        SECRET_KEY = 'dev-only-key-do-not-use-on-a-real-server'
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY is not set. Add it to your .env file (or the '
            'environment) before running with DJANGO_DEBUG off. You can make '
            'one with: python -c "from django.core.management.utils import '
            'get_random_secret_key as g; print(g())"'
        )


def _looks_weak(key):
    lowered = key.lower()
    return (
        len(key) < 32
        or 'insecure' in lowered
        or 'change-this' in lowered
        or lowered.startswith(('os.environ', 'django-', 'your-'))
    )


# Anyone who knows this key can forge login sessions and password reset
# links, so a copied placeholder is refused instead of quietly accepted.
if not DEBUG and _looks_weak(SECRET_KEY):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY looks like a placeholder or is too short. Generate '
        'a fresh one (see .env.example) and put only the generated text after '
        'the = sign, with no Python code around it.'
    )

ALLOWED_HOSTS = env_list(
    'DJANGO_ALLOWED_HOSTS',
    'localhost,127.0.0.1,boben19.pythonanywhere.com',
)
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# Move the admin off /admin/ if you like (keep the trailing slash).
ADMIN_URL = os.environ.get('DJANGO_ADMIN_URL', 'admin/')


# ----------------------------------------------------------------
# Apps and middleware
# ----------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'todo.apps.TodoConfig',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.github',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'todo.middleware.LoginRequiredMiddleware',
    'todo.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'hangarin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'todo.context_processors.hangarin',
            ],
        },
    },
]

WSGI_APPLICATION = 'hangarin.wsgi.application'


# ----------------------------------------------------------------
# Login (allauth: username/password plus Google, Facebook, GitHub)
# ----------------------------------------------------------------

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = 'home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'account_login'

# Logging out or signing in through a social provider must be a POST.
# With these on, any web page could log you out or start a login for you
# just by pointing an <img> or a link at the URL.
ACCOUNT_LOGOUT_ON_GET = False
SOCIALACCOUNT_LOGIN_ON_GET = False

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True
# Confirming an address only makes sense when the site can actually send
# mail (see the EMAIL_* block below). Without a mail server nobody could
# ever confirm, so it stays optional there.
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' if os.environ.get('EMAIL_HOST') else 'optional'
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_BLACKLIST = ['admin', 'administrator', 'root', 'hangarin', 'staff', 'support']
ACCOUNT_FORMS = {
    'login': 'todo.account_forms.StyledLoginForm',
    'signup': 'todo.account_forms.StyledSignupForm',
}

SOCIALACCOUNT_FORMS = {'signup': 'todo.account_forms.StyledSocialSignupForm'}
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_ADAPTER = 'todo.adapters.SocialAdapter'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
    },
    'facebook': {
        'APP': {
            'client_id': os.environ.get('FACEBOOK_CLIENT_ID', ''),
            'secret': os.environ.get('FACEBOOK_CLIENT_SECRET', ''),
            'key': '',
        },
        'FIELDS': ['id', 'email', 'name'],
    },
    'github': {
        'APP': {
            'client_id': os.environ.get('GITHUB_CLIENT_ID', ''),
            'secret': os.environ.get('GITHUB_CLIENT_SECRET', ''),
            'key': '',
        },
    },
}

# Password reset emails need a real mail server to reach anyone. Fill in the
# EMAIL_* values in .env when you have one. Until then they print in the
# terminal, which is fine for testing.
if os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['EMAIL_HOST']
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Hangarin <no-reply@hangarin.local>')


# ----------------------------------------------------------------
# Database
# ----------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ----------------------------------------------------------------
# Passwords
# ----------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ----------------------------------------------------------------
# Language and time
# ----------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True


# ----------------------------------------------------------------
# Static and uploaded files
# ----------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Profile pictures land here. On PythonAnywhere, add a Static files entry
# that maps /media/ to this folder (see the README).
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Uploads are small (avatars only). Anything bigger is refused early.
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ----------------------------------------------------------------
# Hardening for the live site (all skipped while DEBUG is on)
# ----------------------------------------------------------------

X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# The token is put in the page by the template, so JavaScript never has to
# read the cookie and the cookie can be locked away from scripts.
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # PythonAnywhere terminates HTTPS in front of your app and tells Django
    # about it through this header. Set DJANGO_BEHIND_PROXY=False if you host
    # somewhere else that does not send it.
    if env_bool('DJANGO_BEHIND_PROXY', True):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Set DJANGO_SSL_REDIRECT=False if you test with DEBUG off over plain http.
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', True)

    # Starts at one hour so a mistake is easy to back out of. Once you are
    # happy everything works over https, raise it (31536000 is one year).
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))

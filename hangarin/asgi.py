"""
ASGI config for hangarin project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin.settings')

application = get_asgi_application()

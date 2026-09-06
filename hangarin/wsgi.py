"""
WSGI config for hangarin project.

This is also the file PythonAnywhere's "WSGI configuration file" should
point to when you set up the web app (see the deployment section of the
README for exactly what to paste in there).
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin.settings')

application = get_wsgi_application()

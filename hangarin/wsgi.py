"""
WSGI config for hangarin project.

This is also the file PythonAnywhere's "WSGI configuration file" should
point to when you set up the web app (see the deployment section of the
README for exactly what to paste in there).
"""

import os
import sys

path = '/home/yourusername/hangarin'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

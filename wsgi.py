import os
import sys

sys.path.append('/mnt/html/creche_application')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creache_app_project.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
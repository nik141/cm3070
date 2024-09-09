# json_dashboard/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as serve_static
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),  # Include the dashboard app URLs
]

# Serve media files during development
if settings.DEBUG:
    # Custom serving of video files from the specified folder
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_static, {'document_root': settings.VIDEO_DIR}),
    ]

# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('delete/<str:filename>/', views.delete_video, name='delete_video'),
]



"""URL-Konfiguration des Finanzen-Moduls."""
from django.urls import path

from . import views

app_name = 'finanzen'

urlpatterns = [
    path('', views.home, name='home'),
    path('datev-export/', views.datev_export, name='datev_export'),
    path('datev-export/download/', views.datev_export_download, name='datev_export_download'),
]

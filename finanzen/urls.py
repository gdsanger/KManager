"""URL-Konfiguration des Finanzen-Moduls."""
from django.urls import path

from . import views

app_name = 'finanzen'

urlpatterns = [
    path('', views.home, name='home'),
]

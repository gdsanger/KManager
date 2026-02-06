from django.urls import path
from . import views

app_name = 'auftragsverwaltung'

urlpatterns = [
    path('', views.auftragsverwaltung_home, name='home'),
]

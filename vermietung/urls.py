from django.urls import path
from . import views

urlpatterns = [
    path('', views.vermietung_home, name='vermietung'),
]   
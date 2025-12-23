from django.urls import path
from . import views

app_name = 'vermietung'

urlpatterns = [
    path('', views.vermietung_home, name='home'),
    path('components/', views.vermietung_components, name='components'),
]   
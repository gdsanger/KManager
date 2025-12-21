from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('htmx-demo/', views.htmx_demo, name='htmx_demo'),
]

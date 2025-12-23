from django.urls import path
from . import views

app_name = 'vermietung'

urlpatterns = [
    path('dokument/<int:dokument_id>/download/', views.download_dokument, name='dokument_download'),
    path('', views.vermietung_home, name='home'),
]   
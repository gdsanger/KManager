from django.urls import path
from . import views

urlpatterns = [
    path('dokument/<int:dokument_id>/download/', views.download_dokument, name='dokument_download'),
]   
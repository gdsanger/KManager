from django.urls import path
from . import views

app_name = 'vermietung'

urlpatterns = [
    path('dokument/<int:dokument_id>/download/', views.download_dokument, name='dokument_download'),
    path('', views.vermietung_home, name='home'),
    path('components/', views.vermietung_components, name='components'),
    
    # Customer (Kunde) URLs
    path('kunden/', views.kunde_list, name='kunde_list'),
    path('kunden/neu/', views.kunde_create, name='kunde_create'),
    path('kunden/<int:pk>/', views.kunde_detail, name='kunde_detail'),
    path('kunden/<int:pk>/bearbeiten/', views.kunde_edit, name='kunde_edit'),
    path('kunden/<int:pk>/loeschen/', views.kunde_delete, name='kunde_delete'),
    
    # MietObjekt (Rental Object) URLs
    path('mietobjekte/', views.mietobjekt_list, name='mietobjekt_list'),
    path('mietobjekte/neu/', views.mietobjekt_create, name='mietobjekt_create'),
    path('mietobjekte/<int:pk>/', views.mietobjekt_detail, name='mietobjekt_detail'),
    path('mietobjekte/<int:pk>/bearbeiten/', views.mietobjekt_edit, name='mietobjekt_edit'),
    path('mietobjekte/<int:pk>/loeschen/', views.mietobjekt_delete, name='mietobjekt_delete'),
]   
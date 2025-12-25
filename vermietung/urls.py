from django.urls import path
from . import views

app_name = 'vermietung'

urlpatterns = [
    # Document URLs
    path('dokument/<int:dokument_id>/download/', views.download_dokument, name='dokument_download'),
    path('dokument/<int:dokument_id>/loeschen/', views.dokument_delete, name='dokument_delete'),
    path('dokument/upload/<str:entity_type>/<int:entity_id>/', views.dokument_upload, name='dokument_upload'),
    
    # MietObjekt Image URLs
    path('mietobjekte/<int:pk>/bilder/hochladen/', views.mietobjekt_bild_upload, name='mietobjekt_bild_upload'),
    path('mietobjekte/bilder/<int:bild_id>/thumbnail/', views.serve_mietobjekt_bild, {'mode': 'thumbnail'}, name='mietobjekt_bild_thumbnail'),
    path('mietobjekte/bilder/<int:bild_id>/original/', views.serve_mietobjekt_bild, {'mode': 'original'}, name='mietobjekt_bild_original'),
    path('mietobjekte/bilder/<int:bild_id>/loeschen/', views.mietobjekt_bild_delete, name='mietobjekt_bild_delete'),
    
    path('', views.vermietung_home, name='home'),
    path('components/', views.vermietung_components, name='components'),
    
    # Customer (Kunde) URLs
    path('kunden/', views.kunde_list, name='kunde_list'),
    path('kunden/neu/', views.kunde_create, name='kunde_create'),
    path('kunden/<int:pk>/', views.kunde_detail, name='kunde_detail'),
    path('kunden/<int:pk>/bearbeiten/', views.kunde_edit, name='kunde_edit'),
    path('kunden/<int:pk>/loeschen/', views.kunde_delete, name='kunde_delete'),
    
    # Standort (Location) URLs
    path('standorte/', views.standort_list, name='standort_list'),
    path('standorte/neu/', views.standort_create, name='standort_create'),
    path('standorte/<int:pk>/', views.standort_detail, name='standort_detail'),
    path('standorte/<int:pk>/bearbeiten/', views.standort_edit, name='standort_edit'),
    path('standorte/<int:pk>/loeschen/', views.standort_delete, name='standort_delete'),
    
    # MietObjekt (Rental Object) URLs
    path('mietobjekte/', views.mietobjekt_list, name='mietobjekt_list'),
    path('mietobjekte/neu/', views.mietobjekt_create, name='mietobjekt_create'),
    path('mietobjekte/<int:pk>/', views.mietobjekt_detail, name='mietobjekt_detail'),
    path('mietobjekte/<int:pk>/bearbeiten/', views.mietobjekt_edit, name='mietobjekt_edit'),
    path('mietobjekte/<int:pk>/loeschen/', views.mietobjekt_delete, name='mietobjekt_delete'),
    
    # Vertrag (Contract) URLs
    path('vertraege/', views.vertrag_list, name='vertrag_list'),
    path('vertraege/neu/', views.vertrag_create, name='vertrag_create'),
    path('vertraege/<int:pk>/', views.vertrag_detail, name='vertrag_detail'),
    path('vertraege/<int:pk>/bearbeiten/', views.vertrag_edit, name='vertrag_edit'),
    path('vertraege/<int:pk>/beenden/', views.vertrag_end, name='vertrag_end'),
    path('vertraege/<int:pk>/stornieren/', views.vertrag_cancel, name='vertrag_cancel'),
    
    # Uebergabeprotokoll (Handover Protocol) URLs
    path('uebergabeprotokolle/', views.uebergabeprotokoll_list, name='uebergabeprotokoll_list'),
    path('uebergabeprotokolle/neu/', views.uebergabeprotokoll_create, name='uebergabeprotokoll_create'),
    path('uebergabeprotokolle/<int:pk>/', views.uebergabeprotokoll_detail, name='uebergabeprotokoll_detail'),
    path('uebergabeprotokolle/<int:pk>/bearbeiten/', views.uebergabeprotokoll_edit, name='uebergabeprotokoll_edit'),
    path('uebergabeprotokolle/<int:pk>/loeschen/', views.uebergabeprotokoll_delete, name='uebergabeprotokoll_delete'),
    path('vertraege/<int:vertrag_pk>/uebergabeprotokoll/neu/', views.uebergabeprotokoll_create_from_vertrag, name='uebergabeprotokoll_create_from_vertrag'),
]   
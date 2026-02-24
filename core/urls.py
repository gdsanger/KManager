from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('htmx-demo/', views.htmx_demo, name='htmx_demo'),
    
    # User Profile
    path('profile/', views.profile, name='profile'),
    
    # SMTP Settings
    path('smtp-settings/', views.smtp_settings, name='smtp_settings'),
    
    # Mail Templates
    path('mail-templates/', views.mailtemplate_list, name='mailtemplate_list'),
    path('mail-templates/create/', views.mailtemplate_create, name='mailtemplate_create'),
    path('mail-templates/<int:pk>/', views.mailtemplate_detail, name='mailtemplate_detail'),
    path('mail-templates/<int:pk>/edit/', views.mailtemplate_edit, name='mailtemplate_edit'),
    path('mail-templates/<int:pk>/delete/', views.mailtemplate_delete, name='mailtemplate_delete'),
    
    # Mandanten
    path('mandanten/', views.mandant_list, name='mandant_list'),
    path('mandanten/create/', views.mandant_create, name='mandant_create'),
    path('mandanten/<int:pk>/', views.mandant_detail, name='mandant_detail'),
    path('mandanten/<int:pk>/edit/', views.mandant_edit, name='mandant_edit'),
    path('mandanten/<int:pk>/delete/', views.mandant_delete, name='mandant_delete'),
    
    # Customer Support Portal
    path('support-portal/', views.support_portal, name='support_portal'),
    
    # Item Management
    path('items/', views.item_management, name='item_management'),
    path('items/save/', views.item_save_ajax, name='item_save'),
    path('items/new/', views.item_create_new, name='item_create_new'),
    path('items/new-ajax/', views.item_new_ajax, name='item_new_ajax'),
    path('items/edit/<int:pk>/', views.item_edit_ajax, name='item_edit_ajax'),
    path('items/cost-type-2-options/', views.cost_type_2_options, name='cost_type_2_options'),
    path('items/groups/<int:pk>/', views.item_group_get, name='item_group_get'),
    path('items/groups/save/', views.item_group_save, name='item_group_save'),
    
    # Units
    path('units/', views.unit_list, name='unit_list'),
    path('units/create/', views.unit_create, name='unit_create'),
    path('units/<int:pk>/', views.unit_detail, name='unit_detail'),
    path('units/<int:pk>/edit/', views.unit_edit, name='unit_edit'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),

    # Projektverwaltung
    path('projekte/', views.projekt_list, name='projekt_list'),
    path('projekte/create/', views.projekt_create, name='projekt_create'),
    path('projekte/<int:pk>/', views.projekt_detail, name='projekt_detail'),
    path('projekte/<int:pk>/edit/', views.projekt_edit, name='projekt_edit'),
    path('projekte/<int:pk>/delete/', views.projekt_delete, name='projekt_delete'),
    path('projekte/<int:pk>/upload/', views.projekt_file_upload, name='projekt_file_upload'),
    path('projekte/<int:pk>/ordner/create/', views.projekt_ordner_create, name='projekt_ordner_create'),
    path('projekte/<int:pk>/files/<int:file_pk>/delete/', views.projekt_file_delete, name='projekt_file_delete'),
    path('projekte/<int:pk>/files/<int:file_pk>/download/', views.projekt_file_download, name='projekt_file_download'),
]

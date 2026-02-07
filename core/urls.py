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
    path('items/groups/<int:pk>/', views.item_group_get, name='item_group_get'),
    path('items/groups/save/', views.item_group_save, name='item_group_save'),
]

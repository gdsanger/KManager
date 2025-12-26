from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('htmx-demo/', views.htmx_demo, name='htmx_demo'),
    
    # SMTP Settings
    path('smtp-settings/', views.smtp_settings, name='smtp_settings'),
    
    # Mail Templates
    path('mail-templates/', views.mailtemplate_list, name='mailtemplate_list'),
    path('mail-templates/create/', views.mailtemplate_create, name='mailtemplate_create'),
    path('mail-templates/<int:pk>/', views.mailtemplate_detail, name='mailtemplate_detail'),
    path('mail-templates/<int:pk>/edit/', views.mailtemplate_edit, name='mailtemplate_edit'),
    path('mail-templates/<int:pk>/delete/', views.mailtemplate_delete, name='mailtemplate_delete'),
]

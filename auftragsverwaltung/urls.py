from django.urls import path
from . import views

app_name = 'auftragsverwaltung'

urlpatterns = [
    path('', views.auftragsverwaltung_home, name='home'),
    
    # Document list views (generic view with doc_key parameter)
    path('documents/<str:doc_key>/', views.document_list, name='document_list'),
    
    # Convenience URLs for specific document types
    path('angebote/', views.document_list, {'doc_key': 'quote'}, name='quotes'),
    path('auftraege/', views.document_list, {'doc_key': 'order'}, name='orders'),
    path('rechnungen/', views.document_list, {'doc_key': 'invoice'}, name='invoices'),
    path('lieferscheine/', views.document_list, {'doc_key': 'delivery'}, name='deliveries'),
    path('gutschriften/', views.document_list, {'doc_key': 'credit'}, name='credits'),
]

from django.urls import path
from . import views

app_name = 'auftragsverwaltung'

urlpatterns = [
    path('', views.auftragsverwaltung_home, name='home'),
    
    # Contract list view
    path('contracts/', views.contract_list, name='contract_list'),
    
    # Document list views (generic view with doc_key parameter)
    path('documents/<str:doc_key>/', views.document_list, name='document_list'),
    
    # Document detail, create, update views
    path('documents/<str:doc_key>/create/', views.document_create, name='document_create'),
    path('documents/<str:doc_key>/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<str:doc_key>/<int:pk>/update/', views.document_update, name='document_update'),
    
    # AJAX endpoints
    path('ajax/calculate-payment-term/', views.ajax_calculate_payment_term, name='ajax_calculate_payment_term'),
    path('ajax/search-articles/', views.ajax_search_articles, name='ajax_search_articles'),
    path('ajax/get-kostenart2-options/', views.ajax_get_kostenart2_options, name='ajax_get_kostenart2_options'),
    path('ajax/documents/<str:doc_key>/<int:pk>/lines/add/', views.ajax_add_line, name='ajax_add_line'),
    path('ajax/documents/<str:doc_key>/<int:pk>/lines/<int:line_id>/update/', views.ajax_update_line, name='ajax_update_line'),
    path('ajax/documents/<str:doc_key>/<int:pk>/lines/<int:line_id>/delete/', views.ajax_delete_line, name='ajax_delete_line'),
    
    # Convenience URLs for specific document types
    path('angebote/', views.document_list, {'doc_key': 'quote'}, name='quotes'),
    path('auftraege/', views.document_list, {'doc_key': 'order'}, name='orders'),
    path('rechnungen/', views.document_list, {'doc_key': 'invoice'}, name='invoices'),
    path('lieferscheine/', views.document_list, {'doc_key': 'delivery'}, name='deliveries'),
    path('gutschriften/', views.document_list, {'doc_key': 'credit'}, name='credits'),
]

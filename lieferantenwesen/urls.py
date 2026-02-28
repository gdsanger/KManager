"""URL configuration for the Lieferantenwesen module."""
from django.urls import path

from . import views

app_name = "lieferantenwesen"

urlpatterns = [
    # Home / dashboard
    path("", views.home, name="home"),

    # Supplier (Lieferant) CRUD
    path("lieferanten/", views.supplier_list, name="supplier_list"),
    path("lieferanten/neu/", views.supplier_create, name="supplier_create"),
    path("lieferanten/<int:pk>/", views.supplier_detail, name="supplier_detail"),
    path("lieferanten/<int:pk>/bearbeiten/", views.supplier_edit, name="supplier_edit"),

    # InvoiceIn (Eingangsrechnung)
    path("eingangsrechnungen/", views.invoice_list, name="invoice_list"),
    path("eingangsrechnungen/neu/", views.invoice_create, name="invoice_create"),
    path("eingangsrechnungen/pdf-upload/", views.invoice_upload_pdf, name="invoice_upload_pdf"),
    path("eingangsrechnungen/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("eingangsrechnungen/<int:pk>/bearbeiten/", views.invoice_edit, name="invoice_edit"),
    path("eingangsrechnungen/<int:pk>/freigabe/", views.invoice_approve, name="invoice_approve"),
]

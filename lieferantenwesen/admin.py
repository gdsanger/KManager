"""Django admin for the Lieferantenwesen module."""
from django.contrib import admin

from .models import InvoiceIn, InvoiceInLine, Supplier


class InvoiceInLineInline(admin.TabularInline):
    model = InvoiceInLine
    extra = 0
    fields = [
        "position_no",
        "description",
        "quantity",
        "unit",
        "unit_price",
        "net_amount",
        "tax_rate",
        "tax_amount",
        "gross_amount",
    ]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "adresse_city", "email", "telefon", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "email", "adresse_city", "ust_id"]
    ordering = ["name"]


@admin.register(InvoiceIn)
class InvoiceInAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_no",
        "invoice_date",
        "supplier",
        "gross_amount",
        "currency",
        "status",
        "due_date",
    ]
    list_filter = ["status", "currency"]
    search_fields = ["invoice_no", "supplier__name", "payment_reference"]
    ordering = ["-invoice_date"]
    readonly_fields = [
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "approved_at",
        "approved_by",
        "rejected_at",
        "rejected_by",
    ]
    inlines = [InvoiceInLineInline]


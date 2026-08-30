"""Django admin for the Lieferantenwesen module."""
from django.contrib import admin

from .models import InvoiceIn, InvoiceInLine


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


@admin.register(InvoiceIn)
class InvoiceInAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_no",
        "invoice_date",
        "company",
        "supplier",
        "gross_amount",
        "currency",
        "status",
        "due_date",
        "export_status",
    ]
    list_filter = ["company", "status", "currency", "export_status"]
    search_fields = [
        "invoice_no", "supplier__name", "payment_reference", "export_batch_id",
    ]
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
        # Export-Tracking wird ausschließlich vom Export-Service gesetzt.
        "export_status",
        "exported_at",
        "export_batch_id",
    ]
    inlines = [InvoiceInLineInline]


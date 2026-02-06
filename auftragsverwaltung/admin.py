from django.contrib import admin
from auftragsverwaltung.models import DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    """Admin interface for DocumentType"""
    list_display = ('key', 'name', 'prefix', 'is_invoice', 'is_correction', 'requires_due_date', 'is_active')
    list_filter = ('is_active', 'is_invoice', 'is_correction', 'requires_due_date')
    search_fields = ('key', 'name', 'prefix')
    ordering = ('key',)
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('key', 'name', 'prefix', 'is_active')
        }),
        ('Flags', {
            'fields': ('is_invoice', 'is_correction', 'requires_due_date')
        }),
    )

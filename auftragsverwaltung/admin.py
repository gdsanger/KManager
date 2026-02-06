from django.contrib import admin
from auftragsverwaltung.models import DocumentType, NumberRange


@admin.register(NumberRange)
class NumberRangeAdmin(admin.ModelAdmin):
    """Admin interface for NumberRange"""
    list_display = ('company', 'document_type', 'reset_policy', 'current_year', 'current_seq', 'format')
    list_filter = ('company', 'document_type', 'reset_policy')
    search_fields = ('company__name', 'document_type__name', 'document_type__key')
    ordering = ('company', 'document_type')
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('company', 'document_type')
        }),
        ('Konfiguration', {
            'fields': ('format', 'reset_policy')
        }),
        ('Status', {
            'fields': ('current_year', 'current_seq'),
            'description': 'Diese Felder werden automatisch verwaltet, können aber bei Bedarf manuell angepasst werden.'
        }),
    )


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

from django.contrib import admin
from auftragsverwaltung.models import DocumentType, NumberRange, SalesDocument


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


@admin.register(SalesDocument)
class SalesDocumentAdmin(admin.ModelAdmin):
    """Admin interface for SalesDocument"""
    list_display = (
        'number',
        'company',
        'document_type',
        'status',
        'issue_date',
        'due_date',
        'total_net',
        'total_tax',
        'total_gross',
        'source_document'
    )
    list_filter = (
        'company',
        'document_type',
        'status',
        'issue_date'
    )
    search_fields = (
        'number',
        'company__name',
        'document_type__name',
        'document_type__key',
        'notes_internal',
        'notes_public'
    )
    ordering = ('-issue_date', '-id')
    date_hierarchy = 'issue_date'
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('company', 'document_type', 'number', 'status')
        }),
        ('Datumsangaben', {
            'fields': ('issue_date', 'due_date', 'paid_at')
        }),
        ('Beziehungen', {
            'fields': ('payment_term', 'source_document')
        }),
        ('Beträge', {
            'fields': ('total_net', 'total_tax', 'total_gross'),
            'description': 'Diese Felder sind denormalisiert. Berechnungslogik wird in einem separaten Issue implementiert.'
        }),
        ('Snapshots', {
            'fields': ('payment_term_snapshot',),
            'classes': ('collapse',),
            'description': 'JSON-Snapshots zum Zeitpunkt der Belegausstellung.'
        }),
        ('Notizen', {
            'fields': ('notes_internal', 'notes_public'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ()
    
    def get_readonly_fields(self, request, obj=None):
        """Make payment_term_snapshot readonly by default"""
        readonly = list(self.readonly_fields)
        # Optionally make payment_term_snapshot readonly in the future
        return readonly

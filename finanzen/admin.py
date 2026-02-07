from django.contrib import admin
from .models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry


@admin.register(CompanyAccountingSettings)
class CompanyAccountingSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for Company Accounting Settings
    
    Allows configuring DATEV settings and revenue accounts per company/mandant
    """
    list_display = ['company', 'datev_consultant_number', 'datev_client_number', 'tax_number']
    list_filter = ['company']
    search_fields = ['company__name', 'datev_consultant_number', 'datev_client_number', 'tax_number']
    
    fieldsets = (
        ('Mandant', {
            'fields': ('company',)
        }),
        ('DATEV Konfiguration', {
            'fields': ('datev_consultant_number', 'datev_client_number', 'tax_number')
        }),
        ('Erlöskonten je Steuersatz', {
            'fields': ('revenue_account_0', 'revenue_account_7', 'revenue_account_19'),
            'description': 'Erlöskonten für die jeweiligen Steuersätze (0%, 7%, 19%)'
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion"""
        return True


@admin.register(OutgoingInvoiceJournalEntry)
class OutgoingInvoiceJournalEntryAdmin(admin.ModelAdmin):
    """
    Admin interface for Outgoing Invoice Journal Entries
    
    Read-only view of immutable journal entries.
    Journal entries should not be modified after creation (snapshot principle).
    """
    list_display = [
        'document_number',
        'document_date',
        'document_kind',
        'customer_name',
        'gross_amount',
        'export_status',
        'created_at'
    ]
    list_filter = [
        'company',
        'document_kind',
        'export_status',
        'document_date',
        'created_at'
    ]
    search_fields = [
        'document_number',
        'customer_name',
        'debtor_number',
        'export_batch_id'
    ]
    date_hierarchy = 'document_date'
    readonly_fields = [
        'company',
        'document',
        'document_number',
        'document_date',
        'document_kind',
        'customer_name',
        'debtor_number',
        'net_0',
        'net_7',
        'net_19',
        'tax_amount',
        'gross_amount',
        'revenue_account_0',
        'revenue_account_7',
        'revenue_account_19',
        'export_status',
        'exported_at',
        'export_batch_id',
        'created_at',
    ]
    
    fieldsets = (
        ('Referenzen', {
            'fields': ('company', 'document')
        }),
        ('Belegdaten (Snapshot)', {
            'fields': ('document_number', 'document_date', 'document_kind', 'customer_name', 'debtor_number')
        }),
        ('Beträge je Steuersatz', {
            'fields': ('net_0', 'net_7', 'net_19', 'tax_amount', 'gross_amount'),
            'description': 'Nettobeträge aufgeteilt nach Steuersatz'
        }),
        ('Erlöskonten (Snapshot)', {
            'fields': ('revenue_account_0', 'revenue_account_7', 'revenue_account_19')
        }),
        ('Export-Tracking', {
            'fields': ('export_status', 'exported_at', 'export_batch_id')
        }),
        ('Meta', {
            'fields': ('created_at',)
        }),
    )
    
    def has_add_permission(self, request):
        """
        Disable manual creation through admin.
        Journal entries should be created programmatically.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Disable deletion to maintain immutability.
        Journal entries are permanent accounting records.
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """
        Disable editing to maintain immutability.
        Journal entries are snapshot-based and should not be modified.
        """
        return False

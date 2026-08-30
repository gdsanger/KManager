from django.contrib import admin, messages
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
            'fields': ('datev_consultant_number', 'datev_client_number', 'tax_number'),
            'description': (
                'Berater- und Mandantennummer sind Pflichtfelder des '
                'EXTF-Kopfsatzes. Solange der Buchungsstapel nicht an einen '
                'Steuerberater übermittelt wird, genügen die vorbelegten '
                'Platzhalter; für die Übermittlung die echten Werte eintragen.'
            )
        }),
        ('Buchungsstapel (EXTF-Kopfsatz)', {
            'fields': ('account_length', 'fiscal_year_start'),
            'description': (
                'Sachkontenlänge und Wirtschaftsjahresbeginn gehen in den '
                'Kopfsatz jeder Exportdatei ein.'
            )
        }),
        ('Erlöskonten je Steuersatz', {
            'fields': ('revenue_account_0', 'revenue_account_7', 'revenue_account_19'),
            'description': (
                'Erlöskonten für die jeweiligen Steuersätze (0%, 7%, 19%). '
                'Ein an der Kostenart hinterlegtes Erlöskonto übersteuert diese Konten.'
            )
        }),
        ('Gegenkonten Zahlungsseite', {
            'fields': ('bank_account', 'cash_account', 'clearing_account'),
            'description': (
                'GIS exportiert keine Zahlungsbuchungen – der Ausgleich der '
                'offenen Posten passiert im Fibu-System. Die Konten werden hier '
                'für die Einrichtung des Zielsystems gepflegt.'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion"""
        return True


@admin.register(OutgoingInvoiceJournalEntry)
class OutgoingInvoiceJournalEntryAdmin(admin.ModelAdmin):
    """
    Admin interface for Outgoing Invoice Journal Entries

    Journaleinträge sind Snapshots: Anlegen und Bearbeiten bleiben gesperrt,
    Löschen ist als Korrekturweg erlaubt (nur hier im Admin, nicht im Frontend).
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
        Anlegen bleibt bewusst gesperrt.

        Ein Journaleintrag ist der Snapshot eines finalisierten Belegs und
        entsteht ausschließlich programmatisch über
        `finanzen.services.journal.create_journal_entry()`. Ein von Hand
        erfasster Eintrag hätte keinen Beleg als Quelle.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Bearbeiten bleibt bewusst gesperrt.

        Ein Journaleintrag ist ein Snapshot. Korrigiert wird er, indem er
        gelöscht und aus dem Beleg neu erzeugt wird – nicht, indem einzelne
        Werte nachträglich editiert werden. Ein editierbarer Snapshot wäre
        kein Snapshot mehr.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Löschen ist erlaubt – ausschließlich hier im Admin-Backend.

        Beim Aufbau und in der Erprobung entstehen Einträge aus Testbelegen
        oder aus Belegen, die vor einer Korrektur an Kontierung oder
        Steuersätzen finalisiert wurden. Löschen ist dabei kein Datenverlust,
        sondern ein Korrekturweg:

        - Das referenzierte `SalesDocument` bleibt unberührt (der FK steht auf
          PROTECT und schützt den Beleg, nicht den Journaleintrag).
        - Der Eintrag lässt sich idempotent neu erzeugen – über eine erneute
          Finalisierung des Belegs oder über
          `python manage.py backfill_journal_entries`.

        Bereits exportierte Einträge werden nicht blockiert, aber beim Löschen
        mit einer Warnung versehen (siehe `_warn_if_exported`).
        """
        return True

    def _warn_if_exported(self, request, entry):
        """
        Warnen, wenn ein bereits exportierter Eintrag gelöscht wird.

        Der Eintrag ist dann Teil eines DATEV-Buchungsstapels, der bereits im
        Fibu-System liegt – das Löschen hier zieht ihn dort nicht zurück.
        """
        if entry.export_status != 'EXPORTED':
            return

        messages.warning(
            request,
            f'Journaleintrag {entry.document_number} war bereits exportiert '
            f'(Export-Batch {entry.export_batch_id or "unbekannt"}) und ist Teil '
            f'eines DATEV-Buchungsstapels im Fibu-System. Das Löschen hier '
            f'entfernt die Buchung dort nicht – bitte im Fibu-System nachziehen.'
        )

    def delete_model(self, request, obj):
        """Einzellöschung: exportierte Einträge vorab melden."""
        self._warn_if_exported(request, obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Massenaktion: exportierte Einträge vorab melden."""
        for entry in queryset.filter(export_status='EXPORTED'):
            self._warn_if_exported(request, entry)
        super().delete_queryset(request, queryset)

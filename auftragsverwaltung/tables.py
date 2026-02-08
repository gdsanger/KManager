"""
Django Tables2 table definitions for the auftragsverwaltung app.
"""
import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import SalesDocument, Contract, TextTemplate
from finanzen.models import OutgoingInvoiceJournalEntry


class SalesDocumentTable(tables.Table):
    """Table for displaying Sales Documents (Angebote, Aufträge, Rechnungen, etc.)."""
    
    number = tables.Column(
        verbose_name='Nummer',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    company = tables.Column(
        verbose_name='Mandant',
        accessor='company.name',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    customer = tables.Column(
        verbose_name='Kunde',
        accessor='customer.name',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    subject = tables.Column(
        verbose_name='Betreff',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 200px;'}}
    )
    
    issue_date = tables.DateColumn(
        verbose_name='Belegdatum',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    due_date = tables.DateColumn(
        verbose_name='Fälligkeit',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    total_gross = tables.Column(
        verbose_name='Brutto',
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    status = tables.Column(
        verbose_name='Status',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    aktionen = tables.Column(
        verbose_name='Aktionen',
        empty_values=(),
        orderable=False,
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    def render_number(self, value, record):
        """Render number as a link to detail view."""
        url = reverse('auftragsverwaltung:document_detail', kwargs={
            'doc_key': record.document_type.key,
            'pk': record.pk
        })
        return format_html('<a href="{}" class="text-decoration-none">{}</a>', url, value)
    
    def render_total_gross(self, value):
        """Render total_gross with currency."""
        if value is None:
            return '—'
        return f'{value:.2f} €'
    
    def render_status(self, value, record):
        """Render status with colored badge."""
        status_classes = {
            'DRAFT': 'bg-secondary',
            'SENT': 'bg-info',
            'ACCEPTED': 'bg-success',
            'REJECTED': 'bg-danger',
            'CANCELLED': 'bg-dark',
            'OPEN': 'bg-warning',
            'PAID': 'bg-success',
            'OVERDUE': 'bg-danger',
        }
        badge_class = status_classes.get(record.status, 'bg-secondary')
        display_value = record.get_status_display()
        return format_html('<span class="badge {}">{}</span>', badge_class, display_value)
    
    def render_aktionen(self, record):
        """Render action buttons."""
        detail_url = reverse('auftragsverwaltung:document_detail', kwargs={
            'doc_key': record.document_type.key,
            'pk': record.pk
        })
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<a href="{}" class="btn btn-outline-info" title="Details">'
            '<i class="bi bi-eye"></i></a>'
            '</div>',
            detail_url
        )
    
    class Meta:
        model = SalesDocument
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'number',
            'company',
            'customer',
            'subject',
            'issue_date',
            'due_date',
            'total_gross',
            'status',
            'aktionen'
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 25


class ContractTable(tables.Table):
    """Table for displaying Contracts (Verträge)."""
    
    name = tables.Column(
        verbose_name='Vertragsname',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 200px;'}}
    )
    
    company = tables.Column(
        verbose_name='Mandant',
        accessor='company.name',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    customer = tables.Column(
        verbose_name='Kunde',
        accessor='customer.name',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    interval = tables.Column(
        verbose_name='Intervall',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    start_date = tables.DateColumn(
        verbose_name='Startdatum',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    end_date = tables.DateColumn(
        verbose_name='Enddatum',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    next_run_date = tables.DateColumn(
        verbose_name='Nächster Lauf',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    last_run_date = tables.DateColumn(
        verbose_name='Letzter Lauf',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    is_active = tables.BooleanColumn(
        verbose_name='Aktiv',
        attrs={'td': {'class': 'text-center'}}
    )
    
    aktionen = tables.Column(
        verbose_name='Aktionen',
        empty_values=(),
        orderable=False,
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    def render_name(self, value, record):
        """Render name as an HTML link to the contract update view."""
        url = reverse('auftragsverwaltung:contract_update', kwargs={'pk': record.pk})
        return format_html('<a href="{}" class="text-decoration-none">{}</a>', url, value)
    
    def render_interval(self, value, record):
        """Render interval with German display text."""
        return record.get_interval_display()
    
    def render_end_date(self, value):
        """Render end_date with fallback for None."""
        if value is None:
            return '—'
        return value
    
    def render_last_run_date(self, value):
        """Render last_run_date with fallback for None."""
        if value is None:
            return '—'
        return value
    
    def render_aktionen(self, record):
        """Render action buttons."""
        detail_url = reverse('auftragsverwaltung:contract_detail', kwargs={'pk': record.pk})
        edit_url = reverse('auftragsverwaltung:contract_update', kwargs={'pk': record.pk})
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<a href="{}" class="btn btn-outline-info" title="Details">'
            '<i class="bi bi-eye"></i></a>'
            '<a href="{}" class="btn btn-outline-primary" title="Bearbeiten">'
            '<i class="bi bi-pencil"></i></a>'
            '</div>',
            detail_url,
            edit_url
        )
    
    class Meta:
        model = Contract
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'name',
            'company',
            'customer',
            'interval',
            'start_date',
            'end_date',
            'next_run_date',
            'last_run_date',
            'is_active',
            'aktionen',
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 25


class TextTemplateTable(tables.Table):
    """Table for displaying Text Templates (Textbausteine)."""
    
    title = tables.Column(
        verbose_name='Titel',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    type = tables.Column(
        verbose_name='Typ',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    key = tables.Column(
        verbose_name='Schlüssel',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    is_active = tables.BooleanColumn(
        verbose_name='Aktiv',
        attrs={'td': {'class': 'text-center'}}
    )
    
    updated_at = tables.DateTimeColumn(
        verbose_name='Aktualisiert',
        format='d.m.Y H:i',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    aktionen = tables.Column(
        verbose_name='Aktionen',
        empty_values=(),
        orderable=False,
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    def render_title(self, value, record):
        """Render title as a link to edit view."""
        url = reverse('auftragsverwaltung:texttemplate_update', kwargs={'pk': record.pk})
        return format_html('<a href="{}" class="text-decoration-none">{}</a>', url, value)
    
    def render_type(self, value, record):
        """Render type with German display text."""
        type_classes = {
            'HEADER': 'bg-info',
            'FOOTER': 'bg-warning',
            'BOTH': 'bg-success',
        }
        badge_class = type_classes.get(record.type, 'bg-secondary')
        display_value = record.get_type_display()
        return format_html('<span class="badge {}">{}</span>', badge_class, display_value)
    
    def render_aktionen(self, record):
        """Render action buttons."""
        edit_url = reverse('auftragsverwaltung:texttemplate_update', kwargs={'pk': record.pk})
        delete_url = reverse('auftragsverwaltung:texttemplate_delete', kwargs={'pk': record.pk})
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<a href="{}" class="btn btn-outline-primary" title="Bearbeiten">'
            '<i class="bi bi-pencil"></i></a>'
            '<a href="{}" class="btn btn-outline-danger" title="Löschen">'
            '<i class="bi bi-trash"></i></a>'
            '</div>',
            edit_url,
            delete_url
        )
    
    class Meta:
        model = TextTemplate
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'title',
            'type',
            'key',
            'is_active',
            'updated_at',
            'aktionen'
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 25


class OutgoingInvoiceJournalTable(tables.Table):
    """Table for displaying Outgoing Invoice Journal Entries (Rechnungsausgangsjournal)."""
    
    company = tables.Column(
        verbose_name='Mandant',
        accessor='company.name',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    document_number = tables.Column(
        verbose_name='Belegnummer',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    document_date = tables.DateColumn(
        verbose_name='Datum',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    customer_name = tables.Column(
        verbose_name='Kunde',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    amounts = tables.Column(
        verbose_name='Netto/Brutto',
        empty_values=(),
        orderable=False,
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    export_status = tables.Column(
        verbose_name='Status',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    def render_document_number(self, value, record):
        """Render document_number as a link to detail view."""
        url = reverse('auftragsverwaltung:journal_detail', kwargs={'pk': record.pk})
        return format_html('<a href="{}" class="text-decoration-none">{}</a>', url, value)
    
    def render_amounts(self, record):
        """Render net and gross amounts."""
        total_net = record.net_0 + record.net_7 + record.net_19
        return f'{total_net:.2f} € / {record.gross_amount:.2f} €'
    
    def render_export_status(self, value, record):
        """Render export_status with colored badge."""
        status_classes = {
            'OPEN': 'bg-warning',
            'EXPORTED': 'bg-success',
            'ERROR': 'bg-danger',
        }
        badge_class = status_classes.get(record.export_status, 'bg-secondary')
        display_value = record.get_export_status_display()
        return format_html('<span class="badge {}">{}</span>', badge_class, display_value)
    
    class Meta:
        model = OutgoingInvoiceJournalEntry
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'company',
            'document_number',
            'document_date',
            'customer_name',
            'amounts',
            'export_status',
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 25

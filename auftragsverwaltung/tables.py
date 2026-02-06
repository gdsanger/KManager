"""
Django Tables2 table definitions for the auftragsverwaltung app.
"""
import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import SalesDocument


class SalesDocumentTable(tables.Table):
    """Table for displaying Sales Documents (Angebote, Aufträge, Rechnungen, etc.)."""
    
    number = tables.Column(
        verbose_name='Nummer',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    subject = tables.Column(
        verbose_name='Betreff',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 200px;'}}
    )
    
    customer_name = tables.Column(
        verbose_name='Kunde',
        accessor='customer_name',
        order_by='customer_name'
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
        """Render number as a link to detail view (when available)."""
        # For MVP, just return the number as text
        # TODO: Add detail view link when detail view is implemented
        return format_html('<span class="text-decoration-none">{}</span>', value)
    
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
        # For MVP, minimal actions
        # TODO: Add detail, edit, delete URLs when those views are implemented
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<button type="button" class="btn btn-outline-info" title="Details" disabled>'
            '<i class="bi bi-eye"></i></button>'
            '<button type="button" class="btn btn-outline-warning" title="Bearbeiten" disabled>'
            '<i class="bi bi-pencil"></i></button>'
            '</div>'
        )
    
    class Meta:
        model = SalesDocument
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'number',
            'subject',
            'customer_name',
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

"""
Django Tables2 table definitions for the vermietung app.
"""
import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import Eingangsrechnung


class EingangsrechnungTable(tables.Table):
    """Table for displaying Eingangsrechnungen (incoming invoices)."""
    
    belegdatum = tables.DateColumn(
        verbose_name='Belegdatum',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    belegnummer = tables.Column(
        verbose_name='Belegnummer',
        linkify=True,
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    lieferant = tables.Column(
        verbose_name='Lieferant',
        accessor='lieferant.full_name',
        order_by='lieferant__name'
    )
    
    mietobjekt = tables.Column(
        verbose_name='Mietobjekt',
        accessor='mietobjekt.name',
        order_by='mietobjekt__name'
    )
    
    betreff = tables.Column(
        verbose_name='Betreff',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 200px;'}}
    )
    
    nettobetrag = tables.Column(
        verbose_name='Netto',
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    bruttobetrag = tables.Column(
        verbose_name='Brutto',
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    status = tables.Column(
        verbose_name='Status',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    faelligkeit = tables.DateColumn(
        verbose_name='Fälligkeit',
        format='d.m.Y',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    umlagefaehig = tables.BooleanColumn(
        verbose_name='Umlagefähig',
        yesno='✓,✗'
    )
    
    aktionen = tables.Column(
        verbose_name='Aktionen',
        empty_values=(),
        orderable=False,
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    def render_belegnummer(self, value, record):
        """Render belegnummer as a link to detail view."""
        url = reverse('vermietung:eingangsrechnung_detail', args=[record.pk])
        return format_html('<a href="{}" class="text-decoration-none">{}</a>', url, value)
    
    def render_nettobetrag(self, value):
        """Render nettobetrag with currency."""
        if value is None:
            return '—'
        return f'{value:.2f} €'
    
    def render_bruttobetrag(self, value):
        """Render bruttobetrag with currency."""
        if value is None:
            return '—'
        return f'{value:.2f} €'
    
    def render_status(self, value, record):
        """Render status with colored badge."""
        status_classes = {
            'NEU': 'bg-secondary',
            'PRUEFUNG': 'bg-info',
            'OFFEN': 'bg-warning',
            'KLAERUNG': 'bg-danger',
            'BEZAHLT': 'bg-success',
        }
        badge_class = status_classes.get(record.status, 'bg-secondary')
        display_value = record.get_status_display()
        return format_html('<span class="badge {}">{}</span>', badge_class, display_value)
    
    def render_umlagefaehig(self, value):
        """Render umlagefaehig with icon."""
        if value:
            return format_html('<i class="bi bi-check-circle text-success"></i>')
        else:
            return format_html('<i class="bi bi-x-circle text-muted"></i>')
    
    def render_aktionen(self, record):
        """Render action buttons."""
        detail_url = reverse('vermietung:eingangsrechnung_detail', args=[record.pk])
        edit_url = reverse('vermietung:eingangsrechnung_edit', args=[record.pk])
        delete_url = reverse('vermietung:eingangsrechnung_delete', args=[record.pk])
        
        return format_html(
            '<div class="btn-group btn-group-sm" role="group">'
            '<a href="{}" class="btn btn-outline-info" title="Details">'
            '<i class="bi bi-eye"></i></a>'
            '<a href="{}" class="btn btn-outline-warning" title="Bearbeiten">'
            '<i class="bi bi-pencil"></i></a>'
            '<button type="button" class="btn btn-outline-danger" title="Löschen" '
            'onclick="confirmDelete(\'{}\', \'{}\')">'
            '<i class="bi bi-trash"></i></button>'
            '</div>',
            detail_url,
            edit_url,
            record.belegnummer,
            delete_url
        )
    
    class Meta:
        model = Eingangsrechnung
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'belegdatum',
            'belegnummer',
            'lieferant',
            'mietobjekt',
            'betreff',
            'nettobetrag',
            'bruttobetrag',
            'status',
            'faelligkeit',
            'umlagefaehig',
            'aktionen'
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 20

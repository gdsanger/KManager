"""
Django Tables2 table definitions for the core app.
"""
import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from .models import Item


class ItemTable(tables.Table):
    """Table for displaying Items (articles/services)."""
    
    article_no = tables.Column(
        verbose_name='Artikelnummer',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    short_text_1 = tables.Column(
        verbose_name='Kurztext',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 250px;'}}
    )
    
    item_type = tables.Column(
        verbose_name='Typ',
        attrs={'td': {'class': 'text-nowrap'}}
    )
    
    net_price = tables.Column(
        verbose_name='Preis',
        attrs={'td': {'class': 'text-end text-nowrap'}}
    )
    
    is_active = tables.BooleanColumn(
        verbose_name='Aktiv',
        yesno='✓,✗'
    )
    
    item_group = tables.Column(
        verbose_name='Warengruppe',
        accessor='item_group.name',
        order_by='item_group__name'
    )
    
    def render_article_no(self, value, record):
        """Render article_no as a link to select the item."""
        # Link includes the current filters + selected item
        return format_html(
            '<a href="?selected={}&{}" class="text-decoration-none item-link" data-item-id="{}">{}</a>',
            record.pk,
            self.request.GET.urlencode() if hasattr(self, 'request') else '',
            record.pk,
            value
        )
    
    def render_net_price(self, value):
        """Render net_price with currency."""
        if value is None:
            return '—'
        return f'{value:.2f} €'
    
    def render_item_type(self, value, record):
        """Render item_type with badge."""
        type_classes = {
            'MATERIAL': 'bg-primary',
            'SERVICE': 'bg-info',
        }
        badge_class = type_classes.get(record.item_type, 'bg-secondary')
        display_value = record.get_item_type_display()
        return format_html('<span class="badge {}">{}</span>', badge_class, display_value)
    
    def render_is_active(self, value):
        """Render is_active with icon."""
        if value:
            return format_html('<i class="bi bi-check-circle text-success"></i>')
        else:
            return format_html('<i class="bi bi-x-circle text-muted"></i>')
    
    class Meta:
        model = Item
        template_name = 'django_tables2/bootstrap5-dark.html'
        fields = (
            'article_no',
            'short_text_1',
            'item_type',
            'net_price',
            'item_group',
            'is_active'
        )
        attrs = {
            'class': 'table table-dark table-hover',
            'thead': {'class': 'table-dark'}
        }
        per_page = 20

"""
Django Filters for the core app.
"""
import django_filters
from .models import Item, ItemGroup


class ItemFilter(django_filters.FilterSet):
    """Filter for Item list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Artikelnummer, Kurztext...'
        })
    )
    
    group = django_filters.ModelChoiceFilter(
        field_name='item_group',
        queryset=ItemGroup.objects.filter(is_active=True).order_by('code'),
        label='Warengruppe',
        empty_label='Alle Gruppen',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    item_type = django_filters.ChoiceFilter(
        choices=[('', 'Alle Typen')] + list(Item.ITEM_TYPE_CHOICES),
        label='Artikeltyp',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    is_active = django_filters.BooleanFilter(
        label='Aktiv',
        widget=django_filters.widgets.forms.Select(
            choices=[('', 'Alle'), (True, 'Aktiv'), (False, 'Inaktiv')],
            attrs={'class': 'form-select'}
        )
    )
    
    def search_filter(self, queryset, name, value):
        """
        Search across multiple fields.
        """
        from django.db.models import Q
        return queryset.filter(
            Q(article_no__icontains=value) |
            Q(short_text_1__icontains=value) |
            Q(short_text_2__icontains=value) |
            Q(long_text__icontains=value)
        )
    
    class Meta:
        model = Item
        fields = ['q', 'group', 'item_type', 'is_active']

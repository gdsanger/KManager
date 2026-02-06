"""
Django Filters for the auftragsverwaltung app.
"""
import django_filters
from django.db.models import Q
from .models import SalesDocument


class SalesDocumentFilter(django_filters.FilterSet):
    """Filter for SalesDocument list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Nummer, Betreff, Kunde...'
        })
    )
    
    status = django_filters.ChoiceFilter(
        choices=[('', 'Alle Status')] + SalesDocument.STATUS_CHOICES,
        label='Status',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    number = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nummer',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Belegnummer...'
        })
    )
    
    subject = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Betreff',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Betreff...'
        })
    )
    
    issue_date_from = django_filters.DateFilter(
        field_name='issue_date',
        lookup_expr='gte',
        label='Belegdatum von',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    issue_date_to = django_filters.DateFilter(
        field_name='issue_date',
        lookup_expr='lte',
        label='Belegdatum bis',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def search_filter(self, queryset, name, value):
        """
        Full-text search across multiple fields using OR.
        Searches in: number, subject, notes_public, notes_internal
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(number__icontains=value) |
            Q(subject__icontains=value) |
            Q(notes_public__icontains=value) |
            Q(notes_internal__icontains=value)
        )
    
    class Meta:
        model = SalesDocument
        fields = ['q', 'status', 'number', 'subject', 'issue_date_from', 'issue_date_to']

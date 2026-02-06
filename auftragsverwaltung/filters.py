"""
Django Filters for the auftragsverwaltung app.
"""
import django_filters
from django.db.models import Q
from .models import SalesDocument, Contract, TextTemplate


class SalesDocumentFilter(django_filters.FilterSet):
    """Filter for SalesDocument list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Nummer, Betreff, Notizen...'
        })
    )
    
    customer = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        label='Kunde',
        empty_label='Alle Kunden',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
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
    
    def __init__(self, *args, **kwargs):
        """Initialize filter and set up customer queryset."""
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from core.models import Adresse
        # Set customer queryset with ordering by name for easier searching
        self.filters['customer'].queryset = Adresse.objects.all().order_by('name')
    
    class Meta:
        model = SalesDocument
        fields = ['q', 'customer', 'status', 'number', 'subject', 'issue_date_from', 'issue_date_to']


class ContractFilter(django_filters.FilterSet):
    """Filter for Contract list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Name, Kunde...'
        })
    )
    
    is_active = django_filters.ChoiceFilter(
        choices=[('', 'Alle'), ('true', 'Aktiv'), ('false', 'Inaktiv')],
        label='Status',
        empty_label=None,
        method='filter_is_active',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    interval = django_filters.ChoiceFilter(
        choices=[('', 'Alle Intervalle')] + Contract.INTERVAL_CHOICES,
        label='Intervall',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    next_run_date_from = django_filters.DateFilter(
        field_name='next_run_date',
        lookup_expr='gte',
        label='Nächster Lauf von',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    next_run_date_to = django_filters.DateFilter(
        field_name='next_run_date',
        lookup_expr='lte',
        label='Nächster Lauf bis',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def search_filter(self, queryset, name, value):
        """
        Full-text search across multiple fields using OR.
        Searches in: name, customer.name
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(name__icontains=value) |
            Q(customer__name__icontains=value)
        )
    
    def filter_is_active(self, queryset, name, value):
        """Filter for is_active field."""
        if value == 'true':
            return queryset.filter(is_active=True)
        elif value == 'false':
            return queryset.filter(is_active=False)
        return queryset
    
    class Meta:
        model = Contract
        fields = ['q', 'is_active', 'interval', 'next_run_date_from', 'next_run_date_to']


class TextTemplateFilter(django_filters.FilterSet):
    """Filter for TextTemplate list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Titel, Schlüssel, Inhalt...'
        })
    )
    
    type = django_filters.ChoiceFilter(
        choices=[('', 'Alle Typen')] + TextTemplate.TYPE_CHOICES,
        label='Typ',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    is_active = django_filters.ChoiceFilter(
        choices=[('', 'Alle'), ('true', 'Aktiv'), ('false', 'Inaktiv')],
        label='Status',
        empty_label=None,
        method='filter_is_active',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    def search_filter(self, queryset, name, value):
        """
        Full-text search across multiple fields using OR.
        Searches in: title, key, content
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) |
            Q(key__icontains=value) |
            Q(content__icontains=value)
        )
    
    def filter_is_active(self, queryset, name, value):
        """Filter for is_active field."""
        if value == 'true':
            return queryset.filter(is_active=True)
        elif value == 'false':
            return queryset.filter(is_active=False)
        return queryset
    
    class Meta:
        model = TextTemplate
        fields = ['q', 'type', 'is_active']

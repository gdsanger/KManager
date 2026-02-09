"""
Django Filters for the auftragsverwaltung app.
"""
import django_filters
from django.db.models import Q
from .models import SalesDocument, Contract, TextTemplate, TimeEntry
from finanzen.models import OutgoingInvoiceJournalEntry


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


class OutgoingInvoiceJournalFilter(django_filters.FilterSet):
    """Filter for OutgoingInvoiceJournalEntry list view."""
    
    customer_name = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Kunde',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Kundenname...'
        })
    )
    
    export_status = django_filters.ChoiceFilter(
        choices=[('', 'Alle Status')] + OutgoingInvoiceJournalEntry.EXPORT_STATUS_CHOICES,
        label='Status',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    company = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        label='Mandant',
        empty_label='Alle Mandanten',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    def __init__(self, *args, **kwargs):
        """Initialize filter and set up company queryset."""
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from core.models import Mandant
        # Set company queryset with ordering by name
        self.filters['company'].queryset = Mandant.objects.all().order_by('name')
    
    class Meta:
        model = OutgoingInvoiceJournalEntry
        fields = ['customer_name', 'export_status', 'company']


class TimeEntryFilter(django_filters.FilterSet):
    """Filter for TimeEntry list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Beschreibung, Auftragsnummer, Kunde...'
        })
    )
    
    service_date_from = django_filters.DateFilter(
        field_name='service_date',
        lookup_expr='gte',
        label='Leistungsdatum von',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    service_date_to = django_filters.DateFilter(
        field_name='service_date',
        lookup_expr='lte',
        label='Leistungsdatum bis',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
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
    
    order = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        label='Auftrag',
        empty_label='Alle Aufträge',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    performed_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set in __init__
        label='Benutzer',
        empty_label='Alle Benutzer',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    is_travel_cost = django_filters.ChoiceFilter(
        choices=[('', 'Alle'), ('true', 'Ja'), ('false', 'Nein')],
        label='Anfahrt',
        empty_label=None,
        method='filter_is_travel_cost',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    is_billed = django_filters.ChoiceFilter(
        choices=[('', 'Alle'), ('true', 'Ja'), ('false', 'Nein')],
        label='Abgerechnet',
        empty_label=None,
        method='filter_is_billed',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    def search_filter(self, queryset, name, value):
        """
        Full-text search across multiple fields using OR.
        Searches in: description, order.number, order.subject, customer.name
        """
        if not value:
            return queryset
        
        return queryset.filter(
            Q(description__icontains=value) |
            Q(order__number__icontains=value) |
            Q(order__subject__icontains=value) |
            Q(customer__name__icontains=value)
        )
    
    def filter_is_travel_cost(self, queryset, name, value):
        """Filter for is_travel_cost field."""
        if value == 'true':
            return queryset.filter(is_travel_cost=True)
        elif value == 'false':
            return queryset.filter(is_travel_cost=False)
        return queryset
    
    def filter_is_billed(self, queryset, name, value):
        """Filter for is_billed field."""
        if value == 'true':
            return queryset.filter(is_billed=True)
        elif value == 'false':
            return queryset.filter(is_billed=False)
        return queryset
    
    def __init__(self, *args, **kwargs):
        """Initialize filter and set up querysets."""
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from core.models import Adresse
        from django.contrib.auth.models import User
        
        # Set customer queryset with ordering by name
        self.filters['customer'].queryset = Adresse.objects.filter(
            adressen_type='KUNDE'
        ).order_by('name')
        
        # Set order queryset - only orders
        self.filters['order'].queryset = SalesDocument.objects.filter(
            document_type__key__iexact='order'
        ).order_by('-issue_date')
        
        # Set performed_by queryset with ordering by username
        self.filters['performed_by'].queryset = User.objects.all().order_by('username')
    
    class Meta:
        model = TimeEntry
        fields = [
            'q', 'service_date_from', 'service_date_to', 
            'customer', 'order', 'performed_by', 
            'is_travel_cost', 'is_billed'
        ]

"""
Django Filters for the vermietung app.
"""
import django_filters
from .models import Eingangsrechnung, MietObjekt, EINGANGSRECHNUNG_STATUS


class EingangsrechnungFilter(django_filters.FilterSet):
    """Filter for Eingangsrechnung list view."""
    
    q = django_filters.CharFilter(
        method='search_filter',
        label='Suche',
        widget=django_filters.widgets.forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Suche nach Belegnummer, Betreff, Lieferant...'
        })
    )
    
    status = django_filters.ChoiceFilter(
        choices=[('', 'Alle Status')] + list(EINGANGSRECHNUNG_STATUS),
        label='Status',
        empty_label=None,
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    mietobjekt = django_filters.ModelChoiceFilter(
        queryset=MietObjekt.objects.all().order_by('name'),
        label='Mietobjekt',
        empty_label='Alle Objekte',
        widget=django_filters.widgets.forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    umlagefaehig = django_filters.BooleanFilter(
        label='Umlagefähig',
        widget=django_filters.widgets.forms.Select(
            choices=[('', 'Alle'), (True, 'Ja'), (False, 'Nein')],
            attrs={'class': 'form-select'}
        )
    )
    
    belegdatum_von = django_filters.DateFilter(
        field_name='belegdatum',
        lookup_expr='gte',
        label='Belegdatum von',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    belegdatum_bis = django_filters.DateFilter(
        field_name='belegdatum',
        lookup_expr='lte',
        label='Belegdatum bis',
        widget=django_filters.widgets.forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def search_filter(self, queryset, name, value):
        """
        Search across multiple fields.
        """
        from django.db.models import Q
        return queryset.filter(
            Q(belegnummer__icontains=value) |
            Q(betreff__icontains=value) |
            Q(lieferant__name__icontains=value) |
            Q(referenznummer__icontains=value)
        )
    
    class Meta:
        model = Eingangsrechnung
        fields = ['q', 'status', 'mietobjekt', 'umlagefaehig', 'belegdatum_von', 'belegdatum_bis']

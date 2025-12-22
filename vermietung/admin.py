from django.contrib import admin
from django import forms
from .models import MietObjekt, Vertrag, OBJEKT_TYPE
from core.models import Adresse


class VertragAdminForm(forms.ModelForm):
    """
    Custom form for Vertrag admin to restrict Mieter selection to KUNDE addresses.
    """
    class Meta:
        model = Vertrag
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict mieter choices to only KUNDE addresses
        self.fields['mieter'].queryset = Adresse.objects.filter(adressen_type='KUNDE')


@admin.register(MietObjekt)
class MietObjektAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'beschreibung', 'fläche', 'höhe', 'breite', 'tiefe', 'standort', 'mietpreis', 'verfuegbar')
    search_fields = ('name', 'standort__strasse', 'standort__ort', 'standort')
    list_filter = ('type', 'verfuegbar', 'standort')


@admin.register(Vertrag)
class VertragAdmin(admin.ModelAdmin):
    form = VertragAdminForm
    list_display = ('vertragsnummer', 'mietobjekt', 'mieter', 'start', 'ende', 'miete', 'kaution')
    search_fields = ('vertragsnummer', 'mietobjekt__name', 'mieter__name', 'mieter__firma')
    list_filter = ('start', 'ende', 'mietobjekt')
    readonly_fields = ('vertragsnummer',)
    
    fieldsets = (
        ('Vertragsdetails', {
            'fields': ('vertragsnummer', 'mietobjekt', 'mieter')
        }),
        ('Zeitraum', {
            'fields': ('start', 'ende')
        }),
        ('Finanzielle Details', {
            'fields': ('miete', 'kaution')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by prefetching related objects."""
        queryset = super().get_queryset(request)
        return queryset.select_related('mieter', 'mietobjekt')
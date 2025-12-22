from django.contrib import admin
from django import forms
from .models import MietObjekt, Vertrag, Uebergabeprotokoll, OBJEKT_TYPE
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


@admin.register(Uebergabeprotokoll)
class UebergabeprotokollAdmin(admin.ModelAdmin):
    list_display = ('vertrag', 'mietobjekt', 'typ', 'uebergabetag', 'anzahl_schluessel', 'person_vermieter', 'person_mieter')
    search_fields = ('vertrag__vertragsnummer', 'mietobjekt__name', 'person_vermieter', 'person_mieter', 'bemerkungen', 'maengel')
    list_filter = ('typ', 'uebergabetag', 'mietobjekt', 'vertrag')
    date_hierarchy = 'uebergabetag'
    
    fieldsets = (
        ('Vertragsdetails', {
            'fields': ('vertrag', 'mietobjekt', 'typ', 'uebergabetag')
        }),
        ('Zählerstände', {
            'fields': ('zaehlerstand_strom', 'zaehlerstand_gas', 'zaehlerstand_wasser')
        }),
        ('Schlüssel', {
            'fields': ('anzahl_schluessel',)
        }),
        ('Bemerkungen und Mängel', {
            'fields': ('bemerkungen', 'maengel')
        }),
        ('Beteiligte Personen', {
            'fields': ('person_vermieter', 'person_mieter')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by prefetching related objects."""
        queryset = super().get_queryset(request)
        return queryset.select_related('vertrag', 'mietobjekt')
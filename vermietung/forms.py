"""
Forms for the Vermietung (Rental Management) area.
"""

from django import forms
from core.models import Adresse
from .models import MietObjekt, OBJEKT_TYPE


class MietObjektForm(forms.ModelForm):
    """
    Form for creating/editing MietObjekt (rental objects).
    Includes all fields with proper Bootstrap 5 styling.
    """
    
    class Meta:
        model = MietObjekt
        fields = [
            'name',
            'type',
            'beschreibung',
            'fläche',
            'höhe',
            'breite',
            'tiefe',
            'standort',
            'mietpreis',
            'nebenkosten',
            'kaution',
            'verfuegbar'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'beschreibung': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'fläche': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'höhe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'breite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tiefe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'standort': forms.Select(attrs={'class': 'form-select'}),
            'mietpreis': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'nebenkosten': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'kaution': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'verfuegbar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Name *',
            'type': 'Typ *',
            'beschreibung': 'Beschreibung *',
            'fläche': 'Fläche (m²)',
            'höhe': 'Höhe (m)',
            'breite': 'Breite (m)',
            'tiefe': 'Tiefe (m)',
            'standort': 'Standort *',
            'mietpreis': 'Mietpreis (€) *',
            'nebenkosten': 'Nebenkosten (€)',
            'kaution': 'Kaution (€)',
            'verfuegbar': 'Verfügbar',
        }
        help_texts = {
            'kaution': 'Standard: 3x Mietpreis (wird automatisch vorausgefüllt)',
            'verfuegbar': 'Wird automatisch basierend auf aktiven Verträgen aktualisiert',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter standort to only show STANDORT addresses
        self.fields['standort'].queryset = Adresse.objects.filter(adressen_type='STANDORT').order_by('name')


class AdresseKundeForm(forms.ModelForm):
    """
    Form for creating/editing addresses of type KUNDE (Customer).
    The adressen_type field is fixed to KUNDE and not editable by the user.
    """
    
    class Meta:
        model = Adresse
        fields = [
            'firma',
            'anrede',
            'name',
            'strasse',
            'plz',
            'ort',
            'land',
            'telefon',
            'mobil',
            'email',
            'bemerkung'
        ]
        widgets = {
            'firma': forms.TextInput(attrs={'class': 'form-control'}),
            'anrede': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'strasse': forms.TextInput(attrs={'class': 'form-control'}),
            'plz': forms.TextInput(attrs={'class': 'form-control'}),
            'ort': forms.TextInput(attrs={'class': 'form-control'}),
            'land': forms.TextInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'mobil': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bemerkung': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'firma': 'Firma (optional)',
            'anrede': 'Anrede (optional)',
            'name': 'Name *',
            'strasse': 'Straße *',
            'plz': 'PLZ *',
            'ort': 'Ort *',
            'land': 'Land *',
            'telefon': 'Telefon (optional)',
            'mobil': 'Mobil (optional)',
            'email': 'E-Mail (optional)',
            'bemerkung': 'Bemerkung (optional)',
        }
    
    def save(self, commit=True):
        """
        Override save to ensure adressen_type is always set to KUNDE.
        """
        instance = super().save(commit=False)
        instance.adressen_type = 'KUNDE'
        if commit:
            instance.save()
        return instance

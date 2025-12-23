"""
Forms for the Vermietung (Rental Management) area.
"""

from django import forms
from core.models import Adresse


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

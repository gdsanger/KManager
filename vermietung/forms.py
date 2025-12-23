"""
Forms for the Vermietung (Rental Management) area.
"""

from django import forms
from django.core.exceptions import ValidationError
from core.models import Adresse
from .models import MietObjekt, Vertrag, Uebergabeprotokoll, OBJEKT_TYPE


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


class VertragForm(forms.ModelForm):
    """
    Form for creating/editing Vertrag (rental contracts).
    Includes all fields with proper Bootstrap 5 styling.
    Contract number is auto-generated and not editable.
    """
    
    class Meta:
        model = Vertrag
        fields = [
            'mietobjekt',
            'mieter',
            'start',
            'ende',
            'miete',
            'kaution',
            'status',
        ]
        widgets = {
            'mietobjekt': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_mietobjekt',
            }),
            'mieter': forms.Select(attrs={'class': 'form-select'}),
            'start': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'ende': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'miete': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'id_miete',
            }),
            'kaution': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'id_kaution',
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'mietobjekt': 'Mietobjekt *',
            'mieter': 'Mieter (Kunde) *',
            'start': 'Vertragsbeginn *',
            'ende': 'Vertragsende',
            'miete': 'Monatliche Miete (€) *',
            'kaution': 'Kaution (€) *',
            'status': 'Status *',
        }
        help_texts = {
            'mietobjekt': 'Wählen Sie das zu vermietende Objekt aus',
            'mieter': 'Nur Adressen vom Typ "Kunde" können ausgewählt werden',
            'start': 'Startdatum des Vertrags',
            'ende': 'Optional: Enddatum des Vertrags (leer = unbefristet)',
            'miete': 'Monatliche Miete in EUR',
            'kaution': 'Kaution in EUR (wird aus Mietobjekt vorausgefüllt)',
            'status': 'Status des Vertrags',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter mieter to only show KUNDE addresses
        self.fields['mieter'].queryset = Adresse.objects.filter(
            adressen_type='KUNDE'
        ).order_by('name')
        
        # Order mietobjekte by name
        self.fields['mietobjekt'].queryset = MietObjekt.objects.all().order_by('name')
        
        # Pre-fill miete and kaution from mietobjekt if creating new contract
        if not self.instance.pk and 'mietobjekt' in self.initial:
            try:
                mietobjekt = MietObjekt.objects.get(pk=self.initial['mietobjekt'])
                if 'miete' not in self.initial:
                    self.initial['miete'] = mietobjekt.mietpreis
                if 'kaution' not in self.initial and mietobjekt.kaution:
                    self.initial['kaution'] = mietobjekt.kaution
            except MietObjekt.DoesNotExist:
                pass
    
    def clean(self):
        """
        Additional validation to warn about unavailable rental objects.
        The model's clean method will handle overlap validation.
        """
        cleaned_data = super().clean()
        mietobjekt = cleaned_data.get('mietobjekt')
        
        # Add warning if mietobjekt is not available (but don't prevent saving)
        # This is just a UX improvement - the model validation will catch overlaps
        if mietobjekt and not mietobjekt.verfuegbar:
            # We use add_error with None as field to add a non-field warning
            # But we'll let the model's overlap validation be the final say
            pass
        
        return cleaned_data


class VertragEndForm(forms.Form):
    """
    Form for ending a contract by setting the end date.
    """
    ende = forms.DateField(
        label='Vertragsende',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        help_text='Datum an dem der Vertrag beendet werden soll'
    )
    
    def __init__(self, *args, vertrag=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vertrag = vertrag
        
        # Set initial value to today if not provided
        if not self.initial.get('ende'):
            from django.utils import timezone
            self.initial['ende'] = timezone.now().date()
    
    def clean_ende(self):
        """Validate that end date is after start date."""
        ende = self.cleaned_data.get('ende')
        
        if self.vertrag and ende:
            if ende <= self.vertrag.start:
                raise ValidationError(
                    f'Das Enddatum muss nach dem Vertragsbeginn ({self.vertrag.start}) liegen.'
                )
        
        return ende


class UebergabeprotokollForm(forms.ModelForm):
    """
    Form for creating/editing Uebergabeprotokoll (handover protocols).
    Includes all fields with proper Bootstrap 5 styling.
    """
    
    class Meta:
        model = Uebergabeprotokoll
        fields = [
            'vertrag',
            'mietobjekt',
            'typ',
            'uebergabetag',
            'zaehlerstand_strom',
            'zaehlerstand_gas',
            'zaehlerstand_wasser',
            'anzahl_schluessel',
            'bemerkungen',
            'maengel',
            'person_vermieter',
            'person_mieter',
        ]
        widgets = {
            'vertrag': forms.Select(attrs={'class': 'form-select'}),
            'mietobjekt': forms.Select(attrs={'class': 'form-select'}),
            'typ': forms.Select(attrs={'class': 'form-select'}),
            'uebergabetag': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'zaehlerstand_strom': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'zaehlerstand_gas': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'zaehlerstand_wasser': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'anzahl_schluessel': forms.NumberInput(attrs={
                'class': 'form-control',
            }),
            'bemerkungen': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
            }),
            'maengel': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
            }),
            'person_vermieter': forms.TextInput(attrs={'class': 'form-control'}),
            'person_mieter': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'vertrag': 'Vertrag *',
            'mietobjekt': 'Mietobjekt *',
            'typ': 'Typ *',
            'uebergabetag': 'Übergabedatum *',
            'zaehlerstand_strom': 'Zählerstand Strom (kWh)',
            'zaehlerstand_gas': 'Zählerstand Gas (m³)',
            'zaehlerstand_wasser': 'Zählerstand Wasser (m³)',
            'anzahl_schluessel': 'Anzahl Schlüssel',
            'bemerkungen': 'Bemerkungen',
            'maengel': 'Mängel',
            'person_vermieter': 'Person Vermieter',
            'person_mieter': 'Person Mieter',
        }
        help_texts = {
            'vertrag': 'Vertrag zu dem dieses Protokoll gehört',
            'mietobjekt': 'Muss zum ausgewählten Vertrag passen',
            'typ': 'Einzug oder Auszug',
            'uebergabetag': 'Datum der Übergabe',
        }
    
    def __init__(self, *args, vertrag=None, **kwargs):
        """
        Initialize form with optional pre-selected vertrag.
        If vertrag is provided, pre-fill mietobjekt and make fields read-only.
        """
        super().__init__(*args, **kwargs)
        
        # If vertrag is provided (create from vertrag flow), pre-fill and restrict
        if vertrag:
            self.fields['vertrag'].initial = vertrag
            self.fields['vertrag'].widget.attrs['readonly'] = True
            self.fields['vertrag'].disabled = True
            
            # Pre-fill mietobjekt from vertrag
            self.fields['mietobjekt'].initial = vertrag.mietobjekt
            self.fields['mietobjekt'].widget.attrs['readonly'] = True
            self.fields['mietobjekt'].disabled = True
            
            # Limit queryset to just this vertrag's mietobjekt
            self.fields['mietobjekt'].queryset = MietObjekt.objects.filter(pk=vertrag.mietobjekt_id)
        
        # Order vertraege by vertragsnummer
        self.fields['vertrag'].queryset = Vertrag.objects.select_related(
            'mieter'
        ).order_by('-start')
        
        # Order mietobjekte by name
        if not vertrag:
            self.fields['mietobjekt'].queryset = MietObjekt.objects.all().order_by('name')

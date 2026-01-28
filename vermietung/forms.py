"""
Forms for the Vermietung (Rental Management) area.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from core.models import Adresse, Mandant
from .models import (
    MietObjekt, Vertrag, Uebergabeprotokoll, Dokument, MietObjektBild, 
    Aktivitaet, VertragsObjekt, Zaehler, Zaehlerstand, OBJEKT_TYPE,
    Eingangsrechnung, EingangsrechnungAufteilung
)
User = get_user_model()

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
            'verfuegbare_einheiten',
            'volumen',
            'verfuegbar',
            'mandant',
            'parent'
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
            'verfuegbare_einheiten': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'volumen': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'verfuegbar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mandant': forms.Select(attrs={'class': 'form-select'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
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
            'verfuegbare_einheiten': 'Verfügbare Einheiten',
            'volumen': 'Volumen (m³)',
            'verfuegbar': 'Verfügbar',
            'mandant': 'Mandant',
            'parent': 'Übergeordnetes Mietobjekt',
        }
        help_texts = {
            'kaution': 'Standard: 3x Mietpreis (wird automatisch vorausgefüllt)',
            'verfuegbare_einheiten': 'Anzahl der verfügbaren Einheiten (Standard: 1)',
            'volumen': 'Optional: Volumen überschreiben (wird aus H×B×T berechnet)',
            'verfuegbar': 'Wird automatisch basierend auf aktiven Verträgen aktualisiert',
            'mandant': 'Optional: Zugeordneter Mandant für dieses Mietobjekt',
            'parent': 'Optional: Übergeordnetes Mietobjekt (z.B. Gebäude für eine Wohnung)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter standort to only show STANDORT addresses
        self.fields['standort'].queryset = Adresse.objects.filter(adressen_type='STANDORT').order_by('name')
        # Order mandanten by name
        self.fields['mandant'].queryset = Mandant.objects.all().order_by('name')
        
        # Filter parent field to exclude self (when editing) and all descendants
        if self.instance and self.instance.pk:
            # Exclude self and all descendants to prevent circular references
            descendants = self.instance.get_all_children(include_self=True)
            self.fields['parent'].queryset = MietObjekt.objects.exclude(
                pk__in=descendants.values_list('pk', flat=True)
            ).order_by('name')
        else:
            # For new objects, show all MietObjekte
            self.fields['parent'].queryset = MietObjekt.objects.all().order_by('name')



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


class AdresseStandortForm(forms.ModelForm):
    """
    Form for creating/editing addresses of type STANDORT (Location).
    The adressen_type field is fixed to STANDORT and not editable by the user.
    """
    
    class Meta:
        model = Adresse
        fields = [
            'name',
            'strasse',
            'plz',
            'ort',
            'land',
            'telefon',
            'email',
            'bemerkung'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'strasse': forms.TextInput(attrs={'class': 'form-control'}),
            'plz': forms.TextInput(attrs={'class': 'form-control'}),
            'ort': forms.TextInput(attrs={'class': 'form-control'}),
            'land': forms.TextInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'bemerkung': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Standortname *',
            'strasse': 'Straße *',
            'plz': 'PLZ *',
            'ort': 'Ort *',
            'land': 'Land *',
            'telefon': 'Telefon (optional)',
            'email': 'E-Mail (optional)',
            'bemerkung': 'Bemerkung (optional)',
        }
    
    def save(self, commit=True):
        """
        Override save to ensure adressen_type is always set to STANDORT.
        """
        instance = super().save(commit=False)
        instance.adressen_type = 'STANDORT'
        if commit:
            instance.save()
        return instance


class AdresseLieferantForm(forms.ModelForm):
    """
    Form for creating/editing addresses of type LIEFERANT (Supplier).
    The adressen_type field is fixed to LIEFERANT and not editable by the user.
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
        Override save to ensure adressen_type is always set to LIEFERANT.
        """
        instance = super().save(commit=False)
        instance.adressen_type = 'LIEFERANT'
        if commit:
            instance.save()
        return instance


class AdresseForm(forms.ModelForm):
    """
    Form for creating/editing addresses of type Adresse (generic address).
    The adressen_type field is fixed to Adresse and not editable by the user.
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
        Override save to ensure adressen_type is always set to Adresse.
        """
        instance = super().save(commit=False)
        instance.adressen_type = 'Adresse'
        if commit:
            instance.save()
        return instance


class VertragsObjektForm(forms.ModelForm):
    """
    Form for creating/editing VertragsObjekt (rental object assignment in a contract).
    Used in inline formset for managing multiple rental objects in a contract.
    """
    
    class Meta:
        model = VertragsObjekt
        fields = ['mietobjekt', 'preis', 'anzahl', 'zugang', 'abgang', 'status']
        widgets = {
            'mietobjekt': forms.Select(attrs={
                'class': 'form-select form-select-sm mietobjekt-select',
            }),
            'preis': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm preis-input',
                'step': '0.01',
                'min': '0',
            }),
            'anzahl': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm anzahl-input',
                'min': '1',
                'value': '1',
            }),
            'zugang': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date',
            }),
            'abgang': forms.DateInput(attrs={
                'class': 'form-control form-control-sm',
                'type': 'date',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select form-select-sm',
            }),
        }
        labels = {
            'mietobjekt': 'Mietobjekt',
            'preis': 'Preis (€)',
            'anzahl': 'Anzahl',
            'zugang': 'Zugang',
            'abgang': 'Abgang',
            'status': 'Status',
        }
        help_texts = {
            'preis': 'Preis pro Einheit',
            'anzahl': 'Anzahl der Einheiten',
            'zugang': 'Datum der Übergabe/Übernahme (optional)',
            'abgang': 'Datum der Rückgabe (optional)',
            'status': 'Status dieses Objekts',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order mietobjekte by name
        self.fields['mietobjekt'].queryset = MietObjekt.objects.all().order_by('name')
        
        # Pre-fill preis from mietobjekt if creating new
        if not self.instance.pk and self.initial.get('mietobjekt'):
            try:
                mietobjekt = MietObjekt.objects.get(pk=self.initial['mietobjekt'])
                self.initial['preis'] = mietobjekt.mietpreis
            except (MietObjekt.DoesNotExist, KeyError):
                pass


class VertragForm(forms.ModelForm):
    """
    Form for creating/editing Vertrag (rental contracts).
    Includes all fields with proper Bootstrap 5 styling.
    Contract number is auto-generated and not editable.
    Rental objects are managed separately via VertragsObjektFormSet.
    """
    
    class Meta:
        model = Vertrag
        fields = [
            'mieter',
            'start',
            'ende',
            'miete',
            'kaution',
            'umsatzsteuer_satz',
            'status',
            'mandant',
        ]
        widgets = {
            'mieter': forms.Select(attrs={'class': 'form-select'}),
            'start': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }, format='%Y-%m-%d'),
            'ende': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }, format='%Y-%m-%d'),
            'miete': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'id_miete',
                'readonly': 'readonly',
            }),
            'kaution': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'id_kaution',
            }),
            'umsatzsteuer_satz': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'mandant': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'mieter': 'Mieter (Kunde) *',
            'start': 'Vertragsbeginn *',
            'ende': 'Vertragsende',
            'miete': 'Gesamtmiete (€) (Netto)',
            'kaution': 'Kaution (€) *',
            'umsatzsteuer_satz': 'Umsatzsteuer *',
            'status': 'Status *',
            'mandant': 'Mandant',
        }
        help_texts = {
            'mieter': 'Nur Adressen vom Typ "Kunde" können ausgewählt werden',
            'start': 'Startdatum des Vertrags',
            'ende': 'Optional: Enddatum des Vertrags (leer = unbefristet)',
            'miete': 'Wird automatisch aus den Mietobjekten berechnet (Summe aus Anzahl × Preis)',
            'kaution': 'Kaution in EUR',
            'umsatzsteuer_satz': 'Umsatzsteuersatz für die Berechnung des Bruttobetrags',
            'status': 'Status des Vertrags',
            'mandant': 'Optional: Zugeordneter Mandant (wird vom Mietobjekt übernommen wenn leer)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter mieter to only show KUNDE addresses
        self.fields['mieter'].queryset = Adresse.objects.filter(
            adressen_type='KUNDE'
        ).order_by('name')
        
        # Make miete field not required since it will be calculated
        self.fields['miete'].required = False
        
        # Order mandanten by name
        self.fields['mandant'].queryset = Mandant.objects.all().order_by('name')


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
        If vertrag is provided, restrict mietobjekt choices to those in the vertrag.
        """
        super().__init__(*args, **kwargs)
        
        # If vertrag is provided (create from vertrag flow), pre-fill and restrict
        if vertrag:
            self.fields['vertrag'].initial = vertrag
            self.fields['vertrag'].widget.attrs['readonly'] = True
            self.fields['vertrag'].disabled = True
            
            # Limit queryset to mietobjekte in this vertrag
            vertrag_mietobjekte = vertrag.get_mietobjekte()
            self.fields['mietobjekt'].queryset = vertrag_mietobjekte
            
            # Pre-fill with first mietobjekt if available
            first_mietobjekt = vertrag_mietobjekte.first()
            if first_mietobjekt:
                self.fields['mietobjekt'].initial = first_mietobjekt
        
        # Order vertraege by vertragsnummer
        self.fields['vertrag'].queryset = Vertrag.objects.select_related(
            'mieter'
        ).order_by('-start')
        
        # Order mietobjekte by name if vertrag is not set
        if not vertrag:
            self.fields['mietobjekt'].queryset = MietObjekt.objects.all().order_by('name')


class DokumentUploadForm(forms.ModelForm):
    """
    Form for uploading documents.
    Allows uploading a file and optional description.
    The entity (Vertrag, MietObjekt, Adresse, Uebergabeprotokoll) is set programmatically.
    """
    
    # Mapping of entity types to foreign key field names
    # Used in _post_clean() to set FK before validation and in save() as fallback
    ENTITY_TO_FK_MAPPING = {
        'vertrag': 'vertrag_id',
        'mietobjekt': 'mietobjekt_id',
        'adresse': 'adresse_id',
        'uebergabeprotokoll': 'uebergabeprotokoll_id',
    }
    
    file = forms.FileField(
        label='Datei',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.png,.jpg,.jpeg,.gif,.docx,.webp'
        }),
        help_text='Erlaubte Dateitypen: PDF, PNG, JPG/JPEG, GIF, WebP, DOCX. Maximale Größe: 10 MB'
    )
    
    class Meta:
        model = Dokument
        fields = ['beschreibung']
        widgets = {
            'beschreibung': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional: Beschreibung des Dokuments'
            }),
        }
        labels = {
            'beschreibung': 'Beschreibung (optional)',
        }
    
    def __init__(self, *args, entity_type=None, entity_id=None, user=None, **kwargs):
        """
        Initialize form with entity type and ID.
        
        Args:
            entity_type: Type of entity (vertrag, mietobjekt, adresse, uebergabeprotokoll)
            entity_id: ID of the entity
            user: User who is uploading the file
        """
        super().__init__(*args, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.user = user
    
    def _post_clean(self):
        """
        Override to set foreign key before model validation.
        
        This is necessary because Django's ModelForm validation calls full_clean() on the model instance
        during is_valid(), but the foreign key is not part of the form fields (only set programmatically).
        Setting the foreign key here ensures validation passes before model.full_clean() is called.
        """
        # Set the foreign key on the instance before validation
        if self.entity_type and self.entity_id:
            fk_field = self.ENTITY_TO_FK_MAPPING.get(self.entity_type)
            if fk_field:
                setattr(self.instance, fk_field, self.entity_id)
            else:
                # This should never happen if the view is using the form correctly
                raise ValueError(
                    f'Unknown entity_type "{self.entity_type}". '
                    f'Must be one of: {", ".join(self.ENTITY_TO_FK_MAPPING.keys())}'
                )
        
        # Now call parent's _post_clean which will call full_clean() on the instance
        super()._post_clean()
    
    def save(self, commit=True):
        """
        Save the document with uploaded file.
        Handles file storage and metadata.
        
        The foreign key is normally set in _post_clean() during is_valid() to ensure
        validation passes. However, a fallback mechanism sets the FK here if _post_clean()
        wasn't called, allowing save() to work even without prior is_valid() call.
        """
        instance = super().save(commit=False)
        
        # Get uploaded file
        uploaded_file = self.cleaned_data['file']
        
        # Save file to filesystem and get storage path and MIME type
        storage_path, mime_type = Dokument.save_uploaded_file(
            uploaded_file,
            self.entity_type,
            self.entity_id
        )
        
        # Set document metadata
        instance.original_filename = uploaded_file.name
        instance.storage_path = storage_path
        instance.file_size = uploaded_file.size
        instance.mime_type = mime_type
        instance.uploaded_by = self.user
        
        # Foreign key is already set in _post_clean() which runs during is_valid()
        # Safety check: Ensure foreign key is set (fallback if is_valid() wasn't called)
        if not any([instance.vertrag_id, instance.mietobjekt_id, 
                    instance.adresse_id, instance.uebergabeprotokoll_id]):
            # Fallback mechanism: set FK here if _post_clean() wasn't called
            if self.entity_type and self.entity_id:
                fk_field = self.ENTITY_TO_FK_MAPPING.get(self.entity_type)
                if fk_field:
                    setattr(instance, fk_field, self.entity_id)
        
        if commit:
            instance.save()
        
        return instance


class MietObjektBildUploadForm(forms.Form):
    """
    Form for uploading images to MietObjekt gallery.
    Supports multiple file upload.
    """
    
    bilder = forms.FileField(
        label='Bilder',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/png,image/jpeg,image/gif,image/webp,.png,.jpg,.jpeg,.gif,.webp',
        }),
        help_text='Erlaubte Bildtypen: PNG, JPG/JPEG, GIF, WEBP. Maximale Größe: 10 MB pro Bild. Sie können mehrere Bilder gleichzeitig hochladen.',
        required=True
    )
    
    def __init__(self, *args, mietobjekt=None, user=None, **kwargs):
        """
        Initialize form with mietobjekt and user.
        
        Args:
            mietobjekt: MietObjekt instance to upload images for
            user: User who is uploading the images
        """
        super().__init__(*args, **kwargs)
        self.mietobjekt = mietobjekt
        self.user = user
        # Set multiple attribute on the widget after initialization
        self.fields['bilder'].widget.attrs['multiple'] = True
    
    def clean_bilder(self):
        """Validate that files are uploaded."""
        # Note: Multiple files are handled in the view
        return self.cleaned_data.get('bilder')
    
    def save(self, files):
        """
        Save uploaded images.
        
        Args:
            files: List of uploaded files
        
        Returns:
            List of created MietObjektBild instances
        """
        bilder = []
        errors = []
        
        for uploaded_file in files:
            try:
                bild = MietObjektBild.save_uploaded_image(
                    uploaded_file,
                    self.mietobjekt.pk,
                    self.user
                )
                bilder.append(bild)
            except ValidationError as e:
                # Collect errors but continue with other files
                error_message = str(e)
                if hasattr(e, 'messages') and e.messages:
                    error_message = '; '.join(e.messages) if isinstance(e.messages, list) else str(e.messages)
                errors.append(f'{uploaded_file.name}: {error_message}')
        
        # If there were errors, raise them
        if errors:
            raise ValidationError(errors)
        
        return bilder


class AktivitaetForm(forms.ModelForm):
    """
    Form for creating/editing Aktivitaet (activities/tasks).
    Supports context-based creation where context fields are pre-filled and locked.
    """
    
    class Meta:
        model = Aktivitaet
        fields = [
            'titel',
            'beschreibung',
            'status',
            'prioritaet',
            'faellig_am',
            'assigned_user',
            'assigned_supplier',
            'ersteller',
            'ist_serie',
            'intervall_monate',
            'mietobjekt',
            'vertrag',
            'kunde',
        ]
        widgets = {
            'titel': forms.TextInput(attrs={'class': 'form-control'}),
            'beschreibung': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'prioritaet': forms.Select(attrs={'class': 'form-select'}),
            'faellig_am': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'assigned_user': forms.Select(attrs={'class': 'form-select'}),
            'assigned_supplier': forms.Select(attrs={'class': 'form-select'}),
            'ersteller': forms.Select(attrs={'class': 'form-select'}),
            'ist_serie': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_ist_serie'}),
            'intervall_monate': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '12', 'id': 'id_intervall_monate'}),
            'mietobjekt': forms.Select(attrs={'class': 'form-select', 'id': 'id_mietobjekt'}),
            'vertrag': forms.Select(attrs={'class': 'form-select', 'id': 'id_vertrag'}),
            'kunde': forms.Select(attrs={'class': 'form-select', 'id': 'id_kunde'}),
        }
        labels = {
            'titel': 'Titel *',
            'beschreibung': 'Beschreibung',
            'status': 'Status *',
            'prioritaet': 'Priorität *',
            'faellig_am': 'Fällig am',
            'assigned_user': 'Interner Verantwortlicher',
            'assigned_supplier': 'Lieferant',
            'ersteller': 'Ersteller',
            'ist_serie': 'Serien-Aktivität',
            'intervall_monate': 'Intervall (Monate)',
            'mietobjekt': 'Mietobjekt',
            'vertrag': 'Vertrag',
            'kunde': 'Kunde',
        }
        help_texts = {
            'assigned_user': 'Optional: Interner Benutzer, der für diese Aktivität verantwortlich ist',
            'assigned_supplier': 'Optional: Externer Lieferant, dem die Aktivität zugewiesen ist',
            'faellig_am': 'Optional: Fälligkeitsdatum für diese Aktivität',
            'ersteller': 'Benutzer, der diese Aktivität erstellt hat',
            'ist_serie': 'Wiederkehrende Aktivität mit festem Intervall',
            'intervall_monate': 'Intervall in Monaten (1-12) für wiederkehrende Aktivitäten',
        }
    
    def __init__(self, *args, **kwargs):
        # Extract context parameters if provided
        self.context_type = kwargs.pop('context_type', None)
        self.context_id = kwargs.pop('context_id', None)
        self.current_user = kwargs.pop('current_user', None)
        
        super().__init__(*args, **kwargs)
        
        # Filter assigned_user to show all users
        self.fields['assigned_user'].queryset = User.objects.all().order_by('username')
        self.fields['assigned_user'].required = False
        
        # Filter assigned_supplier to only show LIEFERANT addresses
        self.fields['assigned_supplier'].queryset = Adresse.objects.filter(
            adressen_type='LIEFERANT'
        ).order_by('name')
        self.fields['assigned_supplier'].required = False
        
        # Filter ersteller to show all users
        self.fields['ersteller'].queryset = User.objects.all().order_by('username')
        self.fields['ersteller'].required = True
        
        # Pre-fill ersteller with current user for new activities
        if not self.instance.pk and self.current_user:
            self.fields['ersteller'].initial = self.current_user.pk
        
        # Filter kunde to only show KUNDE addresses
        self.fields['kunde'].queryset = Adresse.objects.filter(
            adressen_type='KUNDE'
        ).order_by('name')
        self.fields['kunde'].required = False
        
        # Make intervall_monate optional initially
        self.fields['intervall_monate'].required = False
        
        # If context is provided, pre-fill and lock the context field
        if self.context_type and self.context_id:
            # Hide all context fields initially
            self.fields['mietobjekt'].widget = forms.HiddenInput()
            self.fields['vertrag'].widget = forms.HiddenInput()
            self.fields['kunde'].widget = forms.HiddenInput()
            
            # Set the appropriate context field based on context_type
            if self.context_type == 'mietobjekt':
                self.fields['mietobjekt'].initial = self.context_id
                self.fields['mietobjekt'].disabled = True
            elif self.context_type == 'vertrag':
                self.fields['vertrag'].initial = self.context_id
                self.fields['vertrag'].disabled = True
            elif self.context_type == 'kunde':
                self.fields['kunde'].initial = self.context_id
                self.fields['kunde'].disabled = True
        else:
            # If no context, make context fields visible but only allow one to be selected
            # This is a fallback mode - normally activities should be created from context
            pass
    
    def clean(self):
        """Ensure exactly one context is set."""
        cleaned_data = super().clean()
        
        # If context was provided in __init__, ensure it's set
        if self.context_type and self.context_id:
            try:
                if self.context_type == 'mietobjekt':
                    cleaned_data['mietobjekt'] = MietObjekt.objects.get(pk=self.context_id)
                    cleaned_data['vertrag'] = None
                    cleaned_data['kunde'] = None
                elif self.context_type == 'vertrag':
                    cleaned_data['vertrag'] = Vertrag.objects.get(pk=self.context_id)
                    cleaned_data['mietobjekt'] = None
                    cleaned_data['kunde'] = None
                elif self.context_type == 'kunde':
                    cleaned_data['kunde'] = Adresse.objects.get(pk=self.context_id)
                    cleaned_data['mietobjekt'] = None
                    cleaned_data['vertrag'] = None
            except (MietObjekt.DoesNotExist, Vertrag.DoesNotExist, Adresse.DoesNotExist):
                raise ValidationError('Das angegebene Kontextobjekt existiert nicht.')
        
        return cleaned_data


# Inline formset for managing VertragsObjekt in Vertrag forms
VertragsObjektFormSet = forms.inlineformset_factory(
    Vertrag,
    VertragsObjekt,
    form=VertragsObjektForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ZaehlerForm(forms.ModelForm):
    """
    Form for creating/editing Zaehler (meters).
    Includes all fields with proper Bootstrap 5 styling.
    """
    
    class Meta:
        model = Zaehler
        fields = ['typ', 'bezeichnung', 'einheit', 'parent']
        widgets = {
            'typ': forms.Select(attrs={'class': 'form-select'}),
            'bezeichnung': forms.TextInput(attrs={'class': 'form-control'}),
            'einheit': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'typ': 'Zählertyp *',
            'bezeichnung': 'Bezeichnung *',
            'einheit': 'Einheit',
            'parent': 'Übergeordneter Zähler (optional)',
        }
        help_texts = {
            'typ': 'Art des Zählers (Strom, Gas, Wasser, Heizung, Kühlung)',
            'bezeichnung': 'Beschreibende Bezeichnung (z.B. "Wohnung EG links", "Garage 1–3")',
            'einheit': 'Wird automatisch basierend auf dem Zählertyp gesetzt',
            'parent': 'Optional: Hauptzähler, wenn dieser Zähler ein Zwischenzähler ist',
        }
    
    def __init__(self, *args, **kwargs):
        mietobjekt = kwargs.pop('mietobjekt', None)
        super().__init__(*args, **kwargs)
        
        # Filter parent field to only show meters from the same MietObjekt
        if mietobjekt:
            # Exclude self if editing
            if self.instance.pk:
                self.fields['parent'].queryset = Zaehler.objects.filter(
                    mietobjekt=mietobjekt
                ).exclude(pk=self.instance.pk)
            else:
                self.fields['parent'].queryset = Zaehler.objects.filter(
                    mietobjekt=mietobjekt
                )
        else:
            self.fields['parent'].queryset = Zaehler.objects.none()


class ZaehlerstandForm(forms.ModelForm):
    """
    Form for creating/editing Zaehlerstand (meter readings).
    Includes all fields with proper Bootstrap 5 styling.
    """
    
    class Meta:
        model = Zaehlerstand
        fields = ['datum', 'wert']
        widgets = {
            'datum': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'wert': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
        }
        labels = {
            'datum': 'Datum *',
            'wert': 'Zählerstand *',
        }
        help_texts = {
            'datum': 'Datum der Ablesung',
            'wert': 'Wert des Zählerstands',
        }




class EingangsrechnungForm(forms.ModelForm):
    """Form for creating/editing incoming invoices (Eingangsrechnungen)"""
    
    class Meta:
        model = Eingangsrechnung
        fields = [
            'lieferant',
            'mietobjekt',
            'belegdatum',
            'faelligkeit',
            'belegnummer',
            'betreff',
            'referenznummer',
            'leistungszeitraum_von',
            'leistungszeitraum_bis',
            'notizen',
            'status',
            'zahlungsdatum',
            'umlagefaehig',
        ]
        widgets = {
            'lieferant': forms.Select(attrs={'class': 'form-select'}),
            'mietobjekt': forms.Select(attrs={'class': 'form-select'}),
            'belegdatum': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'faelligkeit': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'belegnummer': forms.TextInput(attrs={'class': 'form-control'}),
            'betreff': forms.TextInput(attrs={'class': 'form-control'}),
            'referenznummer': forms.TextInput(attrs={'class': 'form-control'}),
            'leistungszeitraum_von': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'leistungszeitraum_bis': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notizen': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'zahlungsdatum': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'umlagefaehig': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'lieferant': 'Lieferant *',
            'mietobjekt': 'Mietobjekt *',
            'belegdatum': 'Belegdatum *',
            'faelligkeit': 'Fälligkeit *',
            'belegnummer': 'Belegnummer *',
            'betreff': 'Betreff *',
            'referenznummer': 'Referenznummer',
            'leistungszeitraum_von': 'Leistungszeitraum von',
            'leistungszeitraum_bis': 'Leistungszeitraum bis',
            'notizen': 'Notizen',
            'status': 'Status',
            'zahlungsdatum': 'Zahlungsdatum',
            'umlagefaehig': 'Umlagefähig',
        }
        help_texts = {
            'lieferant': 'Wählen Sie den Lieferanten aus',
            'mietobjekt': 'Wählen Sie das Mietobjekt aus',
            'umlagefaehig': 'Kann auf Mieter umgelegt werden (flächenbasiert)',
            'zahlungsdatum': 'Nur bei Status "Bezahlt" erforderlich',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter lieferant to only show suppliers
        self.fields['lieferant'].queryset = Adresse.objects.filter(adressen_type='LIEFERANT')


class EingangsrechnungAufteilungForm(forms.ModelForm):
    """Form for invoice cost allocations"""
    
    class Meta:
        model = EingangsrechnungAufteilung
        fields = [
            'kostenart1',
            'kostenart2',
            'nettobetrag',
            'beschreibung',
        ]
        widgets = {
            'kostenart1': forms.Select(attrs={'class': 'form-select'}),
            'kostenart2': forms.Select(attrs={'class': 'form-select'}),
            'nettobetrag': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'beschreibung': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'kostenart1': 'Kostenart 1 (Hauptkostenart) *',
            'kostenart2': 'Kostenart 2 (Unterkostenart)',
            'nettobetrag': 'Nettobetrag (€) *',
            'beschreibung': 'Beschreibung',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Kostenart
        # Filter kostenart1 to only show main cost types (Hauptkostenarten)
        self.fields['kostenart1'].queryset = Kostenart.objects.filter(parent__isnull=True)
        # kostenart2 will show all for now, validation happens in clean()


# Formset for invoice allocations
EingangsrechnungAufteilungFormSet = forms.inlineformset_factory(
    Eingangsrechnung,
    EingangsrechnungAufteilung,
    form=EingangsrechnungAufteilungForm,
    extra=1,  # Start with one allocation by default
    min_num=1,  # At least one allocation required
    validate_min=True,
    can_delete=True,
)

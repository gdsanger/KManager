"""
Forms for the Vermietung (Rental Management) area.
"""

from django import forms
from django.core.exceptions import ValidationError
from core.models import Adresse
from .models import MietObjekt, Vertrag, Uebergabeprotokoll, Dokument, MietObjektBild, VertragsObjekt, OBJEKT_TYPE


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


class VertragForm(forms.ModelForm):
    """
    Form for creating/editing Vertrag (rental contracts).
    Includes all fields with proper Bootstrap 5 styling.
    Contract number is auto-generated and not editable.
    Supports multiple MietObjekte via many-to-many relationship.
    """
    
    # Custom field for selecting multiple mietobjekte
    mietobjekte = forms.ModelMultipleChoiceField(
        queryset=MietObjekt.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        label='Mietobjekte *',
        help_text='Wählen Sie ein oder mehrere Objekte aus (Mehrfachauswahl möglich)'
    )
    
    class Meta:
        model = Vertrag
        fields = [
            'mieter',
            'start',
            'ende',
            'miete',
            'kaution',
            'status',
        ]
        widgets = {
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
            'mieter': 'Mieter (Kunde) *',
            'start': 'Vertragsbeginn *',
            'ende': 'Vertragsende',
            'miete': 'Monatliche Miete (€) *',
            'kaution': 'Kaution (€) *',
            'status': 'Status *',
        }
        help_texts = {
            'mieter': 'Nur Adressen vom Typ "Kunde" können ausgewählt werden',
            'start': 'Startdatum des Vertrags',
            'ende': 'Optional: Enddatum des Vertrags (leer = unbefristet)',
            'miete': 'Monatliche Miete in EUR',
            'kaution': 'Kaution in EUR',
            'status': 'Status des Vertrags',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter mieter to only show KUNDE addresses
        self.fields['mieter'].queryset = Adresse.objects.filter(
            adressen_type='KUNDE'
        ).order_by('name')
        
        # If editing existing contract, pre-fill mietobjekte from VertragsObjekt
        if self.instance.pk:
            # Get currently assigned mietobjekte
            current_mietobjekte = self.instance.get_mietobjekte()
            self.fields['mietobjekte'].initial = current_mietobjekte
    
    def clean_mietobjekte(self):
        """Validate that at least one mietobjekt is selected."""
        mietobjekte = self.cleaned_data.get('mietobjekte')
        if not mietobjekte:
            raise ValidationError('Mindestens ein Mietobjekt muss ausgewählt werden.')
        return mietobjekte
    
    def clean(self):
        """
        Additional validation to warn about unavailable rental objects.
        VertragsObjekt.clean() will handle overlap validation when objects are saved.
        """
        cleaned_data = super().clean()
        mietobjekte = cleaned_data.get('mietobjekte', [])
        
        # Check if any selected mietobjekte are not available
        unavailable = [obj for obj in mietobjekte if not obj.verfuegbar]
        if unavailable:
            unavailable_names = ', '.join(obj.name for obj in unavailable)
            self.add_error(
                'mietobjekte',
                f'Achtung: Folgende Objekte sind aktuell nicht verfügbar: {unavailable_names}. '
                f'Möglicherweise gibt es bereits einen aktiven Vertrag.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """
        Save the Vertrag and create VertragsObjekt entries for selected mietobjekte.
        """
        instance = super().save(commit=commit)
        
        if commit:
            # Get selected mietobjekte
            mietobjekte = self.cleaned_data.get('mietobjekte', [])
            
            # Clear existing VertragsObjekt entries
            instance.vertragsobjekte.all().delete()
            
            # Create new VertragsObjekt entries
            for mietobjekt in mietobjekte:
                VertragsObjekt.objects.create(
                    vertrag=instance,
                    mietobjekt=mietobjekt
                )
            
            # Update availability of all affected mietobjekte
            instance.update_mietobjekte_availability()
        
        return instance


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


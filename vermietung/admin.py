from django.contrib import admin
from django import forms
from .models import (
    MietObjekt, Vertrag, Uebergabeprotokoll, Dokument, 
    OBJEKT_TYPE, VERTRAG_STATUS, DOKUMENT_ENTITY_TYPES
)
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
    actions = ['recalculate_availability']
    
    def recalculate_availability(self, request, queryset):
        """Recalculate availability for selected MietObjekt."""
        updated = 0
        for mietobjekt in queryset:
            old_verfuegbar = mietobjekt.verfuegbar
            mietobjekt.update_availability()
            if old_verfuegbar != mietobjekt.verfuegbar:
                updated += 1
        
        self.message_user(
            request, 
            f'Verfügbarkeit für {queryset.count()} Mietobjekte geprüft. {updated} wurden aktualisiert.'
        )
    recalculate_availability.short_description = 'Verfügbarkeit neu berechnen'


@admin.register(Vertrag)
class VertragAdmin(admin.ModelAdmin):
    form = VertragAdminForm
    list_display = ('vertragsnummer', 'mietobjekt', 'mieter', 'start', 'ende', 'status', 'miete', 'kaution')
    search_fields = ('vertragsnummer', 'mietobjekt__name', 'mieter__name', 'mieter__firma')
    list_filter = ('status', 'start', 'ende', 'mietobjekt')
    readonly_fields = ('vertragsnummer',)
    
    fieldsets = (
        ('Vertragsdetails', {
            'fields': ('vertragsnummer', 'mietobjekt', 'mieter', 'status')
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
    
    actions = ['mark_as_active', 'mark_as_ended', 'mark_as_cancelled']
    
    def mark_as_active(self, request, queryset):
        """Set selected contracts to active status."""
        updated = queryset.update(status='active')
        # Update availability for affected MietObjekte
        for vertrag in queryset:
            vertrag.update_mietobjekt_availability()
        self.message_user(request, f'{updated} Verträge wurden als aktiv markiert.')
    mark_as_active.short_description = 'Als aktiv markieren'
    
    def mark_as_ended(self, request, queryset):
        """Set selected contracts to ended status."""
        updated = queryset.update(status='ended')
        # Update availability for affected MietObjekte
        for vertrag in queryset:
            vertrag.update_mietobjekt_availability()
        self.message_user(request, f'{updated} Verträge wurden als beendet markiert.')
    mark_as_ended.short_description = 'Als beendet markieren'
    
    def mark_as_cancelled(self, request, queryset):
        """Set selected contracts to cancelled status."""
        updated = queryset.update(status='cancelled')
        # Update availability for affected MietObjekte
        for vertrag in queryset:
            vertrag.update_mietobjekt_availability()
        self.message_user(request, f'{updated} Verträge wurden als storniert markiert.')
    mark_as_cancelled.short_description = 'Als storniert markieren'


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


class DokumentAdminForm(forms.ModelForm):
    """
    Custom form for Dokument admin to handle file uploads.
    """
    file = forms.FileField(
        required=False,
        label="Datei hochladen",
        help_text="Erlaubte Dateitypen: PDF, PNG, JPG, GIF, DOCX. Maximale Größe: 10 MB"
    )
    
    class Meta:
        model = Dokument
        fields = '__all__'
        # Make storage_path, file_size, and mime_type read-only in form
        # They will be auto-populated on save
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make these fields read-only if editing existing document
        if self.instance.pk:
            self.fields['storage_path'].widget.attrs['readonly'] = True
            self.fields['file_size'].widget.attrs['readonly'] = True
            self.fields['mime_type'].widget.attrs['readonly'] = True
    
    def clean(self):
        """Validate that exactly one target entity is set."""
        cleaned_data = super().clean()
        
        # For new documents, require a file upload
        if not self.instance.pk and not cleaned_data.get('file'):
            raise forms.ValidationError('Bitte wählen Sie eine Datei zum Hochladen aus.')
        
        # Validate exactly one target entity
        target_entities = [
            cleaned_data.get('vertrag'),
            cleaned_data.get('mietobjekt'),
            cleaned_data.get('adresse'),
            cleaned_data.get('uebergabeprotokoll')
        ]
        set_entities = [e for e in target_entities if e is not None]
        
        if len(set_entities) == 0:
            raise forms.ValidationError(
                'Das Dokument muss genau einem Zielobjekt zugeordnet werden '
                '(Vertrag, Mietobjekt, Adresse oder Übergabeprotokoll).'
            )
        
        if len(set_entities) > 1:
            raise forms.ValidationError(
                'Das Dokument kann nur einem einzigen Zielobjekt zugeordnet werden.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to handle file upload."""
        instance = super().save(commit=False)
        
        # If this is a new upload, process the file
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file and not instance.pk:
            # First, set the foreign keys from cleaned_data so we can get entity info
            instance.vertrag = self.cleaned_data.get('vertrag')
            instance.mietobjekt = self.cleaned_data.get('mietobjekt')
            instance.adresse = self.cleaned_data.get('adresse')
            instance.uebergabeprotokoll = self.cleaned_data.get('uebergabeprotokoll')
            
            # Now get entity type and ID
            entity_type = instance.get_entity_type()
            entity_id = instance.get_entity_id()
            
            # Save the file and get storage info
            storage_path, mime_type = Dokument.save_uploaded_file(
                uploaded_file,
                entity_type,
                entity_id
            )
            
            # Update instance fields
            instance.original_filename = uploaded_file.name
            instance.storage_path = storage_path
            instance.file_size = uploaded_file.size
            instance.mime_type = mime_type
        
        if commit:
            instance.save()
        
        return instance


@admin.register(Dokument)
class DokumentAdmin(admin.ModelAdmin):
    form = DokumentAdminForm
    list_display = (
        'original_filename', 
        'get_entity_type_display',
        'get_entity_name',
        'file_size_display', 
        'mime_type', 
        'uploaded_at', 
        'uploaded_by'
    )
    search_fields = (
        'original_filename', 
        'beschreibung',
        'vertrag__vertragsnummer',
        'mietobjekt__name',
        'adresse__name',
        'uebergabeprotokoll__vertrag__vertragsnummer'
    )
    list_filter = ('mime_type', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'storage_path', 'file_size', 'mime_type', 'original_filename')
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Datei-Upload', {
            'fields': ('file',)
        }),
        ('Datei-Informationen', {
            'fields': ('original_filename', 'storage_path', 'file_size', 'mime_type')
        }),
        ('Zielobjekt', {
            'fields': ('vertrag', 'mietobjekt', 'adresse', 'uebergabeprotokoll'),
            'description': 'Wählen Sie genau ein Zielobjekt aus, dem dieses Dokument zugeordnet werden soll.'
        }),
        ('Zusätzliche Informationen', {
            'fields': ('beschreibung', 'uploaded_by', 'uploaded_at')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by prefetching related objects."""
        queryset = super().get_queryset(request)
        return queryset.select_related('vertrag', 'mietobjekt', 'adresse', 'uebergabeprotokoll', 'uploaded_by')
    
    def save_model(self, request, obj, form, change):
        """Set uploaded_by to current user if not set."""
        if not change and not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_entity_type_display(self, obj):
        """Display the entity type."""
        entity_type = obj.get_entity_type()
        if entity_type:
            return dict(DOKUMENT_ENTITY_TYPES).get(entity_type, entity_type)
        return '-'
    get_entity_type_display.short_description = 'Typ'
    
    def get_entity_name(self, obj):
        """Display the entity name."""
        if obj.vertrag:
            return str(obj.vertrag)
        elif obj.mietobjekt:
            return str(obj.mietobjekt)
        elif obj.adresse:
            return str(obj.adresse)
        elif obj.uebergabeprotokoll:
            return str(obj.uebergabeprotokoll)
        return '-'
    get_entity_name.short_description = 'Zugeordnet zu'
    
    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        size_bytes = obj.file_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    file_size_display.short_description = 'Größe'
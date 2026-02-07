from django.contrib import admin
from django import forms
from .models import (
    MietObjekt, Vertrag, VertragsObjekt, Uebergabeprotokoll, Dokument, Aktivitaet, AktivitaetsBereich,
    OBJEKT_TYPE, VERTRAG_STATUS, DOKUMENT_ENTITY_TYPES, AKTIVITAET_STATUS, AKTIVITAET_PRIORITAET,
    Eingangsrechnung, EingangsrechnungAufteilung
)
from core.models import Adresse, Mandant
from core.services.activity_stream import ActivityStreamService
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


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
    list_display = ('name', 'type', 'beschreibung', 'fläche', 'höhe', 'breite', 'tiefe', 'standort', 'mietpreis', 'kaution', 'display_qm_mietpreis', 'mandant', 'parent', 'verfuegbar')
    search_fields = ('name', 'standort__strasse', 'standort__ort', 'standort', 'parent__name')
    list_filter = ('type', 'verfuegbar', 'standort', 'mandant', 'parent')
    readonly_fields = ('display_qm_mietpreis', 'display_children')
    actions = ['recalculate_availability']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('name', 'type', 'beschreibung', 'standort', 'mandant')
        }),
        ('Hierarchie', {
            'fields': ('parent', 'display_children'),
            'description': 'Hierarchische Beziehungen zwischen Mietobjekten'
        }),
        ('Abmessungen', {
            'fields': ('fläche', 'höhe', 'breite', 'tiefe', 'volumen')
        }),
        ('Finanzielle Details', {
            'fields': ('mietpreis', 'nebenkosten', 'kaution', 'display_qm_mietpreis')
        }),
        ('Verfügbarkeit', {
            'fields': ('verfuegbare_einheiten', 'verfuegbar')
        }),
    )
    
    def display_qm_mietpreis(self, obj):
        """Display qm_mietpreis as read-only field."""
        qm_preis = obj.qm_mietpreis
        if qm_preis is not None:
            return f"{qm_preis} €/m²"
        return "-"
    display_qm_mietpreis.short_description = "qm-Mietpreis"
    
    def display_children(self, obj):
        """Display list of child MietObjekte."""
        if obj.pk:
            children = obj.children.all()
            if children.exists():
                return ", ".join([child.name for child in children])
            return "Keine untergeordneten Objekte"
        return "-"
    display_children.short_description = "Untergeordnete Mietobjekte"
    
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


# Helper functions for ActivityStream integration in Admin
def _get_vertrag_status_display_name(status):
    """
    Get display name for a Vertrag status.
    
    Args:
        status: str, status code (e.g., 'active', 'ended', 'cancelled')
        
    Returns:
        str: Display name from VERTRAG_STATUS choices
    """
    status_dict = dict(VERTRAG_STATUS)
    return status_dict.get(status, status)


def _get_mandant_for_vertrag(vertrag):
    """
    Get Mandant for a Vertrag.
    
    Args:
        vertrag: Vertrag instance
        
    Returns:
        Mandant instance or None if no mandant can be determined
    """
    # Get mandant from vertrag
    if vertrag.mandant:
        return vertrag.mandant
    
    # Fallback: get first available mandant
    return Mandant.objects.first()


def _log_vertrag_stream_event_admin(vertrag, event_type, actor=None, description=None, severity='INFO'):
    """
    Log an ActivityStream event for a Vertrag from Django Admin.
    
    Args:
        vertrag: Vertrag instance
        event_type: str, event type (e.g., 'contract.created', 'contract.status_changed')
        actor: User instance who performed the action (optional)
        description: str, additional description (optional)
        severity: str, severity level (default: 'INFO')
    """
    mandant = _get_mandant_for_vertrag(vertrag)
    
    # If no mandant, cannot create stream event
    if not mandant:
        logger.warning(
            f"Cannot create ActivityStream event for Vertrag {vertrag.pk}: "
            f"No Mandant found"
        )
        return
    
    try:
        ActivityStreamService.add(
            company=mandant,
            domain='RENTAL',
            activity_type=event_type,
            title=f'Vertrag: {vertrag.vertragsnummer}',
            description=description or '',
            target_url=reverse('vermietung:vertrag_detail', args=[vertrag.pk]),
            actor=actor,
            severity=severity
        )
    except Exception as e:
        logger.error(
            f"Failed to create ActivityStream event for Vertrag {vertrag.pk}: {e}"
        )


@admin.register(Vertrag)
class VertragAdmin(admin.ModelAdmin):
    form = VertragAdminForm
    list_display = ('vertragsnummer', 'mietobjekt', 'mieter', 'start', 'ende', 'status', 'miete', 'kaution', 'mandant')
    search_fields = ('vertragsnummer', 'mietobjekt__name', 'mieter__name', 'mieter__firma')
    list_filter = ('status', 'start', 'ende', 'mietobjekt', 'mandant')
    
    fieldsets = (
        ('Vertragsdetails', {
            'fields': ('vertragsnummer', 'mietobjekt', 'mieter', 'status', 'mandant')
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
        return queryset.select_related('mieter', 'mietobjekt', 'mandant')
    
    def save_model(self, request, obj, form, change):
        """
        Override save_model to log ActivityStream events for create and edit operations.
        
        Args:
            request: HTTP request
            obj: Vertrag instance being saved
            form: ModelForm instance
            change: Boolean indicating if this is a change (True) or creation (False)
        """
        # Store old status before save to detect changes
        old_status = None
        if change and obj.pk:
            try:
                old_instance = Vertrag.objects.get(pk=obj.pk)
                old_status = old_instance.status
            except Vertrag.DoesNotExist:
                pass
        
        # Save the object
        super().save_model(request, obj, form, change)
        
        # Log ActivityStream events
        if not change:
            # New contract created
            mieter_name = obj.mieter.full_name() if obj.mieter else 'Unbekannt'
            _log_vertrag_stream_event_admin(
                vertrag=obj,
                event_type='contract.created',
                actor=request.user,
                description=f'Neuer Vertrag erstellt für Mieter: {mieter_name}. Status: {_get_vertrag_status_display_name(obj.status)} (via Admin)',
                severity='INFO'
            )
        else:
            # Contract edited - check if status changed
            if old_status and old_status != obj.status:
                old_status_display = _get_vertrag_status_display_name(old_status)
                new_status_display = _get_vertrag_status_display_name(obj.status)
                _log_vertrag_stream_event_admin(
                    vertrag=obj,
                    event_type='contract.status_changed',
                    actor=request.user,
                    description=f'Status geändert: {old_status_display} → {new_status_display} (via Admin)',
                    severity='INFO'
                )
    
    actions = ['mark_as_active', 'mark_as_ended', 'mark_as_cancelled']
    
    def mark_as_active(self, request, queryset):
        """Set selected contracts to active status and log ActivityStream events."""
        updated = 0
        affected_vertrage = []
        
        for vertrag in queryset:
            old_status = vertrag.status
            if old_status != 'active':
                vertrag.status = 'active'
                vertrag.save()
                affected_vertrage.append(vertrag)
                
                # Log ActivityStream event
                old_status_display = _get_vertrag_status_display_name(old_status)
                new_status_display = _get_vertrag_status_display_name('active')
                _log_vertrag_stream_event_admin(
                    vertrag=vertrag,
                    event_type='contract.status_changed',
                    actor=request.user,
                    description=f'Status geändert: {old_status_display} → {new_status_display} (via Admin Bulk Action)',
                    severity='INFO'
                )
                updated += 1
        
        # Batch update availability for all affected contracts
        # Note: Each call updates all associated MietObjekte, but doing it once per unique set is more efficient
        affected_mietobjekt_ids = set()
        for vertrag in affected_vertrage:
            if vertrag.mietobjekt_id:
                affected_mietobjekt_ids.add(vertrag.mietobjekt_id)
            affected_mietobjekt_ids.update(
                vertrag.vertragsobjekte.values_list('mietobjekt_id', flat=True)
            )
        
        # Update each unique MietObjekt only once
        from django.utils import timezone
        from django.db.models import Q
        for mietobjekt_id in affected_mietobjekt_ids:
            has_active_contract = VertragsObjekt.objects.filter(
                mietobjekt_id=mietobjekt_id,
                vertrag__status='active'
            ).select_related('vertrag').filter(
                vertrag__start__lte=timezone.now().date()
            ).filter(
                Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=timezone.now().date())
            ).exists()
            MietObjekt.objects.filter(pk=mietobjekt_id).update(
                verfuegbar=not has_active_contract
            )
        
        self.message_user(request, f'{updated} Verträge wurden als aktiv markiert.')
    mark_as_active.short_description = 'Als aktiv markieren'
    
    def mark_as_ended(self, request, queryset):
        """Set selected contracts to ended status and log ActivityStream events."""
        updated = 0
        affected_vertrage = []
        
        for vertrag in queryset:
            old_status = vertrag.status
            if old_status != 'ended':
                vertrag.status = 'ended'
                vertrag.save()
                affected_vertrage.append(vertrag)
                
                # Log ActivityStream event
                old_status_display = _get_vertrag_status_display_name(old_status)
                new_status_display = _get_vertrag_status_display_name('ended')
                _log_vertrag_stream_event_admin(
                    vertrag=vertrag,
                    event_type='contract.status_changed',
                    actor=request.user,
                    description=f'Status geändert: {old_status_display} → {new_status_display} (via Admin Bulk Action)',
                    severity='INFO'
                )
                updated += 1
        
        # Batch update availability for all affected contracts
        affected_mietobjekt_ids = set()
        for vertrag in affected_vertrage:
            if vertrag.mietobjekt_id:
                affected_mietobjekt_ids.add(vertrag.mietobjekt_id)
            affected_mietobjekt_ids.update(
                vertrag.vertragsobjekte.values_list('mietobjekt_id', flat=True)
            )
        
        # Update each unique MietObjekt only once
        from django.utils import timezone
        from django.db.models import Q
        for mietobjekt_id in affected_mietobjekt_ids:
            has_active_contract = VertragsObjekt.objects.filter(
                mietobjekt_id=mietobjekt_id,
                vertrag__status='active'
            ).select_related('vertrag').filter(
                vertrag__start__lte=timezone.now().date()
            ).filter(
                Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=timezone.now().date())
            ).exists()
            MietObjekt.objects.filter(pk=mietobjekt_id).update(
                verfuegbar=not has_active_contract
            )
        
        self.message_user(request, f'{updated} Verträge wurden als beendet markiert.')
    mark_as_ended.short_description = 'Als beendet markieren'
    
    def mark_as_cancelled(self, request, queryset):
        """Set selected contracts to cancelled status and log ActivityStream events."""
        updated = 0
        affected_vertrage = []
        
        for vertrag in queryset:
            old_status = vertrag.status
            if old_status != 'cancelled':
                vertrag.status = 'cancelled'
                vertrag.save()
                affected_vertrage.append(vertrag)
                
                # Log ActivityStream event
                old_status_display = _get_vertrag_status_display_name(old_status)
                new_status_display = _get_vertrag_status_display_name('cancelled')
                _log_vertrag_stream_event_admin(
                    vertrag=vertrag,
                    event_type='contract.cancelled',
                    actor=request.user,
                    description=f'Vertrag wurde storniert. Status: {old_status_display} → {new_status_display} (via Admin Bulk Action)',
                    severity='WARNING'
                )
                updated += 1
        
        # Batch update availability for all affected contracts
        affected_mietobjekt_ids = set()
        for vertrag in affected_vertrage:
            if vertrag.mietobjekt_id:
                affected_mietobjekt_ids.add(vertrag.mietobjekt_id)
            affected_mietobjekt_ids.update(
                vertrag.vertragsobjekte.values_list('mietobjekt_id', flat=True)
            )
        
        # Update each unique MietObjekt only once
        from django.utils import timezone
        from django.db.models import Q
        for mietobjekt_id in affected_mietobjekt_ids:
            has_active_contract = VertragsObjekt.objects.filter(
                mietobjekt_id=mietobjekt_id,
                vertrag__status='active'
            ).select_related('vertrag').filter(
                vertrag__start__lte=timezone.now().date()
            ).filter(
                Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=timezone.now().date())
            ).exists()
            MietObjekt.objects.filter(pk=mietobjekt_id).update(
                verfuegbar=not has_active_contract
            )
        
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


@admin.register(AktivitaetsBereich)
class AktivitaetsBereichAdmin(admin.ModelAdmin):
    """
    Admin interface for AktivitaetsBereich (activity categories/areas).
    """
    list_display = ('name', 'beschreibung', 'created_at', 'get_aktivitaeten_count')
    search_fields = ('name', 'beschreibung')
    readonly_fields = ('created_at',)
    ordering = ('name',)
    
    def get_aktivitaeten_count(self, obj):
        """Get count of activities in this category."""
        return obj.aktivitaeten.count()
    get_aktivitaeten_count.short_description = 'Anzahl Aktivitäten'


class AktivitaetAdminForm(forms.ModelForm):
    """
    Custom form for Aktivitaet admin to restrict selections and provide validation.
    """
    class Meta:
        model = Aktivitaet
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict kunde choices to only KUNDE addresses
        self.fields['kunde'].queryset = Adresse.objects.filter(adressen_type='KUNDE')
        # Restrict assigned_supplier choices to only LIEFERANT addresses
        self.fields['assigned_supplier'].queryset = Adresse.objects.filter(adressen_type='LIEFERANT')


@admin.register(Aktivitaet)
class AktivitaetAdmin(admin.ModelAdmin):
    form = AktivitaetAdminForm
    list_display = (
        'titel',
        'get_context_type',
        'bereich',
        'status',
        'prioritaet',
        'faellig_am',
        'assigned_user',
        'assigned_supplier',
        'created_at'
    )
    search_fields = (
        'titel',
        'beschreibung',
        'bereich__name',
        'mietobjekt__name',
        'vertrag__vertragsnummer',
        'kunde__name',
        'assigned_user__username',
        'assigned_supplier__name'
    )
    list_filter = ('status', 'prioritaet', 'bereich', 'faellig_am', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'faellig_am'
    
    fieldsets = (
        ('Aufgabendetails', {
            'fields': ('titel', 'beschreibung', 'status', 'prioritaet', 'faellig_am', 'bereich')
        }),
        ('Kontext (optional)', {
            'fields': ('mietobjekt', 'vertrag', 'kunde'),
            'description': 'Optional: Wählen Sie einen oder mehrere Kontexte aus. Aktivitäten ohne Kontext sind für private/persönliche Aufgaben erlaubt.'
        }),
        ('Zuweisung (optional)', {
            'fields': ('assigned_user', 'assigned_supplier'),
            'description': 'Sie können die Aktivität intern (Benutzer), extern (Lieferant), beiden oder keinem zuweisen.'
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries by prefetching related objects."""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'mietobjekt',
            'vertrag',
            'kunde',
            'bereich',
            'assigned_user',
            'assigned_supplier'
        )
    
    def get_context_type(self, obj):
        """Display the context type."""
        if obj.mietobjekt:
            return f"Mietobjekt: {obj.mietobjekt.name}"
        elif obj.vertrag:
            return f"Vertrag: {obj.vertrag.vertragsnummer}"
        elif obj.kunde:
            return f"Kunde: {obj.kunde.name}"
        return '-'
    get_context_type.short_description = 'Kontext'
    
    actions = ['mark_as_in_bearbeitung', 'mark_as_erledigt', 'mark_as_abgebrochen']
    
    def mark_as_in_bearbeitung(self, request, queryset):
        """Set selected activities to IN_BEARBEITUNG status."""
        updated = queryset.update(status='IN_BEARBEITUNG')
        self.message_user(request, f'{updated} Aktivitäten wurden als "In Bearbeitung" markiert.')
    mark_as_in_bearbeitung.short_description = 'Als "In Bearbeitung" markieren'
    
    def mark_as_erledigt(self, request, queryset):
        """Set selected activities to ERLEDIGT status."""
        updated = queryset.update(status='ERLEDIGT')
        self.message_user(request, f'{updated} Aktivitäten wurden als "Erledigt" markiert.')
    mark_as_erledigt.short_description = 'Als "Erledigt" markieren'
    
    def mark_as_abgebrochen(self, request, queryset):
        """Set selected activities to ABGEBROCHEN status."""
        updated = queryset.update(status='ABGEBROCHEN')
        self.message_user(request, f'{updated} Aktivitäten wurden als "Abgebrochen" markiert.')
    mark_as_abgebrochen.short_description = 'Als "Abgebrochen" markieren'

class EingangsrechnungAufteilungInline(admin.TabularInline):
    """Inline admin for invoice cost allocations"""
    model = EingangsrechnungAufteilung
    extra = 1
    fields = ('kostenart1', 'kostenart2', 'nettobetrag', 'beschreibung')
    readonly_fields = ()


@admin.register(Eingangsrechnung)
class EingangsrechnungAdmin(admin.ModelAdmin):
    list_display = (
        'belegnummer', 'belegdatum', 'lieferant', 'mietobjekt', 
        'betreff', 'status', 'faelligkeit', 'umlagefaehig'
    )
    search_fields = (
        'belegnummer', 'betreff', 'referenznummer',
        'lieferant__name', 'lieferant__firma', 'mietobjekt__name'
    )
    list_filter = ('status', 'umlagefaehig', 'mietobjekt', 'lieferant')
    date_hierarchy = 'belegdatum'
    inlines = [EingangsrechnungAufteilungInline]
    
    fieldsets = (
        ('Lieferant & Mietobjekt', {
            'fields': ('lieferant', 'mietobjekt')
        }),
        ('Belegdaten', {
            'fields': ('belegnummer', 'belegdatum', 'faelligkeit', 'betreff', 'referenznummer')
        }),
        ('Leistungszeitraum', {
            'fields': ('leistungszeitraum_von', 'leistungszeitraum_bis'),
            'classes': ('collapse',)
        }),
        ('Status & Zahlung', {
            'fields': ('status', 'zahlungsdatum', 'umlagefaehig')
        }),
        ('Notizen', {
            'fields': ('notizen',),
            'classes': ('collapse',)
        }),
    )


@admin.register(EingangsrechnungAufteilung)
class EingangsrechnungAufteilungAdmin(admin.ModelAdmin):
    list_display = ('eingangsrechnung', 'kostenart1', 'kostenart2', 'nettobetrag', 'beschreibung')
    search_fields = ('eingangsrechnung__belegnummer', 'kostenart1__name', 'kostenart2__name', 'beschreibung')
    list_filter = ('kostenart1', 'kostenart2')

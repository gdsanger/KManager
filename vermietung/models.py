
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from core.models import Adresse
import os
import magic
from pathlib import Path

OBJEKT_TYPE = [
       ('GEBAEUDE','Gebäude'),
        ('RAUM','Raum'),
        ('CONTAINER','Container'),
        ('STELLPLATZ','Stellplatz'),
        ('KFZ','KFZ'),
        ('SONSTIGES','Sonstiges'),
    ]

VERTRAG_STATUS = [
    ('draft', 'Entwurf'),
    ('active', 'Aktiv'),
    ('ended', 'Beendet'),
    ('cancelled', 'Storniert'),
]


class VertragQuerySet(models.QuerySet):
    """Custom queryset for Vertrag with helper methods."""
    
    def currently_active(self):
        """
        Filter to contracts that are currently active (occupying their MietObjekt).
        A contract is currently active if:
        - Status is 'active'
        - start <= today
        - ende is NULL or ende > today
        """
        today = timezone.now().date()
        return self.filter(
            status='active',
            start__lte=today
        ).filter(
            models.Q(ende__isnull=True) | models.Q(ende__gt=today)
        )


class MietObjekt(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=OBJEKT_TYPE)
    beschreibung = models.TextField()
    fläche = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    höhe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    breite = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tiefe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    standort = models.ForeignKey(Adresse, on_delete=models.CASCADE)
    mietpreis = models.DecimalField(max_digits=10, decimal_places=2)
    verfuegbar = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    def update_availability(self):
        """
        Update the availability based on currently active contracts.
        MietObjekt is available if there are no currently active contracts.
        """
        has_active_contract = self.vertraege.currently_active().exists()
        self.verfuegbar = not has_active_contract
        self.save(update_fields=['verfuegbar'])


class Vertrag(models.Model):
    """
    Rental contract model (Mietvertrag).
    Each contract is for exactly one MietObjekt.
    A MietObjekt can have multiple contracts over time (history).
    """
    vertragsnummer = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        verbose_name="Vertragsnummer",
        help_text="Automatisch generierte Vertragsnummer im Format V-00000"
    )
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.PROTECT,
        related_name='vertraege',
        verbose_name="Mietobjekt"
    )
    mieter = models.ForeignKey(
        Adresse,
        on_delete=models.PROTECT,
        related_name='vertraege',
        limit_choices_to={'adressen_type': 'KUNDE'},
        verbose_name="Mieter",
        help_text="Nur Adressen vom Typ 'Kunde' können ausgewählt werden"
    )
    start = models.DateField(
        verbose_name="Vertragsbeginn",
        help_text="Startdatum des Vertrags (Pflicht)"
    )
    ende = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vertragsende",
        help_text="Enddatum des Vertrags (optional, NULL = offenes Ende)"
    )
    miete = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Miete",
        help_text="Monatliche Miete in EUR"
    )
    kaution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Kaution",
        help_text="Kaution in EUR"
    )
    status = models.CharField(
        max_length=20,
        choices=VERTRAG_STATUS,
        default='active',
        verbose_name="Status",
        help_text="Status des Vertrags"
    )
    
    # Custom manager
    objects = VertragQuerySet.as_manager()
    
    class Meta:
        verbose_name = "Vertrag"
        verbose_name_plural = "Verträge"
        ordering = ['-start']
    
    def __str__(self):
        """
        String representation of the contract.
        Note: This may cause database queries if mieter is not pre-loaded.
        Use select_related('mieter', 'mietobjekt') in queries to avoid N+1 problems.
        """
        mieter_name = self.mieter.full_name() if self.mieter else 'Unbekannt'
        mietobjekt_name = self.mietobjekt.name if self.mietobjekt else 'Unbekannt'
        return f"{self.vertragsnummer} - {mietobjekt_name} ({mieter_name})"
    
    def is_currently_active(self):
        """
        Check if this contract is currently active (occupying the MietObjekt).
        A contract is currently active if:
        - Status is 'active'
        - start <= today
        - ende is NULL or ende > today
        """
        if self.status != 'active':
            return False
        
        today = timezone.now().date()
        
        # Contract must have started
        if self.start > today:
            return False
        
        # Contract must not have ended
        if self.ende is not None and self.ende <= today:
            return False
        
        return True
    
    def clean(self):
        """
        Validate the contract data:
        1. If ende is set, it must be greater than start
        2. Check for overlapping contracts for the same MietObjekt
        """
        super().clean()
        
        # Validate date range
        if self.ende and self.start and self.ende <= self.start:
            raise ValidationError({
                'ende': 'Das Vertragsende muss nach dem Vertragsbeginn liegen.'
            })
        
        # Check for overlapping contracts
        if self.mietobjekt_id:
            self._check_for_overlaps()
    
    def _check_for_overlaps(self):
        """
        Check if this contract overlaps with any existing ACTIVE contracts for the same MietObjekt.
        Only active contracts are considered for overlap checking.
        A contract overlaps if:
        - Contract A starts before Contract B ends AND Contract A ends after Contract B starts
        - Special case: if a contract has no end date (NULL), it blocks all future starts
        """
        # Get all other ACTIVE contracts for the same MietObjekt
        existing_contracts = Vertrag.objects.filter(
            mietobjekt=self.mietobjekt,
            status='active'  # Only check active contracts
        ).exclude(pk=self.pk if self.pk else None)
        
        # Only check for overlaps if this contract is active
        if self.status != 'active':
            return
        
        for contract in existing_contracts:
            # Case 1: Existing contract has no end date (open-ended)
            # It blocks any new contract that starts after its start date
            if contract.ende is None:
                if self.start >= contract.start:
                    raise ValidationError({
                        'start': f'Es existiert bereits ein laufender Vertrag ohne Enddatum '
                                f'({contract.vertragsnummer}) für dieses Mietobjekt ab {contract.start}.'
                    })
                # New contract starts before existing open-ended contract
                if self.ende is None or self.ende > contract.start:
                    raise ValidationError({
                        'ende': f'Dieser Vertrag würde mit einem bestehenden Vertrag '
                               f'({contract.vertragsnummer}) überlappen, der am {contract.start} beginnt.'
                    })
            
            # Case 2: This contract has no end date
            elif self.ende is None:
                # It blocks any existing contract that ends after this contract's start
                if contract.start < self.start and (contract.ende is None or contract.ende > self.start):
                    raise ValidationError({
                        'start': f'Ein Vertrag ohne Enddatum würde mit bestehendem Vertrag '
                                f'({contract.vertragsnummer}) überlappen.'
                    })
                # It blocks any existing contract that starts after this contract's start
                if contract.start >= self.start:
                    raise ValidationError({
                        'start': f'Ein Vertrag ohne Enddatum würde mit bestehendem Vertrag '
                                f'({contract.vertragsnummer}) überlappen.'
                    })
            
            # Case 3: Both contracts have end dates
            else:
                # Standard overlap check: A.start < B.end AND A.end > B.start
                if self.start < contract.ende and self.ende > contract.start:
                    raise ValidationError({
                        'start': f'Dieser Vertrag überschneidet sich mit bestehendem Vertrag '
                                f'({contract.vertragsnummer}) von {contract.start} bis {contract.ende}.'
                    })
    
    def save(self, *args, **kwargs):
        """
        Override save to auto-generate contract number if not set.
        Uses database-level locking to prevent race conditions.
        Updates the MietObjekt availability after saving.
        """
        if not self.vertragsnummer:
            self.vertragsnummer = self._generate_vertragsnummer()
        
        # Run full_clean to trigger validation
        self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Update availability of the MietObjekt after saving
        self.update_mietobjekt_availability()
    
    def update_mietobjekt_availability(self):
        """
        Update the availability of the associated MietObjekt.
        MietObjekt is available if there are no currently active contracts.
        Public method that can be called from admin actions.
        """
        if not self.mietobjekt_id:
            return
        
        # Check if there are any currently active contracts for this MietObjekt
        has_active_contract = Vertrag.objects.filter(
            mietobjekt_id=self.mietobjekt_id
        ).currently_active().exists()
        
        # Update the MietObjekt directly without triggering save
        MietObjekt.objects.filter(pk=self.mietobjekt_id).update(
            verfuegbar=not has_active_contract
        )
    
    def _generate_vertragsnummer(self):
        """
        Generate next contract number in format V-00000.
        Uses SELECT FOR UPDATE to prevent race conditions.
        """
        with transaction.atomic():
            # Get the last contract number using database locking
            # Order by ID to ensure we get the most recently created contract
            # (since vertragsnummer is a CharField, lexicographic ordering won't work correctly)
            last_contract = Vertrag.objects.select_for_update().order_by('-id').first()
            
            if last_contract and last_contract.vertragsnummer:
                try:
                    # Extract number from V-00000 format
                    last_number = int(last_contract.vertragsnummer.split('-')[1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    # If parsing fails, fall back to counting all contracts + 1
                    next_number = Vertrag.objects.count() + 1
            else:
                next_number = 1
            
            # Format as V-00000
            return f"V-{next_number:05d}"


UEBERGABE_TYP = [
    ('EINZUG', 'Einzug'),
    ('AUSZUG', 'Auszug'),
]


class Uebergabeprotokoll(models.Model):
    """
    Handover protocol model (Übergabeprotokoll).
    Documents the handover (move-in/move-out) including meter readings,
    keys, defects and involved persons.
    Each protocol is linked to a Vertrag and MietObjekt.
    """
    vertrag = models.ForeignKey(
        Vertrag,
        on_delete=models.PROTECT,
        related_name='uebergabeprotokolle',
        verbose_name="Vertrag"
    )
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.PROTECT,
        related_name='uebergabeprotokolle',
        verbose_name="Mietobjekt"
    )
    typ = models.CharField(
        max_length=10,
        choices=UEBERGABE_TYP,
        verbose_name="Typ",
        help_text="Art der Übergabe (Einzug oder Auszug)"
    )
    uebergabetag = models.DateField(
        verbose_name="Übergabetag",
        help_text="Datum der Übergabe"
    )
    
    # Zählerstände (Meter readings)
    zaehlerstand_strom = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Zählerstand Strom",
        help_text="Stromzählerstand in kWh"
    )
    zaehlerstand_gas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Zählerstand Gas",
        help_text="Gaszählerstand in m³"
    )
    zaehlerstand_wasser = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Zählerstand Wasser",
        help_text="Wasserzählerstand in m³"
    )
    
    # Schlüssel (Keys)
    anzahl_schluessel = models.IntegerField(
        default=0,
        verbose_name="Anzahl Schlüssel",
        help_text="Anzahl der übergebenen Schlüssel"
    )
    
    # Bemerkungen und Mängel (Remarks and defects)
    bemerkungen = models.TextField(
        blank=True,
        verbose_name="Bemerkungen",
        help_text="Allgemeine Bemerkungen zur Übergabe"
    )
    maengel = models.TextField(
        blank=True,
        verbose_name="Mängel",
        help_text="Festgestellte Mängel bei der Übergabe"
    )
    
    # Personen (Persons involved)
    person_vermieter = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Person Vermieter",
        help_text="Name der Person auf Vermieterseite"
    )
    person_mieter = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Person Mieter",
        help_text="Name der Person auf Mieterseite"
    )
    
    class Meta:
        verbose_name = "Übergabeprotokoll"
        verbose_name_plural = "Übergabeprotokolle"
        ordering = ['-uebergabetag']
    
    def __str__(self):
        """String representation of the handover protocol."""
        typ_display = self.get_typ_display()
        return f"{typ_display} - {self.vertrag.vertragsnummer} - {self.uebergabetag}"
    
    def clean(self):
        """
        Validate the handover protocol data:
        1. MietObjekt must match the Vertrag's MietObjekt
        2. Uebergabetag should be within or near the contract period
        """
        super().clean()
        
        # Validate that MietObjekt matches Vertrag's MietObjekt
        # Use _id fields to avoid triggering additional queries
        if self.vertrag_id and self.mietobjekt_id:
            # We need to fetch the vertrag's mietobjekt_id
            # This is only done during validation, not on every access
            from django.db.models import F
            vertrag_mietobjekt_id = Vertrag.objects.filter(
                pk=self.vertrag_id
            ).values_list('mietobjekt_id', flat=True).first()
            
            if vertrag_mietobjekt_id != self.mietobjekt_id:
                # Get mietobjekt name for better error message
                mietobjekt_name = MietObjekt.objects.filter(
                    pk=vertrag_mietobjekt_id
                ).values_list('name', flat=True).first()
                raise ValidationError({
                    'mietobjekt': f'Das Mietobjekt muss zum Vertrag passen. '
                                 f'Der Vertrag ist für "{mietobjekt_name}".'
                })
        
        # Validate that uebergabetag is reasonable relative to contract dates
        if self.vertrag_id and self.uebergabetag:
            # Fetch contract dates efficiently
            vertrag_data = Vertrag.objects.filter(
                pk=self.vertrag_id
            ).values('start', 'ende').first()
            
            if vertrag_data:
                if self.typ == 'EINZUG':
                    # Move-in should be around contract start
                    if self.uebergabetag < vertrag_data['start']:
                        raise ValidationError({
                            'uebergabetag': f'Das Einzugsdatum sollte nicht vor dem Vertragsbeginn '
                                           f'({vertrag_data["start"]}) liegen.'
                        })
                elif self.typ == 'AUSZUG':
                    # Move-out should be around contract end (if set)
                    if vertrag_data['ende'] and self.uebergabetag > vertrag_data['ende']:
                        raise ValidationError({
                            'uebergabetag': f'Das Auszugsdatum sollte nicht nach dem Vertragsende '
                                           f'({vertrag_data["ende"]}) liegen.'
                        })
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)


# Document entity types for storage path
DOKUMENT_ENTITY_TYPES = [
    ('vertrag', 'Vertrag'),
    ('mietobjekt', 'Mietobjekt'),
    ('adresse', 'Adresse'),
    ('uebergabeprotokoll', 'Übergabeprotokoll'),
]

# Allowed MIME types for documents
ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'image/png': ['.png'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/gif': ['.gif'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

# Max file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_file_size(file):
    """Validate that file size does not exceed maximum allowed size."""
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            f'Die Dateigröße ({file.size / (1024*1024):.2f} MB) überschreitet '
            f'das Maximum von {MAX_FILE_SIZE / (1024*1024):.0f} MB.'
        )


def validate_file_type(file):
    """
    Validate that file type is one of the allowed types.
    
    Returns:
        str: The detected MIME type if valid
    
    Raises:
        ValidationError: If file type is not allowed
    """
    # Read file content to detect MIME type
    file.seek(0)
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    
    if mime not in ALLOWED_MIME_TYPES:
        allowed_extensions = []
        for extensions in ALLOWED_MIME_TYPES.values():
            allowed_extensions.extend(extensions)
        raise ValidationError(
            f'Dateityp "{mime}" ist nicht erlaubt. '
            f'Erlaubte Typen: {", ".join(sorted(set(allowed_extensions)))}'
        )
    
    # Also check file extension matches MIME type
    filename = file.name.lower()
    expected_extensions = ALLOWED_MIME_TYPES.get(mime, [])
    if not any(filename.endswith(ext) for ext in expected_extensions):
        raise ValidationError(
            f'Dateierweiterung passt nicht zum erkannten Dateityp "{mime}". '
            f'Erwartete Erweiterungen: {", ".join(expected_extensions)}'
        )
    
    return mime


class Dokument(models.Model):
    """
    Document model for managing files in the Vermietung (rental) module.
    
    Documents are stored in the filesystem under <APP_ROOT>/data/vermietung/<entity_type>/<entity_id>/
    Metadata is stored in the database.
    
    Each document is linked to exactly one target entity:
    - Vertrag (contract)
    - MietObjekt (rental object)
    - Adresse (address)
    - Uebergabeprotokoll (handover protocol)
    """
    # Original filename
    original_filename = models.CharField(
        max_length=255,
        verbose_name="Originaler Dateiname",
        help_text="Der ursprüngliche Dateiname beim Upload"
    )
    
    # Storage path (relative to VERMIETUNG_DOCUMENTS_ROOT)
    storage_path = models.CharField(
        max_length=500,
        verbose_name="Speicherpfad",
        help_text="Relativer Pfad zur Datei im Filesystem"
    )
    
    # File metadata
    file_size = models.IntegerField(
        verbose_name="Dateigröße",
        help_text="Dateigröße in Bytes"
    )
    
    mime_type = models.CharField(
        max_length=100,
        verbose_name="MIME-Type",
        help_text="MIME-Type der Datei"
    )
    
    # Upload metadata
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hochgeladen am",
        help_text="Zeitpunkt des Uploads"
    )
    
    uploaded_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Hochgeladen von",
        help_text="Benutzer, der die Datei hochgeladen hat"
    )
    
    # Optional description
    beschreibung = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Optional: Beschreibung des Dokuments"
    )
    
    # Foreign keys to target entities (exactly one must be set)
    vertrag = models.ForeignKey(
        Vertrag,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dokumente',
        verbose_name="Vertrag"
    )
    
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dokumente',
        verbose_name="Mietobjekt"
    )
    
    adresse = models.ForeignKey(
        Adresse,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dokumente',
        verbose_name="Adresse"
    )
    
    uebergabeprotokoll = models.ForeignKey(
        Uebergabeprotokoll,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dokumente',
        verbose_name="Übergabeprotokoll"
    )
    
    class Meta:
        verbose_name = "Dokument"
        verbose_name_plural = "Dokumente"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        """String representation of the document."""
        entity = self.get_entity_display()
        return f"{self.original_filename} ({entity})"
    
    def clean(self):
        """
        Validate that exactly one target entity is set.
        """
        super().clean()
        
        # Count how many foreign keys are set
        target_entities = [
            self.vertrag_id,
            self.mietobjekt_id,
            self.adresse_id,
            self.uebergabeprotokoll_id
        ]
        set_entities = [e for e in target_entities if e is not None]
        
        if len(set_entities) == 0:
            raise ValidationError(
                'Das Dokument muss genau einem Zielobjekt zugeordnet werden '
                '(Vertrag, Mietobjekt, Adresse oder Übergabeprotokoll).'
            )
        
        if len(set_entities) > 1:
            raise ValidationError(
                'Das Dokument kann nur einem einzigen Zielobjekt zugeordnet werden.'
            )
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_entity_type(self):
        """Get the entity type string for storage path."""
        if self.vertrag_id:
            return 'vertrag'
        elif self.mietobjekt_id:
            return 'mietobjekt'
        elif self.adresse_id:
            return 'adresse'
        elif self.uebergabeprotokoll_id:
            return 'uebergabeprotokoll'
        return None
    
    def get_entity_id(self):
        """Get the entity ID for storage path."""
        if self.vertrag_id:
            return self.vertrag_id
        elif self.mietobjekt_id:
            return self.mietobjekt_id
        elif self.adresse_id:
            return self.adresse_id
        elif self.uebergabeprotokoll_id:
            return self.uebergabeprotokoll_id
        return None
    
    def get_entity_display(self):
        """Get a display string for the linked entity."""
        if self.vertrag:
            return f"Vertrag: {self.vertrag}"
        elif self.mietobjekt:
            return f"Mietobjekt: {self.mietobjekt}"
        elif self.adresse:
            return f"Adresse: {self.adresse}"
        elif self.uebergabeprotokoll:
            return f"Übergabeprotokoll: {self.uebergabeprotokoll}"
        return "Unbekannt"
    
    def get_absolute_path(self):
        """Get the absolute filesystem path to the document."""
        return Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / self.storage_path
    
    def delete(self, *args, **kwargs):
        """Override delete to also remove the file from filesystem."""
        # Delete the file from filesystem
        file_path = self.get_absolute_path()
        if file_path.exists():
            file_path.unlink()
            
            # Try to remove empty parent directories
            try:
                parent = file_path.parent
                doc_root = Path(settings.VERMIETUNG_DOCUMENTS_ROOT)
                # Only clean up directories within document root
                while parent != doc_root and parent.is_relative_to(doc_root):
                    if not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                    else:
                        break
            except (OSError, RuntimeError, ValueError):
                pass  # Ignore errors when cleaning up directories
        
        super().delete(*args, **kwargs)
    
    @staticmethod
    def generate_storage_path(entity_type, entity_id, filename):
        """
        Generate storage path for a document.
        
        Path format: <entity_type>/<entity_id>/<filename>
        This prevents ID collisions between different entity types.
        
        Args:
            entity_type: Type of entity (vertrag, mietobjekt, adresse, uebergabeprotokoll)
            entity_id: ID of the entity
            filename: Name of the file
        
        Returns:
            Relative path string
        """
        return f"{entity_type}/{entity_id}/{filename}"
    
    @staticmethod
    def save_uploaded_file(uploaded_file, entity_type, entity_id):
        """
        Save an uploaded file to the filesystem.
        
        Args:
            uploaded_file: Django UploadedFile object
            entity_type: Type of entity (vertrag, mietobjekt, adresse, uebergabeprotokoll)
            entity_id: ID of the entity
        
        Returns:
            Tuple of (storage_path, mime_type)
        
        Raises:
            ValidationError: If file validation fails
        """
        # Validate file size
        validate_file_size(uploaded_file)
        
        # Validate file type and get MIME type
        mime_type = validate_file_type(uploaded_file)
        
        # Generate storage path
        storage_path = Dokument.generate_storage_path(
            entity_type, 
            entity_id, 
            uploaded_file.name
        )
        
        # Create absolute path
        absolute_path = Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / storage_path
        
        # Create directory if it doesn't exist
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(absolute_path, 'wb') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        return storage_path, mime_type


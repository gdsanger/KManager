
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.models import Adresse

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
        today = timezone.now().date()
        has_active_contract = self.vertraege.filter(
            status='active',
            start__lte=today
        ).filter(
            models.Q(ende__isnull=True) | models.Q(ende__gt=today)
        ).exists()
        
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
        self._update_mietobjekt_availability()
    
    def _update_mietobjekt_availability(self):
        """
        Update the availability of the associated MietObjekt.
        MietObjekt is available if there are no currently active contracts.
        """
        if not self.mietobjekt_id:
            return
        
        # Check if there are any currently active contracts for this MietObjekt
        today = timezone.now().date()
        has_active_contract = Vertrag.objects.filter(
            mietobjekt_id=self.mietobjekt_id,
            status='active',
            start__lte=today
        ).filter(
            models.Q(ende__isnull=True) | models.Q(ende__gt=today)
        ).exists()
        
        # Update the MietObjekt
        from django.db.models import F
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
    

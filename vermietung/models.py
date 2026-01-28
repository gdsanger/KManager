
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal, ROUND_HALF_UP
from core.models import Adresse, Mandant
import os
import magic
from pathlib import Path
from PIL import Image
import uuid
import logging
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

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

UMSATZSTEUER_SAETZE = [
    ('0', '0% Umsatzsteuer (steuerfrei)'),
    ('7', '7% Umsatzsteuer (Beherbergung)'),
    ('19', '19% Umsatzsteuer (Gewerbe)'),
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
    nebenkosten = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    kaution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Kaution",
        help_text="Kautions-Vorgabe (Standard: 3x Miete)"
    )
    verfuegbare_einheiten = models.IntegerField(
        default=1,
        verbose_name="Verfügbare Einheiten",
        help_text="Anzahl der verfügbaren Einheiten (für mehrfach vermietbare Objekte)"
    )
    volumen = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Volumen (m³)",
        help_text="Volumen in m³ (wird aus H×B×T berechnet, kann überschrieben werden)"
    )
    verfuegbar = models.BooleanField(default=True)
    mandant = models.ForeignKey(
        Mandant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Mandant",
        help_text="Zugeordneter Mandant für dieses Mietobjekt"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Übergeordnetes Mietobjekt",
        help_text="Übergeordnetes Mietobjekt (z.B. Gebäude für eine Wohnung)"
    )

    def __str__(self):
        return self.name
    
    @property
    def qm_mietpreis(self):
        """
        Berechnet den qm-Mietpreis (mietpreis / fläche).
        Rundet auf 2 Nachkommastellen.
        Gibt None zurück wenn fläche fehlt oder 0 ist.
        """
        if not self.fläche or self.fläche == 0:
            return None
        # Perform division and ensure result is Decimal
        result = Decimal(self.mietpreis) / Decimal(self.fläche)
        # Runde auf 2 Nachkommastellen
        return result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @property
    def volumen_berechnet(self):
        """
        Berechnet das Volumen aus Höhe × Breite × Tiefe.
        Rundet auf 3 Nachkommastellen.
        Gibt None zurück wenn eine der Dimensionen fehlt oder 0 ist.
        """
        if not all([self.höhe, self.breite, self.tiefe]) or any([
            self.höhe == 0, self.breite == 0, self.tiefe == 0
        ]):
            return None
        # Calculate volume: H × B × T
        result = Decimal(self.höhe) * Decimal(self.breite) * Decimal(self.tiefe)
        # Round to 3 decimal places
        return result.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    
    def get_volumen(self):
        """
        Gibt das Volumen zurück. Wenn volumen gesetzt ist (überschrieben),
        wird dieser Wert zurückgegeben, ansonsten das berechnete Volumen.
        
        Returns:
            Decimal or None: Das Volumen in m³
        """
        if self.volumen is not None:
            return self.volumen
        return self.volumen_berechnet
    
    def get_all_children(self, include_self=False):
        """
        Get all child MietObjekte recursively using an iterative approach
        to avoid N+1 queries.
        
        Args:
            include_self: If True, includes this object in the result
        
        Returns:
            QuerySet of all descendant MietObjekt objects
        """
        descendants_set = set()
        
        if include_self:
            descendants_set.add(self.pk)
        
        # Use iterative approach with a queue to avoid recursion and N+1 queries
        to_process = list(self.children.values_list('pk', flat=True))
        descendants_set.update(to_process)
        
        while to_process:
            # Get all children of all items in current batch in one query
            current_batch = to_process
            to_process = []
            
            # Single query to get all children of current batch
            new_children = list(
                MietObjekt.objects.filter(parent_id__in=current_batch)
                .values_list('pk', flat=True)
            )
            
            # Add new children to process and to descendants
            for child_pk in new_children:
                if child_pk not in descendants_set:
                    descendants_set.add(child_pk)
                    to_process.append(child_pk)
        
        return MietObjekt.objects.filter(pk__in=descendants_set)
    
    def get_hierarchy_level(self):
        """
        Get the level in the hierarchy (0 = root, 1 = direct child, etc.).
        
        Returns:
            int: Hierarchy level
        """
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level
    
    def get_root_parent(self):
        """
        Get the root parent (topmost MietObjekt in the hierarchy).
        
        Returns:
            MietObjekt: The root parent or self if this is already a root
        """
        if not self.parent:
            return self
        
        current = self.parent
        while current.parent:
            current = current.parent
        return current
    
    def get_all_vertraege(self):
        """
        Get all contracts (Vertrag) associated with this MietObjekt.
        Works with both new VertragsObjekt relationship and legacy mietobjekt field.
        
        Returns:
            QuerySet of Vertrag objects
        """
        # Collect contract IDs from both relationships
        contract_ids = set()
        
        # Get contract IDs from new VertragsObjekt relationship
        contract_ids.update(
            self.vertragsobjekte.values_list('vertrag_id', flat=True)
        )
        
        # Also get from legacy relationship (during migration period)
        contract_ids.update(
            self.vertraege_legacy.values_list('id', flat=True)
        )
        
        # Return queryset of all contracts with these IDs
        # Vertrag is defined later in this same file
        if contract_ids:
            return Vertrag.objects.filter(id__in=contract_ids)
        return Vertrag.objects.none()
    
    def get_active_units_count(self):
        """
        Count the total number of units currently in active contracts.
        A contract is currently active if:
        - Status is 'active'
        - start <= today
        - ende is NULL or ende > today
        
        Works with both new VertragsObjekt relationship and legacy mietobjekt field.
        
        Returns:
            int: Total number of units in active contracts
        """
        today = timezone.now().date()
        
        # Count units via VertragsObjekt (new n:m relationship)
        units_count = VertragsObjekt.objects.filter(
            mietobjekt=self,
            vertrag__status='active',
            vertrag__start__lte=today
        ).filter(
            Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=today)
        ).aggregate(
            total=models.Sum('anzahl')
        )['total'] or 0
        
        # Also check legacy relationship during migration period
        # Legacy contracts don't have anzahl, so we count them as 1 unit each
        # IMPORTANT: Exclude vertraege that already have a VertragsObjekt entry
        # to avoid double counting (since Vertrag.save() auto-creates VertragsObjekt
        # when legacy mietobjekt field is set)
        # Only consider VertragsObjekt entries for currently active contracts
        vertragsobjekt_vertrag_ids = VertragsObjekt.objects.filter(
            mietobjekt=self,
            vertrag__status='active',
            vertrag__start__lte=today
        ).filter(
            Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=today)
        ).values_list('vertrag_id', flat=True)
        
        legacy_count = self.vertraege_legacy.filter(
            status='active',
            start__lte=today
        ).filter(
            Q(ende__isnull=True) | Q(ende__gt=today)
        ).exclude(
            id__in=vertragsobjekt_vertrag_ids
        ).count()
        
        return units_count + legacy_count
    
    def get_available_units_count(self):
        """
        Calculate the number of units still available for booking.
        
        Returns:
            int: Number of units available (verfuegbare_einheiten - active units)
        """
        active_units = self.get_active_units_count()
        return max(0, self.verfuegbare_einheiten - active_units)
    
    def has_active_contracts(self):
        """
        Check if this MietObjekt has any currently active contracts.
        Now considers verfuegbare_einheiten: returns True if all units are rented.
        A contract is currently active if:
        - Status is 'active'
        - start <= today
        - ende is NULL or ende > today
        
        Works with both new VertragsObjekt relationship and legacy mietobjekt field.
        
        Returns:
            bool: True if all available units are in active contracts, False otherwise
        """
        active_units = self.get_active_units_count()
        return active_units >= self.verfuegbare_einheiten
    
    def clean(self):
        """
        Validate the MietObjekt data.
        """
        super().clean()
        
        # Validate verfuegbare_einheiten
        if self.verfuegbare_einheiten is not None and self.verfuegbare_einheiten < 1:
            raise ValidationError({
                'verfuegbare_einheiten': 'Die Anzahl der verfügbaren Einheiten muss mindestens 1 sein.'
            })
        
        # Validate parent field to prevent circular references
        if self.parent:
            # Check if parent is self
            if self.pk and self.parent.pk == self.pk:
                raise ValidationError({
                    'parent': 'Ein Mietobjekt kann nicht sein eigenes übergeordnetes Objekt sein.'
                })
            
            # Check for circular reference by traversing up the parent chain
            visited = set()
            if self.pk:
                visited.add(self.pk)
            
            current = self.parent
            while current:
                # If we've already seen this object, there's a cycle
                if current.pk in visited:
                    raise ValidationError({
                        'parent': 'Zirkuläre Referenz erkannt. Das gewählte übergeordnete Objekt würde eine Schleife erstellen.'
                    })
                visited.add(current.pk)
                
                # Move up the chain
                current = current.parent
    
    def save(self, *args, **kwargs):
        """
        Override save to set kaution default value for new objects.
        For new MietObjekt instances, kaution is pre-filled with 3 × mietpreis.
        """
        # Only set default kaution if this is a new object (no pk yet) and kaution is not already set
        if not self.pk and self.kaution is None:
            self.kaution = self.mietpreis * 3
        super().save(*args, **kwargs)
    
    def update_availability(self):
        """
        Update the availability based on currently active contracts.
        MietObjekt is available if there are no currently active contracts containing it.
        Works with both legacy vertraege and new vertragsobjekte relationships.
        """
        self.verfuegbar = not self.has_active_contracts()
        self.save(update_fields=['verfuegbar'])


class Vertrag(models.Model):
    """
    Rental contract model (Mietvertrag).
    A contract can contain multiple MietObjekte (n:m relationship via VertragsObjekt).
    A MietObjekt can have multiple contracts over time (history).
    """
    vertragsnummer = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        verbose_name="Vertragsnummer",
        help_text="Automatisch generierte Vertragsnummer im Format V-00000"
    )
    # Legacy field - will be removed after migration
    # Kept temporarily for backwards compatibility during migration
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.PROTECT,
        related_name='vertraege_legacy',
        verbose_name="Mietobjekt (Legacy)",
        null=True,
        blank=True
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
    umsatzsteuer_satz = models.CharField(
        max_length=2,
        choices=UMSATZSTEUER_SAETZE,
        default='19',
        verbose_name="Umsatzsteuer",
        help_text="Umsatzsteuersatz für diesen Vertrag"
    )
    mandant = models.ForeignKey(
        Mandant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Mandant",
        help_text="Zugeordneter Mandant für diesen Vertrag"
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
        Use select_related('mieter') and prefetch_related('vertragsobjekte__mietobjekt') in queries to avoid N+1 problems.
        """
        mieter_name = self.mieter.full_name() if self.mieter else 'Unbekannt'
        
        # For backwards compatibility during migration, check legacy field first
        if self.mietobjekt:
            mietobjekt_name = self.mietobjekt.name
        else:
            # Try to get from VertragsObjekt (new model)
            first_obj = self.vertragsobjekte.first()
            if first_obj:
                mietobjekt_name = first_obj.mietobjekt.name
                # If there are more objects, indicate that
                count = self.vertragsobjekte.count()
                if count > 1:
                    mietobjekt_name += f" (+{count-1} weitere)"
            else:
                mietobjekt_name = 'Kein Objekt'
        
        return f"{self.vertragsnummer} - {mietobjekt_name} ({mieter_name})"
    
    def get_mietobjekte(self):
        """
        Get all MietObjekt instances associated with this contract.
        Returns a queryset of MietObjekt objects.
        Works during migration by checking both legacy field and new VertragsObjekt.
        """
        mietobjekt_ids = set()
        
        # Legacy field (during migration)
        if self.mietobjekt_id:
            mietobjekt_ids.add(self.mietobjekt_id)
        
        # New VertragsObjekt relationship
        mietobjekt_ids.update(
            self.vertragsobjekte.values_list('mietobjekt_id', flat=True)
        )
        
        # Return queryset of all MietObjekt instances
        if mietobjekt_ids:
            return MietObjekt.objects.filter(id__in=mietobjekt_ids)
        return MietObjekt.objects.none()
    
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
    
    def berechne_gesamtmiete(self):
        """
        Calculate total rent from all VertragsObjekt items.
        Returns sum of (anzahl * preis) for all contract objects.
        Returns Decimal with 2 decimal places.
        """
        total = Decimal('0.00')
        for vo in self.vertragsobjekte.all():
            total += vo.gesamtpreis
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def berechne_umsatzsteuer(self):
        """
        Calculate VAT amount based on total rent (net amount) and VAT rate.
        Returns Decimal with 2 decimal places.
        """
        nettobetrag = self.berechne_gesamtmiete()
        umsatzsteuer_prozent = Decimal(self.umsatzsteuer_satz)
        umsatzsteuer_betrag = (nettobetrag * umsatzsteuer_prozent / Decimal('100'))
        return umsatzsteuer_betrag.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def berechne_bruttobetrag(self):
        """
        Calculate gross amount (net amount + VAT).
        Returns Decimal with 2 decimal places.
        """
        nettobetrag = self.berechne_gesamtmiete()
        umsatzsteuer = self.berechne_umsatzsteuer()
        bruttobetrag = nettobetrag + umsatzsteuer
        return bruttobetrag.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def clean(self):
        """
        Validate the contract data:
        1. If ende is set, it must be greater than start
        2. For backwards compatibility, check overlaps on legacy mietobjekt field
        
        Note: Overlap checking for new n:m relationship is handled in VertragsObjekt.clean()
        """
        super().clean()
        
        # Validate date range
        if self.ende and self.start and self.ende <= self.start:
            raise ValidationError({
                'ende': 'Das Vertragsende muss nach dem Vertragsbeginn liegen.'
            })
        
        # Backwards compatibility: Check for overlaps on legacy mietobjekt field
        # This is needed during migration period when tests/code still use the legacy field
        if self.mietobjekt_id and self.status == 'active':
            # Find other active contracts for this mietobjekt
            other_contracts = Vertrag.objects.filter(
                mietobjekt_id=self.mietobjekt_id,
                status='active'
            ).exclude(pk=self.pk if self.pk else None)
            
            # Check for date overlaps
            for contract in other_contracts:
                # Case 1: Existing contract has no end date (open-ended)
                if contract.ende is None:
                    if self.start >= contract.start:
                        raise ValidationError({
                            'mietobjekt': f'Es existiert bereits ein laufender Vertrag ohne Enddatum '
                                         f'({contract.vertragsnummer}) für dieses Mietobjekt ab {contract.start}.'
                        })
                    # New contract starts before existing open-ended contract
                    if self.ende is None or self.ende > contract.start:
                        raise ValidationError({
                            'mietobjekt': f'Dieser Vertrag würde mit einem bestehenden Vertrag '
                                         f'({contract.vertragsnummer}) überlappen, der am {contract.start} beginnt.'
                        })
                
                # Case 2: This contract has no end date
                elif self.ende is None:
                    # It blocks any existing contract that ends after this contract's start
                    if contract.start < self.start and (contract.ende is None or contract.ende > self.start):
                        raise ValidationError({
                            'mietobjekt': f'Ein Vertrag ohne Enddatum würde mit bestehendem Vertrag '
                                         f'({contract.vertragsnummer}) überlappen.'
                        })
                    # It blocks any existing contract that starts after this contract's start
                    if contract.start >= self.start:
                        raise ValidationError({
                            'mietobjekt': f'Ein Vertrag ohne Enddatum würde mit bestehendem Vertrag '
                                         f'({contract.vertragsnummer}) überlappen.'
                        })
                
                # Case 3: Both contracts have end dates
                else:
                    # Standard overlap check: A.start < B.end AND A.end > B.start
                    if self.start < contract.ende and self.ende > contract.start:
                        raise ValidationError({
                            'mietobjekt': f'Dieser Vertrag überschneidet sich mit bestehendem Vertrag '
                                         f'({contract.vertragsnummer}) von {contract.start} bis {contract.ende}.'
                        })
    
    
    def save(self, *args, **kwargs):
        """
        Override save to auto-generate contract number if not set.
        Uses database-level locking to prevent race conditions.
        Also handles backwards compatibility: if legacy mietobjekt field is set,
        automatically creates VertragsObjekt entry.
        Auto-inherits mandant from the first MietObjekt if not explicitly set.
        """
        if not self.vertragsnummer:
            self.vertragsnummer = self._generate_vertragsnummer()
        
        # Auto-inherit mandant from MietObjekt if not set
        # Only do this for new contracts or when mandant is None
        if not self.mandant_id:
            # Try legacy mietobjekt field first (during migration)
            if self.mietobjekt_id:
                try:
                    mietobjekt = MietObjekt.objects.get(pk=self.mietobjekt_id)
                    if mietobjekt.mandant_id:
                        self.mandant_id = mietobjekt.mandant_id
                except MietObjekt.DoesNotExist:
                    pass
            # If not set via legacy field and this is an existing contract, 
            # try to get from first VertragsObjekt
            elif self.pk:
                first_vo = self.vertragsobjekte.select_related('mietobjekt__mandant').first()
                if first_vo and first_vo.mietobjekt.mandant_id:
                    self.mandant_id = first_vo.mietobjekt.mandant_id
        
        # Run full_clean to trigger validation
        self.full_clean()
        
        is_new = self.pk is None
        had_legacy_mietobjekt = self.mietobjekt_id
        
        super().save(*args, **kwargs)
        
        # Backwards compatibility: If legacy mietobjekt field is used,
        # automatically create/update VertragsObjekt entry
        if had_legacy_mietobjekt:
            # Check if VertragsObjekt already exists for this combination
            existing = VertragsObjekt.objects.filter(
                vertrag=self,
                mietobjekt_id=had_legacy_mietobjekt
            ).exists()
            
            if not existing:
                # Create VertragsObjekt entry
                VertragsObjekt.objects.create(
                    vertrag=self,
                    mietobjekt_id=had_legacy_mietobjekt
                )
            
            # Update availability
            self.update_mietobjekte_availability()
    
    def update_mietobjekte_availability(self):
        """
        Update the availability of all associated MietObjekte.
        MietObjekt is available if there are no currently active contracts containing it.
        Public method that can be called from admin actions.
        """
        # Get all mietobjekte for this contract (both legacy and new)
        mietobjekt_ids = set()
        
        # Legacy field (during migration)
        if self.mietobjekt_id:
            mietobjekt_ids.add(self.mietobjekt_id)
        
        # New VertragsObjekt relationship
        mietobjekt_ids.update(
            self.vertragsobjekte.values_list('mietobjekt_id', flat=True)
        )
        
        # Update availability for each mietobjekt
        for mietobjekt_id in mietobjekt_ids:
            # Check if there are any currently active contracts containing this MietObjekt
            has_active_contract = VertragsObjekt.objects.filter(
                mietobjekt_id=mietobjekt_id,
                vertrag__status='active'
            ).select_related('vertrag').filter(
                vertrag__start__lte=timezone.now().date()
            ).filter(
                Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=timezone.now().date())
            ).exists()
            
            # Update the MietObjekt directly without triggering save
            MietObjekt.objects.filter(pk=mietobjekt_id).update(
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


VERTRAGSOBJEKT_STATUS = [
    ('AKTIV', 'Aktiv'),
    ('BEENDET', 'Beendet'),
]


class VertragsObjekt(models.Model):
    """
    Junction model for n:m relationship between Vertrag and MietObjekt.
    Represents a rental object within a contract.
    A contract can contain multiple rental objects, and a rental object can be in multiple contracts (over time).
    Each assignment includes pricing, quantity, dates, and status information.
    """
    vertrag = models.ForeignKey(
        Vertrag,
        on_delete=models.CASCADE,
        related_name='vertragsobjekte',
        verbose_name="Vertrag"
    )
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.PROTECT,
        related_name='vertragsobjekte',
        verbose_name="Mietobjekt"
    )
    preis = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Preis",
        help_text="Preis für dieses Mietobjekt im Vertrag"
    )
    anzahl = models.IntegerField(
        default=1,
        verbose_name="Anzahl",
        help_text="Anzahl der gemieteten Einheiten"
    )
    zugang = models.DateField(
        null=True,
        blank=True,
        verbose_name="Zugang",
        help_text="Datum des Zugangs (Übernahme)"
    )
    abgang = models.DateField(
        null=True,
        blank=True,
        verbose_name="Abgang",
        help_text="Datum des Abgangs (Rückgabe)"
    )
    status = models.CharField(
        max_length=20,
        choices=VERTRAGSOBJEKT_STATUS,
        default='AKTIV',
        verbose_name="Status",
        help_text="Status dieses Mietobjekts im Vertrag"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
        help_text="Zeitpunkt der Zuordnung"
    )
    
    class Meta:
        verbose_name = "Vertragsobjekt"
        verbose_name_plural = "Vertragsobjekte"
        # Ensure a mietobjekt can only be added once to a contract
        unique_together = [['vertrag', 'mietobjekt']]
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.vertrag.vertragsnummer} - {self.mietobjekt.name}"
    
    @property
    def gesamtpreis(self):
        """
        Calculate total price for this contract object: anzahl * preis.
        Returns Decimal with 2 decimal places.
        """
        if self.preis is None or self.anzahl is None:
            return Decimal('0.00')
        return (Decimal(str(self.anzahl)) * Decimal(str(self.preis))).quantize(
            Decimal('0.01'), 
            rounding=ROUND_HALF_UP
        )
    
    def clean(self):
        """
        Validate the contract object data:
        1. Price must be positive
        2. Quantity must be positive
        3. If abgang is set, it must be after zugang
        4. Check if there are enough available units for this mietobjekt (only for active contracts)
        """
        super().clean()
        
        # Validate price
        if self.preis is not None and self.preis < 0:
            raise ValidationError({
                'preis': 'Der Preis darf nicht negativ sein.'
            })
        
        # Validate quantity
        if self.anzahl is not None and self.anzahl <= 0:
            raise ValidationError({
                'anzahl': 'Die Anzahl muss mindestens 1 sein.'
            })
        
        # Validate date range
        if self.zugang and self.abgang and self.abgang < self.zugang:
            raise ValidationError({
                'abgang': 'Das Abgangsdatum muss nach dem Zugangsdatum liegen oder am gleichen Tag sein.'
            })
        
        # Only validate availability if this is for an active contract
        if not self.vertrag_id or self.vertrag.status != 'active':
            return
        
        # Check if there are enough available units for this mietobjekt
        # A contract is currently active if status='active' and start <= today and (ende is NULL or ende > today)
        if not self.mietobjekt_id:
            return
        
        today = timezone.now().date()
        
        # Get the MietObjekt to check available units
        try:
            mietobjekt = MietObjekt.objects.get(pk=self.mietobjekt_id)
        except MietObjekt.DoesNotExist:
            return
        
        # Count units already in other active contracts
        active_units = VertragsObjekt.objects.filter(
            mietobjekt=self.mietobjekt,
            vertrag__status='active',
            vertrag__start__lte=today
        ).filter(
            Q(vertrag__ende__isnull=True) | Q(vertrag__ende__gt=today)
        ).exclude(
            pk=self.pk if self.pk else None
        ).aggregate(
            total=models.Sum('anzahl')
        )['total'] or 0
        
        # Check if adding this contract would exceed available units
        requested_units = self.anzahl or 1
        if active_units + requested_units > mietobjekt.verfuegbare_einheiten:
            available = mietobjekt.verfuegbare_einheiten - active_units
            raise ValidationError({
                'anzahl': f'Nicht genügend Einheiten verfügbar. '
                         f'Verfügbare Einheiten: {mietobjekt.verfuegbare_einheiten}, '
                         f'bereits vergeben: {active_units}, '
                         f'noch verfügbar: {available}.'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to set default price from mietobjekt if not provided.
        Also runs validation and updates MietObjekt availability.
        
        Note: We update availability immediately after save to ensure the
        MietObjekt.verfuegbar field is always current. This is acceptable
        since VertragsObjekt instances are typically created/updated one
        at a time through the UI. For bulk operations, consider using
        MietObjekt.update_availability() separately after the bulk operation.
        """
        # Set default price from mietobjekt if not provided
        if self.preis is None and self.mietobjekt_id:
            try:
                mietobjekt = MietObjekt.objects.get(pk=self.mietobjekt_id)
                self.preis = mietobjekt.mietpreis
            except MietObjekt.DoesNotExist:
                pass
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update MietObjekt availability after saving
        # This ensures the verfuegbar field is always current
        if self.mietobjekt_id:
            try:
                mietobjekt = MietObjekt.objects.get(pk=self.mietobjekt_id)
                mietobjekt.update_availability()
            except MietObjekt.DoesNotExist:
                pass


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
        1. MietObjekt must belong to the Vertrag (via VertragsObjekt or legacy field)
        2. Uebergabetag should be within or near the contract period
        """
        super().clean()
        
        # Validate that MietObjekt belongs to the Vertrag
        # Use _id fields to avoid triggering additional queries
        if self.vertrag_id and self.mietobjekt_id:
            # Check if mietobjekt is in this vertrag (via VertragsObjekt or legacy field)
            is_in_vertrag = False
            
            # Check new VertragsObjekt relationship
            is_in_vertrag = VertragsObjekt.objects.filter(
                vertrag_id=self.vertrag_id,
                mietobjekt_id=self.mietobjekt_id
            ).exists()
            
            # Also check legacy field during migration
            if not is_in_vertrag:
                vertrag_legacy_mietobjekt_id = Vertrag.objects.filter(
                    pk=self.vertrag_id
                ).values_list('mietobjekt_id', flat=True).first()
                is_in_vertrag = (vertrag_legacy_mietobjekt_id == self.mietobjekt_id)
            
            if not is_in_vertrag:
                # Get available mietobjekte names for better error message
                vertrag_mietobjekte = []
                
                # Get from VertragsObjekt
                vertrag_mietobjekte.extend(
                    VertragsObjekt.objects.filter(
                        vertrag_id=self.vertrag_id
                    ).values_list('mietobjekt__name', flat=True)
                )
                
                # Get from legacy field
                legacy_name = Vertrag.objects.filter(
                    pk=self.vertrag_id,
                    mietobjekt__isnull=False
                ).values_list('mietobjekt__name', flat=True).first()
                if legacy_name:
                    vertrag_mietobjekte.append(legacy_name)
                
                if vertrag_mietobjekte:
                    mietobjekte_str = ', '.join(f'"{name}"' for name in vertrag_mietobjekte)
                    raise ValidationError({
                        'mietobjekt': f'Das Mietobjekt muss zum Vertrag gehören. '
                                     f'Verfügbare Objekte: {mietobjekte_str}.'
                    })
                else:
                    raise ValidationError({
                        'mietobjekt': 'Das Mietobjekt muss zum Vertrag gehören. '
                                     'Dieser Vertrag hat keine zugeordneten Objekte.'
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
    'image/webp': ['.webp'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

# Allowed MIME types for images (used in MietObjektBild)
ALLOWED_IMAGE_MIME_TYPES = {
    'image/png': ['.png'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp'],
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
        try:
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {absolute_path.parent}")
        except Exception as e:
            logger.error(
                f"Failed to create directory {absolute_path.parent}: {e}",
                exc_info=True
            )
            raise ValidationError(
                f'Fehler beim Erstellen des Verzeichnisses: {e}'
            )
        
        # Save file
        try:
            with open(absolute_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            logger.debug(f"Saved document to: {absolute_path}")
        except Exception as e:
            logger.error(
                f"Failed to save file {absolute_path}: {e}",
                exc_info=True
            )
            raise ValidationError(
                f'Fehler beim Speichern der Datei: {e}'
            )
        
        return storage_path, mime_type


def validate_image_file_size(file):
    """Validate that image file size does not exceed maximum allowed size."""
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            f'Die Bildgröße ({file.size / (1024*1024):.2f} MB) überschreitet '
            f'das Maximum von {MAX_FILE_SIZE / (1024*1024):.0f} MB.'
        )


def validate_image_file_type(file):
    """
    Validate that file type is one of the allowed image types.
    
    Returns:
        str: The detected MIME type if valid
    
    Raises:
        ValidationError: If file type is not allowed
    """
    # Read file content to detect MIME type
    file.seek(0)
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    
    if mime not in ALLOWED_IMAGE_MIME_TYPES:
        allowed_extensions = []
        for extensions in ALLOWED_IMAGE_MIME_TYPES.values():
            allowed_extensions.extend(extensions)
        raise ValidationError(
            f'Bildtyp "{mime}" ist nicht erlaubt. '
            f'Erlaubte Typen: {", ".join(sorted(set(allowed_extensions)))}'
        )
    
    # Also check file extension matches MIME type
    filename = file.name.lower()
    expected_extensions = ALLOWED_IMAGE_MIME_TYPES.get(mime, [])
    if not any(filename.endswith(ext) for ext in expected_extensions):
        raise ValidationError(
            f'Dateierweiterung passt nicht zum erkannten Bildtyp "{mime}". '
            f'Erwartete Erweiterungen: {", ".join(expected_extensions)}'
        )
    
    return mime


class MietObjektBild(models.Model):
    """
    Image model for MietObjekt gallery.
    
    Images are stored in the filesystem under /data/vermietung/mietobjekt/<id>/images/
    Both original and thumbnail are stored.
    Metadata is stored in the database.
    """
    # Foreign key to MietObjekt
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.CASCADE,
        related_name='bilder',
        verbose_name="Mietobjekt"
    )
    
    # Original filename
    original_filename = models.CharField(
        max_length=255,
        verbose_name="Originaler Dateiname",
        help_text="Der ursprüngliche Dateiname beim Upload"
    )
    
    # Storage paths (relative to VERMIETUNG_DOCUMENTS_ROOT)
    storage_path = models.CharField(
        max_length=500,
        verbose_name="Speicherpfad (Original)",
        help_text="Relativer Pfad zum Original-Bild"
    )
    
    thumbnail_path = models.CharField(
        max_length=500,
        verbose_name="Speicherpfad (Thumbnail)",
        help_text="Relativer Pfad zum Thumbnail"
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
        help_text="Benutzer, der das Bild hochgeladen hat"
    )
    
    class Meta:
        verbose_name = "Mietobjekt Bild"
        verbose_name_plural = "Mietobjekt Bilder"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        """String representation of the image."""
        return f"{self.original_filename} ({self.mietobjekt.name})"
    
    def get_absolute_path(self):
        """Get the absolute filesystem path to the original image."""
        return Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / self.storage_path
    
    def get_thumbnail_absolute_path(self):
        """Get the absolute filesystem path to the thumbnail."""
        return Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / self.thumbnail_path
    
    def delete(self, *args, **kwargs):
        """Override delete to also remove the files from filesystem."""
        # Delete original file
        original_path = self.get_absolute_path()
        if original_path.exists():
            original_path.unlink()
        
        # Delete thumbnail
        thumbnail_path = self.get_thumbnail_absolute_path()
        if thumbnail_path.exists():
            thumbnail_path.unlink()
        
        # Try to remove empty parent directories
        try:
            parent = original_path.parent
            doc_root = Path(settings.VERMIETUNG_DOCUMENTS_ROOT)
            # Only clean up directories within document root
            # Note: is_relative_to() requires Python >= 3.9
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
    def generate_storage_paths(mietobjekt_id, filename):
        """
        Generate storage paths for original and thumbnail images.
        
        Path format: mietobjekt/<id>/images/<uuid>_<filename>
        Thumbnail: mietobjekt/<id>/images/thumb_<uuid>_<filename>
        
        Args:
            mietobjekt_id: ID of the MietObjekt
            filename: Name of the file
        
        Returns:
            Tuple of (original_path, thumbnail_path)
        """
        # Generate unique filename to prevent collisions
        unique_id = uuid.uuid4().hex[:8]
        safe_filename = f"{unique_id}_{filename}"
        
        original_path = f"mietobjekt/{mietobjekt_id}/images/{safe_filename}"
        thumbnail_path = f"mietobjekt/{mietobjekt_id}/images/thumb_{safe_filename}"
        
        return original_path, thumbnail_path
    
    @staticmethod
    def create_thumbnail(original_path, thumbnail_path, size=(300, 300)):
        """
        Create a thumbnail from the original image.
        
        Args:
            original_path: Path to the original image
            thumbnail_path: Path where thumbnail should be saved
            size: Tuple of (width, height) for thumbnail size
        """
        # Open original image
        img = Image.open(original_path)
        
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Create thumbnail (maintains aspect ratio)
        # Using Image.LANCZOS for compatibility (Image.Resampling.LANCZOS in Pillow >= 10.0.0)
        img.thumbnail(size, Image.LANCZOS)
        
        # Save thumbnail
        img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
    
    @staticmethod
    def save_uploaded_image(uploaded_file, mietobjekt_id, user=None):
        """
        Save an uploaded image file with thumbnail generation.
        
        Args:
            uploaded_file: Django UploadedFile object
            mietobjekt_id: ID of the MietObjekt
            user: User who uploaded the file (optional)
        
        Returns:
            MietObjektBild instance
        
        Raises:
            ValidationError: If file validation fails
        """
        # Validate file size
        validate_image_file_size(uploaded_file)
        
        # Validate file type and get MIME type
        mime_type = validate_image_file_type(uploaded_file)
        
        # Generate storage paths
        storage_path, thumbnail_path = MietObjektBild.generate_storage_paths(
            mietobjekt_id,
            uploaded_file.name
        )
        
        # Create absolute paths
        absolute_path = Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / storage_path
        absolute_thumbnail_path = Path(settings.VERMIETUNG_DOCUMENTS_ROOT) / thumbnail_path
        
        # Create directory if it doesn't exist
        try:
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {absolute_path.parent}")
        except Exception as e:
            logger.error(
                f"Failed to create directory {absolute_path.parent}: {e}",
                exc_info=True
            )
            raise ValidationError(
                f'Fehler beim Erstellen des Verzeichnisses: {e}'
            )
        
        # Save original file
        try:
            with open(absolute_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            logger.debug(f"Saved original image to: {absolute_path}")
        except Exception as e:
            logger.error(
                f"Failed to save file {absolute_path}: {e}",
                exc_info=True
            )
            raise ValidationError(
                f'Fehler beim Speichern der Datei: {e}'
            )
        
        # Generate thumbnail
        try:
            MietObjektBild.create_thumbnail(absolute_path, absolute_thumbnail_path)
            logger.debug(f"Created thumbnail at: {absolute_thumbnail_path}")
        except Exception as e:
            # If thumbnail creation fails, delete the original and raise error
            logger.error(
                f"Failed to create thumbnail for {absolute_path}: {e}",
                exc_info=True
            )
            if absolute_path.exists():
                absolute_path.unlink()
            raise ValidationError(f'Fehler beim Erstellen des Thumbnails: {e}')
        
        # Create database entry
        try:
            bild = MietObjektBild(
                mietobjekt_id=mietobjekt_id,
                original_filename=uploaded_file.name,
                storage_path=storage_path,
                thumbnail_path=thumbnail_path,
                file_size=uploaded_file.size,
                mime_type=mime_type,
                uploaded_by=user
            )
            bild.save()
            logger.info(
                f"Successfully uploaded image '{uploaded_file.name}' "
                f"for MietObjekt {mietobjekt_id}"
            )
        except Exception as e:
            # Clean up files if database save fails
            logger.error(
                f"Failed to save database record for {uploaded_file.name}: {e}",
                exc_info=True
            )
            if absolute_path.exists():
                absolute_path.unlink()
            if absolute_thumbnail_path.exists():
                absolute_thumbnail_path.unlink()
            raise ValidationError(
                f'Fehler beim Speichern der Datenbank-Einträge: {e}'
            )
        
        return bild


# Status choices for Aktivitaet
AKTIVITAET_STATUS = [
    ('OFFEN', 'Offen'),
    ('IN_BEARBEITUNG', 'In Bearbeitung'),
    ('ERLEDIGT', 'Erledigt'),
    ('ABGEBROCHEN', 'Abgebrochen'),
]

# Priority choices for Aktivitaet
AKTIVITAET_PRIORITAET = [
    ('NIEDRIG', 'Niedrig'),
    ('NORMAL', 'Normal'),
    ('HOCH', 'Hoch'),
]


class Aktivitaet(models.Model):
    """
    Task/Activity model for the Vermietung module.
    
    Each activity is linked to exactly one context:
    - MietObjekt (rental object)
    - Vertrag (contract)
    - Kunde (customer address)
    
    Assignment is flexible and optional:
    - Can be assigned to internal user (assigned_user)
    - Can be assigned to external supplier (assigned_supplier)
    - Can be assigned to both
    - Can be unassigned
    """
    # Core fields
    titel = models.CharField(
        max_length=200,
        verbose_name="Titel",
        help_text="Titel der Aktivität"
    )
    
    beschreibung = models.TextField(
        blank=True,
        verbose_name="Beschreibung",
        help_text="Detaillierte Beschreibung der Aktivität"
    )
    
    status = models.CharField(
        max_length=20,
        choices=AKTIVITAET_STATUS,
        default='OFFEN',
        verbose_name="Status",
        help_text="Status der Aktivität"
    )
    
    prioritaet = models.CharField(
        max_length=20,
        choices=AKTIVITAET_PRIORITAET,
        default='NORMAL',
        verbose_name="Priorität",
        help_text="Priorität der Aktivität"
    )
    
    faellig_am = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fällig am",
        help_text="Fälligkeitsdatum der Aktivität"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
        help_text="Zeitpunkt der Erstellung"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am",
        help_text="Zeitpunkt der letzten Aktualisierung"
    )
    
    # Context fields (exactly one must be set)
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='aktivitaeten',
        verbose_name="Mietobjekt"
    )
    
    vertrag = models.ForeignKey(
        Vertrag,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='aktivitaeten',
        verbose_name="Vertrag"
    )
    
    kunde = models.ForeignKey(
        Adresse,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='aktivitaeten',
        verbose_name="Kunde",
        limit_choices_to={'adressen_type': 'KUNDE'}
    )
    
    # Assignment fields (both optional, flexible combinations)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aktivitaeten',
        verbose_name="Zugewiesen an (Intern)",
        help_text="Interner Benutzer, dem die Aktivität zugewiesen ist"
    )
    
    assigned_supplier = models.ForeignKey(
        Adresse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aktivitaeten_als_lieferant',
        verbose_name="Zugewiesen an (Extern)",
        help_text="Externer Lieferant, dem die Aktivität zugewiesen ist",
        limit_choices_to={'adressen_type': 'LIEFERANT'}
    )
    
    # Creator field - who created this activity
    ersteller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='aktivitaeten_erstellt',
        verbose_name="Ersteller",
        help_text="Benutzer, der diese Aktivität erstellt hat"
    )
    
    # Series/recurring activity fields
    ist_serie = models.BooleanField(
        default=False,
        verbose_name="Serien-Aktivität",
        help_text="Ist dies eine wiederkehrende Aktivität?"
    )
    
    intervall_monate = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Intervall (Monate)",
        help_text="Intervall in Monaten für wiederkehrende Aktivitäten (1-12)",
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    
    serien_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Serien-ID",
        help_text="Eindeutige ID zur Gruppierung von Aktivitäten einer Serie"
    )
    
    class Meta:
        verbose_name = "Aktivität"
        verbose_name_plural = "Aktivitäten"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['faellig_am']),
            models.Index(fields=['assigned_user']),
            models.Index(fields=['assigned_supplier']),
            models.Index(fields=['ersteller']),
            models.Index(fields=['ist_serie']),
            models.Index(fields=['serien_id']),
        ]
    
    def __str__(self):
        """String representation of the activity."""
        return f"{self.titel} ({self.get_status_display()})"
    
    def clean(self):
        """
        Validate the activity data:
        1. Exactly one context must be set (mietobjekt, vertrag, or kunde)
        2. If assigned_supplier is set, it must be of type LIEFERANT
        3. If ist_serie is True, intervall_monate must be set
        """
        super().clean()
        
        # Check context constraint: exactly one must be set
        context_fields = [
            self.mietobjekt_id,
            self.vertrag_id,
            self.kunde_id
        ]
        set_contexts = [field for field in context_fields if field is not None]
        
        if len(set_contexts) == 0:
            raise ValidationError(
                'Die Aktivität muss genau einem Kontext zugeordnet werden '
                '(Mietobjekt, Vertrag oder Kunde).'
            )
        
        if len(set_contexts) > 1:
            raise ValidationError(
                'Die Aktivität kann nur einem einzigen Kontext zugeordnet werden '
                '(Mietobjekt, Vertrag oder Kunde).'
            )
        
        # Check assigned_supplier is of type LIEFERANT
        if self.assigned_supplier_id:
            # We need to check the actual adressen_type
            # Use _id to avoid additional queries during validation
            supplier = Adresse.objects.filter(
                pk=self.assigned_supplier_id
            ).values_list('adressen_type', flat=True).first()
            
            if supplier != 'LIEFERANT':
                raise ValidationError({
                    'assigned_supplier': 'Die zugewiesene Adresse muss vom Typ "Lieferant" sein.'
                })
        
        # Check series fields consistency
        if self.ist_serie:
            if not self.intervall_monate:
                raise ValidationError({
                    'intervall_monate': 'Intervall muss für Serien-Aktivitäten angegeben werden.'
                })
            if self.intervall_monate < 1 or self.intervall_monate > 12:
                raise ValidationError({
                    'intervall_monate': 'Intervall muss zwischen 1 und 12 Monaten liegen.'
                })
        
        # If not a series activity, clear series-related fields
        if not self.ist_serie:
            self.intervall_monate = None
    
    def save(self, *args, **kwargs):
        """
        Override save to run validation and handle series logic.
        When a series activity is marked as ERLEDIGT, create the next one.
        """
        # Track if status changed to ERLEDIGT
        status_changed_to_erledigt = False
        if self.pk:  # Existing instance
            old_instance = Aktivitaet.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.status != 'ERLEDIGT' and self.status == 'ERLEDIGT':
                status_changed_to_erledigt = True
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Create next activity in series if applicable
        if status_changed_to_erledigt and self.ist_serie and self.intervall_monate:
            self.create_next_series_activity()
    
    def create_next_series_activity(self):
        """
        Create the next activity in a recurring series.
        Called automatically when a series activity is marked as ERLEDIGT.
        """
        from datetime import date
        
        # Generate serien_id if not set
        if not self.serien_id:
            self.serien_id = uuid.uuid4()
            # Save without triggering save logic again
            Aktivitaet.objects.filter(pk=self.pk).update(serien_id=self.serien_id)
        
        # Calculate new due date
        new_faellig_am = None
        if self.faellig_am:
            new_faellig_am = self.faellig_am + relativedelta(months=self.intervall_monate)
        
        # Create the next activity
        next_activity = Aktivitaet(
            titel=self.titel,
            beschreibung=self.beschreibung,
            status='OFFEN',
            prioritaet=self.prioritaet,
            faellig_am=new_faellig_am,
            mietobjekt=self.mietobjekt,
            vertrag=self.vertrag,
            kunde=self.kunde,
            assigned_user=self.assigned_user,
            assigned_supplier=self.assigned_supplier,
            ersteller=self.ersteller,
            ist_serie=True,
            intervall_monate=self.intervall_monate,
            serien_id=self.serien_id
        )
        
        # Use update_fields to avoid triggering validation in save
        next_activity.save(update_fields=None)
    
    def get_context_display(self):
        """Get a display string for the linked context."""
        if self.mietobjekt:
            return f"Mietobjekt: {self.mietobjekt}"
        elif self.vertrag:
            return f"Vertrag: {self.vertrag}"
        elif self.kunde:
            return f"Kunde: {self.kunde}"
        return "Kein Kontext"


# Meter type choices
ZAEHLER_TYPEN = [
    ('STROM', 'Strom'),
    ('GAS', 'Gas'),
    ('WASSER', 'Wasser'),
    ('HEIZUNG', 'Heizung'),
    ('KUEHLUNG', 'Kühlung'),
]

# Unit mapping for meter types
ZAEHLER_EINHEITEN = {
    'STROM': 'kWh',
    'GAS': 'm³',
    'WASSER': 'm³',
    'HEIZUNG': 'kWh',
    'KUEHLUNG': 'kWh',
}


class Zaehler(models.Model):
    """
    Meter model for tracking utility consumption in rental properties.
    
    Each meter is linked to a MietObjekt and can optionally have a parent meter
    for sub-meter functionality. Sub-meters' consumption is subtracted from their
    parent meter's consumption.
    """
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.CASCADE,
        related_name='zaehler',
        verbose_name="Mietobjekt"
    )
    
    typ = models.CharField(
        max_length=20,
        choices=ZAEHLER_TYPEN,
        verbose_name="Zählertyp",
        help_text="Typ des Zählers (Strom, Gas, Wasser, Heizung, Kühlung)"
    )
    
    bezeichnung = models.CharField(
        max_length=255,
        verbose_name="Bezeichnung",
        help_text="Beschreibende Bezeichnung des Zählers (z.B. 'Wohnung EG links', 'Garage 1–3')"
    )
    
    einheit = models.CharField(
        max_length=20,
        verbose_name="Einheit",
        help_text="Maßeinheit (kWh, m³, etc.)"
    )
    
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='sub_zaehler',
        verbose_name="Übergeordneter Zähler",
        help_text="Optional: Hauptzähler, wenn dieser Zähler ein Zwischenzähler ist"
    )
    
    class Meta:
        verbose_name = "Zähler"
        verbose_name_plural = "Zähler"
        ordering = ['mietobjekt', 'typ', 'bezeichnung']
    
    def __str__(self):
        """String representation of the meter."""
        parent_info = f" (Zwischenzähler von {self.parent.bezeichnung})" if self.parent else ""
        return f"{self.bezeichnung} ({self.get_typ_display()}) - {self.mietobjekt.name}{parent_info}"
    
    def clean(self):
        """
        Validate meter data:
        1. Parent meter must have the same type
        2. No circular parent relationships
        3. Einheit must match the type
        """
        super().clean()
        
        # Validate parent type matches
        if self.parent:
            if self.parent.typ != self.typ:
                raise ValidationError({
                    'parent': f'Der übergeordnete Zähler muss denselben Typ haben ({self.get_typ_display()}).'
                })
            
            # Check for circular references
            current = self.parent
            visited = {self.pk} if self.pk else set()
            
            while current:
                if current.pk in visited:
                    raise ValidationError({
                        'parent': 'Zyklische Zählerstrukturen sind nicht erlaubt.'
                    })
                visited.add(current.pk)
                current = current.parent
        
        # Validate einheit matches typ
        expected_einheit = ZAEHLER_EINHEITEN.get(self.typ)
        if expected_einheit and self.einheit != expected_einheit:
            raise ValidationError({
                'einheit': f'Die Einheit für {self.get_typ_display()} sollte {expected_einheit} sein.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to set einheit from typ if not provided."""
        # Auto-set einheit based on typ
        if not self.einheit and self.typ:
            self.einheit = ZAEHLER_EINHEITEN.get(self.typ, '')
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_letzter_zaehlerstand(self):
        """
        Get the most recent meter reading.
        
        Returns:
            Zaehlerstand instance or None if no readings exist
        """
        return self.staende.order_by('-datum').first()
    
    def berechne_verbrauch(self, von_datum=None, bis_datum=None):
        """
        Calculate consumption between two dates.
        
        Args:
            von_datum: Start date (inclusive). If None, uses oldest reading.
            bis_datum: End date (inclusive). If None, uses newest reading.
        
        Returns:
            Decimal: Consumption or None if insufficient data
        """
        staende = self.staende.order_by('datum')
        
        if von_datum:
            staende = staende.filter(datum__gte=von_datum)
        if bis_datum:
            staende = staende.filter(datum__lte=bis_datum)
        
        if staende.count() < 2:
            return None
        
        erster_stand = staende.first()
        letzter_stand = staende.last()
        
        return letzter_stand.wert - erster_stand.wert
    
    def berechne_effektiver_verbrauch(self, von_datum=None, bis_datum=None):
        """
        Calculate effective consumption (consumption - sum of sub-meter consumption).
        
        Only applies to meters with sub-meters. For meters without sub-meters,
        returns the same as berechne_verbrauch().
        
        Args:
            von_datum: Start date (inclusive). If None, uses oldest reading.
            bis_datum: End date (inclusive). If None, uses newest reading.
        
        Returns:
            Decimal: Effective consumption or None if insufficient data
        """
        verbrauch = self.berechne_verbrauch(von_datum, bis_datum)
        
        if verbrauch is None:
            return None
        
        # Subtract consumption of all sub-meters
        sub_verbrauch = Decimal('0.00')
        for sub_zaehler in self.sub_zaehler.all():
            sub_v = sub_zaehler.berechne_verbrauch(von_datum, bis_datum)
            if sub_v is not None:
                sub_verbrauch += sub_v
        
        return verbrauch - sub_verbrauch


class Zaehlerstand(models.Model):
    """
    Meter reading model for recording readings at specific dates.
    
    Each reading is linked to a Zaehler and includes a date and value.
    Consumption is calculated from differences between readings.
    """
    zaehler = models.ForeignKey(
        Zaehler,
        on_delete=models.CASCADE,
        related_name='staende',
        verbose_name="Zähler"
    )
    
    datum = models.DateField(
        verbose_name="Datum",
        help_text="Datum der Ablesung"
    )
    
    wert = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name="Zählerstand",
        help_text="Wert des Zählerstands (z.B. kWh, m³)"
    )
    
    class Meta:
        verbose_name = "Zählerstand"
        verbose_name_plural = "Zählerstände"
        ordering = ['-datum']
        # Ensure only one reading per meter per date
        unique_together = [['zaehler', 'datum']]
    
    def __str__(self):
        """String representation of the meter reading."""
        return f"{self.zaehler.bezeichnung} - {self.datum}: {self.wert} {self.zaehler.einheit}"
    
    def clean(self):
        """
        Validate meter reading data:
        1. Reading value must be non-negative
        2. Reading must be chronologically plausible (not less than previous reading)
        """
        super().clean()
        
        # Validate non-negative
        if self.wert < 0:
            raise ValidationError({
                'wert': 'Der Zählerstand darf nicht negativ sein.'
            })
        
        # Validate chronological plausibility (value should not decrease)
        if self.zaehler_id:
            # Get the previous reading (closest date before this one)
            previous = Zaehlerstand.objects.filter(
                zaehler=self.zaehler,
                datum__lt=self.datum
            ).order_by('-datum').first()
            
            if previous and self.wert < previous.wert:
                raise ValidationError({
                    'wert': f'Der neue Zählerstand ({self.wert}) kann nicht kleiner sein als der '
                           f'vorherige Stand vom {previous.datum} ({previous.wert} {self.zaehler.einheit}).'
                })
            
            # Also check if there's a later reading that would be violated
            later = Zaehlerstand.objects.filter(
                zaehler=self.zaehler,
                datum__gt=self.datum
            ).exclude(
                pk=self.pk if self.pk else None
            ).order_by('datum').first()
            
            if later and self.wert > later.wert:
                raise ValidationError({
                    'wert': f'Der Zählerstand ({self.wert}) kann nicht größer sein als der '
                           f'spätere Stand vom {later.datum} ({later.wert} {self.zaehler.einheit}).'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)



EINGANGSRECHNUNG_STATUS = [
    ('NEU', 'Neu'),
    ('PRUEFUNG', 'Prüfung'),
    ('OFFEN', 'Offen'),
    ('KLAERUNG', 'Klärung'),
    ('BEZAHLT', 'Bezahlt'),
]


class Eingangsrechnung(models.Model):
    """Incoming invoice for rental property costs (utilities, energy, repairs, etc.)"""
    
    # Supplier and property
    lieferant = models.ForeignKey(
        Adresse,
        on_delete=models.PROTECT,
        limit_choices_to={'adressen_type': 'LIEFERANT'},
        verbose_name="Lieferant",
        related_name='eingangsrechnungen'
    )
    mietobjekt = models.ForeignKey(
        MietObjekt,
        on_delete=models.PROTECT,
        verbose_name="Mietobjekt",
        related_name='eingangsrechnungen'
    )
    
    # Document details
    belegdatum = models.DateField(verbose_name="Belegdatum")
    faelligkeit = models.DateField(verbose_name="Fälligkeit")
    belegnummer = models.CharField(max_length=100, verbose_name="Belegnummer")
    betreff = models.CharField(max_length=200, verbose_name="Betreff")
    referenznummer = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referenznummer"
    )
    
    # Service period (optional)
    leistungszeitraum_von = models.DateField(
        blank=True,
        null=True,
        verbose_name="Leistungszeitraum von"
    )
    leistungszeitraum_bis = models.DateField(
        blank=True,
        null=True,
        verbose_name="Leistungszeitraum bis"
    )
    
    # Notes
    notizen = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notizen"
    )
    
    # Status and payment
    status = models.CharField(
        max_length=20,
        choices=EINGANGSRECHNUNG_STATUS,
        default='NEU',
        verbose_name="Status"
    )
    zahlungsdatum = models.DateField(
        blank=True,
        null=True,
        verbose_name="Zahlungsdatum"
    )
    
    # Allocation
    umlagefaehig = models.BooleanField(
        default=True,
        verbose_name="Umlagefähig"
    )
    
    # Audit fields
    erstellt_am = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    geaendert_am = models.DateTimeField(auto_now=True, verbose_name="Geändert am")
    
    class Meta:
        verbose_name = "Eingangsrechnung"
        verbose_name_plural = "Eingangsrechnungen"
        ordering = ['-belegdatum', '-erstellt_am']
    
    def __str__(self):
        return f"{self.belegnummer} - {self.lieferant.name} - {self.belegdatum}"
    
    @property
    def nettobetrag(self):
        """Calculate net amount from all allocations"""
        return sum(
            aufteilung.nettobetrag or Decimal('0')
            for aufteilung in self.aufteilungen.all()
        )
    
    @property
    def umsatzsteuer(self):
        """Calculate VAT from all allocations"""
        return sum(
            aufteilung.umsatzsteuer or Decimal('0')
            for aufteilung in self.aufteilungen.all()
        )
    
    @property
    def bruttobetrag(self):
        """Calculate gross amount (net + VAT)"""
        return self.nettobetrag + self.umsatzsteuer
    
    def clean(self):
        """Validate the invoice"""
        super().clean()
        errors = {}
        
        # Service period validation
        if self.leistungszeitraum_von and self.leistungszeitraum_bis:
            if self.leistungszeitraum_von > self.leistungszeitraum_bis:
                errors['leistungszeitraum_bis'] = 'Leistungszeitraum bis muss nach dem Von-Datum liegen.'
        
        # Payment date validation
        if self.status == 'BEZAHLT' and not self.zahlungsdatum:
            errors['zahlungsdatum'] = 'Bei Status "Bezahlt" muss ein Zahlungsdatum angegeben werden.'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def mark_as_paid(self, payment_date=None):
        """Mark invoice as paid with the given payment date"""
        from django.utils import timezone
        self.status = 'BEZAHLT'
        self.zahlungsdatum = payment_date or timezone.now().date()
        self.save()


class EingangsrechnungAufteilung(models.Model):
    """Cost allocation for an incoming invoice
    
    Splits invoice amounts by cost types with automatic VAT calculation
    """
    
    eingangsrechnung = models.ForeignKey(
        Eingangsrechnung,
        on_delete=models.CASCADE,
        related_name='aufteilungen',
        verbose_name="Eingangsrechnung"
    )
    
    # Cost types (hierarchical)
    kostenart1 = models.ForeignKey(
        'core.Kostenart',
        on_delete=models.PROTECT,
        related_name='aufteilungen_hauptkostenart',
        limit_choices_to={'parent__isnull': True},
        verbose_name="Kostenart 1 (Hauptkostenart)"
    )
    kostenart2 = models.ForeignKey(
        'core.Kostenart',
        on_delete=models.PROTECT,
        related_name='aufteilungen_unterkostenart',
        blank=True,
        null=True,
        verbose_name="Kostenart 2 (Unterkostenart)"
    )
    
    # Amount
    nettobetrag = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Nettobetrag"
    )
    
    # Optional description
    beschreibung = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Beschreibung"
    )
    
    class Meta:
        verbose_name = "Eingangsrechnungsaufteilung"
        verbose_name_plural = "Eingangsrechnungsaufteilungen"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.eingangsrechnung.belegnummer} - {self.kostenart1.name} - {self.nettobetrag}"
    
    @property
    def umsatzsteuer_satz(self):
        """Get VAT rate from cost type (prefer kostenart2 if set, otherwise kostenart1)"""
        kostenart = self.kostenart2 if self.kostenart2 else self.kostenart1
        return Decimal(kostenart.umsatzsteuer_satz)
    
    @property
    def umsatzsteuer(self):
        """Calculate VAT amount"""
        if not self.nettobetrag:
            return Decimal('0')
        return (self.nettobetrag * self.umsatzsteuer_satz / Decimal('100')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP
        )
    
    @property
    def bruttobetrag(self):
        """Calculate gross amount (net + VAT)"""
        if not self.nettobetrag:
            return Decimal('0')
        return self.nettobetrag + self.umsatzsteuer
    
    def clean(self):
        """Validate the allocation"""
        super().clean()
        errors = {}
        
        # Validate net amount is non-negative
        if self.nettobetrag is not None and self.nettobetrag < 0:
            errors['nettobetrag'] = 'Nettobetrag muss größer oder gleich 0 sein.'
        
        # Validate kostenart2 belongs to kostenart1
        if self.kostenart2 and self.kostenart2.parent != self.kostenart1:
            errors['kostenart2'] = f'Kostenart 2 "{self.kostenart2.name}" muss zur Hauptkostenart "{self.kostenart1.name}" gehören.'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.full_clean()
        super().save(*args, **kwargs)

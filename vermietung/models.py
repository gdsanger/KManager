
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction
from core.models import Adresse

OBJEKT_TYPE = [
       ('GEBAEUDE','Gebäude'),
        ('RAUM','Raum'),
        ('CONTAINER','Container'),
        ('STELLPLATZ','Stellplatz'),
        ('KFZ','KFZ'),
        ('SONSTIGES','Sonstiges'),
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
    
    class Meta:
        verbose_name = "Vertrag"
        verbose_name_plural = "Verträge"
        ordering = ['-start']
    
    def __str__(self):
        return f"{self.vertragsnummer} - {self.mietobjekt.name} ({self.mieter.full_name()})"
    
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
        Check if this contract overlaps with any existing contracts for the same MietObjekt.
        A contract overlaps if:
        - Contract A starts before Contract B ends AND Contract A ends after Contract B starts
        - Special case: if a contract has no end date (NULL), it blocks all future starts
        """
        # Get all other contracts for the same MietObjekt
        existing_contracts = Vertrag.objects.filter(
            mietobjekt=self.mietobjekt
        ).exclude(pk=self.pk if self.pk else None)
        
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
        """
        if not self.vertragsnummer:
            self.vertragsnummer = self._generate_vertragsnummer()
        
        # Run full_clean to trigger validation
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    def _generate_vertragsnummer(self):
        """
        Generate next contract number in format V-00000.
        Uses SELECT FOR UPDATE to prevent race conditions.
        """
        with transaction.atomic():
            # Get the last contract number using database locking
            last_contract = Vertrag.objects.select_for_update().order_by('-vertragsnummer').first()
            
            if last_contract and last_contract.vertragsnummer:
                # Extract number from V-00000 format
                last_number = int(last_contract.vertragsnummer.split('-')[1])
                next_number = last_number + 1
            else:
                next_number = 1
            
            # Format as V-00000
            return f"V-{next_number:05d}"
    

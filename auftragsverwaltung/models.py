from django.db import models
from django.core.exceptions import ValidationError


class DocumentType(models.Model):
    """
    Document Types (Dokumenttypen) - data-driven entity
    
    Document types must not be hardcoded (no Enum) but managed as configurable
    data-driven entities. The document type contains flags to control business
    behavior (e.g., invoice, correction).
    
    Scope: Global (not tenant-specific, no company FK)
    """
    key = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Key",
        help_text="Eindeutiger maschinenlesbarer Schlüssel (z.B. 'rechnung', 'angebot')"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Menschenlesbare Bezeichnung des Dokumenttyps"
    )
    prefix = models.CharField(
        max_length=10,
        verbose_name="Präfix",
        help_text="Präfix für Nummerierung (z.B. 'R', 'A', 'AB')"
    )
    
    # Flags
    is_invoice = models.BooleanField(
        default=False,
        verbose_name="Ist Rechnung",
        help_text="Kennzeichnet, ob dieser Dokumenttyp eine Rechnung ist"
    )
    is_correction = models.BooleanField(
        default=False,
        verbose_name="Ist Korrektur",
        help_text="Kennzeichnet, ob dieser Dokumenttyp eine Korrektur ist"
    )
    requires_due_date = models.BooleanField(
        default=False,
        verbose_name="Fälligkeitsdatum erforderlich",
        help_text="Kennzeichnet, ob ein Fälligkeitsdatum erforderlich ist"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob dieser Dokumenttyp aktiv ist"
    )
    
    class Meta:
        verbose_name = "Dokumenttyp"
        verbose_name_plural = "Dokumenttypen"
        ordering = ['key']
        indexes = [
            # Note: 'key' field already has an index due to unique=True
            models.Index(fields=['is_active'], name='doctype_is_active_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower('key'),
                name='documenttype_key_unique_case_insensitive',
                violation_error_message='Ein Dokumenttyp mit diesem Key existiert bereits (Groß-/Kleinschreibung wird ignoriert).'
            )
        ]
    
    def __str__(self):
        return f"{self.key}: {self.name} ({self.prefix})"
    
    def clean(self):
        """Validate document type data
        
        Note: While Django's CharField enforces non-null values by default,
        we explicitly check for whitespace-only values which would otherwise
        pass Django's default validation.
        """
        super().clean()
        
        # Validate key: must not be empty or whitespace-only
        if self.key and not self.key.strip():
            raise ValidationError({
                'key': 'Der Key darf nicht nur aus Leerzeichen bestehen.'
            })
        
        # Validate name: must not be empty or whitespace-only
        if self.name and not self.name.strip():
            raise ValidationError({
                'name': 'Der Name darf nicht nur aus Leerzeichen bestehen.'
            })
        
        # Validate prefix: must not be empty or whitespace-only
        if self.prefix and not self.prefix.strip():
            raise ValidationError({
                'prefix': 'Das Präfix darf nicht nur aus Leerzeichen bestehen.'
            })


class NumberRange(models.Model):
    """
    Number Range (Nummernkreis) - race-safe, tenant-specific number assignment
    
    Provides atomic number generation for documents with yearly reset policy.
    Each company+document_type combination has exactly one NumberRange.
    
    Examples:
    - R26-00001 (Invoice from 2026)
    - A26-00001 (Quote from 2026)
    """
    RESET_POLICY_CHOICES = [
        ('YEARLY', 'Yearly Reset'),
        ('NEVER', 'Never Reset'),
    ]
    
    company = models.ForeignKey(
        'core.Mandant',
        on_delete=models.PROTECT,
        related_name='number_ranges',
        verbose_name="Mandant"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='number_ranges',
        verbose_name="Dokumenttyp"
    )
    format = models.CharField(
        max_length=100,
        default='{prefix}{yy}-{seq:05d}',
        verbose_name="Format",
        help_text="Format string with tokens: {prefix}, {yy}, {seq:05d}"
    )
    reset_policy = models.CharField(
        max_length=10,
        choices=RESET_POLICY_CHOICES,
        default='YEARLY',
        verbose_name="Reset-Policy",
        help_text="YEARLY: Reset sequence on year change, NEVER: Continuous sequence"
    )
    current_year = models.IntegerField(
        default=0,
        verbose_name="Aktuelles Jahr (YY)",
        help_text="Zweistellige Jahreszahl der zuletzt vergebenen Nummer"
    )
    current_seq = models.IntegerField(
        default=0,
        verbose_name="Aktuelle Sequenz",
        help_text="Zuletzt vergebene Sequenznummer"
    )
    
    class Meta:
        verbose_name = "Nummernkreis"
        verbose_name_plural = "Nummernkreise"
        ordering = ['company', 'document_type']
        indexes = [
            models.Index(fields=['company', 'document_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'document_type'],
                name='unique_numberrange_per_company_doctype',
                violation_error_message='Es kann nur einen Nummernkreis pro Mandant und Dokumenttyp geben.'
            )
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.document_type.name} ({self.reset_policy})"


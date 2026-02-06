from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


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


class SalesDocument(models.Model):
    """
    Sales Document (Verkaufsbeleg) - central persistent document model
    
    Represents all sales-related documents (e.g., quotes, invoices, delivery notes)
    in a unified, extensible structure. Each document belongs to a company and has
    a specific document type that controls behavior via flags.
    
    Scope: Tenant-specific (company FK required)
    
    Out of Scope:
    - Workflow/Transitions/State-Machine
    - Calculation logic for total fields
    """
    
    # Status choices (MVP - code-based, lightweight)
    STATUS_CHOICES = [
        ('DRAFT', 'Entwurf'),
        ('SENT', 'Versendet'),
        ('ACCEPTED', 'Akzeptiert'),
        ('REJECTED', 'Abgelehnt'),
        ('CANCELLED', 'Storniert'),
        ('OPEN', 'Offen'),
        ('PAID', 'Bezahlt'),
        ('OVERDUE', 'Überfällig'),
    ]
    
    # Mandatory Foreign Keys (DB: NOT NULL)
    company = models.ForeignKey(
        'core.Mandant',
        on_delete=models.PROTECT,
        related_name='sales_documents',
        verbose_name="Mandant"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='sales_documents',
        verbose_name="Dokumenttyp"
    )
    
    # Central Fields
    number = models.CharField(
        max_length=32,
        db_index=True,
        verbose_name="Nummer",
        help_text="Dokumentnummer (z.B. R26-00001)"
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        db_index=True,
        verbose_name="Status"
    )
    issue_date = models.DateField(
        verbose_name="Belegdatum",
        help_text="Datum der Belegausstellung"
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fälligkeitsdatum",
        help_text="Fälligkeitsdatum (erforderlich bei Dokumenttypen mit requires_due_date=True)"
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Bezahlt am",
        help_text="Zeitpunkt der Zahlung"
    )
    
    # Relationships
    payment_term = models.ForeignKey(
        'core.PaymentTerm',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_documents',
        verbose_name="Zahlungsbedingung"
    )
    source_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_documents',
        verbose_name="Quelldokument",
        help_text="Referenz auf das ursprüngliche Dokument (erforderlich bei is_correction=True)"
    )
    
    # Snapshots
    payment_term_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Zahlungsbedingung-Snapshot",
        help_text="JSON-Snapshot der Zahlungsbedingung zum Zeitpunkt der Belegausstellung"
    )
    
    # Total Fields (denormalized; no calculation in this issue)
    total_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Nettobetrag",
        help_text="Gesamtbetrag netto"
    )
    total_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Steuerbetrag",
        help_text="Gesamtbetrag Steuer"
    )
    total_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Bruttobetrag",
        help_text="Gesamtbetrag brutto"
    )
    
    # Meta fields
    notes_internal = models.TextField(
        blank=True,
        default="",
        verbose_name="Interne Notizen",
        help_text="Interne Notizen (nicht für Kunden sichtbar)"
    )
    notes_public = models.TextField(
        blank=True,
        default="",
        verbose_name="Öffentliche Notizen",
        help_text="Öffentliche Notizen (auf Beleg sichtbar)"
    )
    
    class Meta:
        verbose_name = "Verkaufsbeleg"
        verbose_name_plural = "Verkaufsbelege"
        ordering = ['-issue_date', '-id']
        indexes = [
            models.Index(fields=['company', 'document_type']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['-issue_date']),
        ]
        constraints = [
            # Unique constraint: number is unique per (company, document_type)
            models.UniqueConstraint(
                fields=['company', 'document_type', 'number'],
                name='unique_salesdocument_number_per_company_doctype',
                violation_error_message='Diese Nummer existiert bereits für diesen Mandanten und Dokumenttyp.'
            )
        ]
    
    def __str__(self):
        return f"{self.number} ({self.company.name})"
    
    def clean(self):
        """Validate sales document data
        
        Business rules:
        1. If document_type.requires_due_date == True, then due_date is required
        2. If document_type.is_correction == True, then source_document is required
        """
        super().clean()
        
        # Validation 1: requires_due_date => due_date required
        if self.document_type and self.document_type.requires_due_date:
            if not self.due_date:
                raise ValidationError({
                    'due_date': 'Fälligkeitsdatum ist erforderlich für diesen Dokumenttyp.'
                })
        
        # Validation 2: is_correction => source_document required
        if self.document_type and self.document_type.is_correction:
            if not self.source_document:
                raise ValidationError({
                    'source_document': 'Quelldokument ist erforderlich für Korrekturdokumente.'
                })


class SalesDocumentSource(models.Model):
    """
    Sales Document Source (Dokumentherkunft) - tracks origin and references
    
    Stores the structured origin of sales documents (e.g., "copied from",
    "derived from", "correction of") to enable reporting and audit trails.
    
    Business Rules:
    - Company consistency: target_document.company_id == source_document.company_id
    - Multiple sources per document allowed
    - No self-references allowed
    - Unique per (target_document, source_document, role)
    """
    
    # Role choices
    ROLE_CHOICES = [
        ('COPIED_FROM', 'Kopiert von'),
        ('DERIVED_FROM', 'Abgeleitet von'),
        ('CORRECTION_OF', 'Korrektur von'),
    ]
    
    # Foreign Keys
    target_document = models.ForeignKey(
        SalesDocument,
        on_delete=models.PROTECT,
        related_name='sources_as_target',
        verbose_name="Zieldokument",
        help_text="Das Dokument, für das die Herkunft gespeichert wird"
    )
    source_document = models.ForeignKey(
        SalesDocument,
        on_delete=models.PROTECT,
        related_name='sources_as_source',
        verbose_name="Quelldokument",
        help_text="Das Ursprungsdokument"
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name="Rolle",
        help_text="Art der Beziehung zwischen Ziel- und Quelldokument"
    )
    
    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    
    class Meta:
        verbose_name = "Dokumentherkunft"
        verbose_name_plural = "Dokumentherkünfte"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_document']),
            models.Index(fields=['source_document']),
            models.Index(fields=['target_document', 'role']),
        ]
        constraints = [
            # Unique constraint: (target, source, role) triple
            models.UniqueConstraint(
                fields=['target_document', 'source_document', 'role'],
                name='unique_document_source_per_target_source_role',
                violation_error_message='Diese Dokumentherkunft existiert bereits.'
            ),
            # Check constraint: prevent self-reference
            models.CheckConstraint(
                check=~models.Q(target_document=models.F('source_document')),
                name='prevent_self_reference_document_source',
                violation_error_message='Ein Dokument kann nicht auf sich selbst verweisen.'
            ),
        ]
    
    def __str__(self):
        return f"{self.target_document.number} ← {self.get_role_display()} ← {self.source_document.number}"
    
    def clean(self):
        """Validate sales document source data
        
        Business rules:
        1. Company consistency: target and source must belong to same company
        2. No self-references allowed
        """
        super().clean()
        
        # Validation 1: Company consistency
        if self.target_document and self.source_document:
            if self.target_document.company_id != self.source_document.company_id:
                raise ValidationError({
                    'source_document': 'Ziel- und Quelldokument müssen zum selben Mandanten gehören.'
                })
        
        # Validation 2: No self-references
        if self.target_document and self.source_document:
            if self.target_document_id == self.source_document_id:
                raise ValidationError({
                    'source_document': 'Ein Dokument kann nicht auf sich selbst verweisen.'
                })


class SalesDocumentLine(models.Model):
    """
    Sales Document Line (Dokumentposition) - flexible line item model
    
    Supports three line types:
    - NORMAL: always included in totals (regardless of is_selected)
    - OPTIONAL: included in totals only if is_selected=True
    - ALTERNATIVE: included in totals only if is_selected=True
    
    Snapshot stability: unit_price_net and tax_rate are persisted snapshots
    and must not automatically change when Item or TaxRate are modified.
    """
    
    # Line type choices
    LINE_TYPE_CHOICES = [
        ('NORMAL', 'Normal'),
        ('OPTIONAL', 'Optional'),
        ('ALTERNATIVE', 'Alternative'),
    ]
    
    # Foreign Keys
    document = models.ForeignKey(
        SalesDocument,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name="Dokument"
    )
    item = models.ForeignKey(
        'core.Item',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_document_lines',
        verbose_name="Artikel/Leistung"
    )
    tax_rate = models.ForeignKey(
        'core.TaxRate',
        on_delete=models.PROTECT,
        related_name='sales_document_lines',
        verbose_name="Steuersatz"
    )
    
    # Position fields
    position_no = models.IntegerField(
        verbose_name="Positionsnummer",
        help_text="Eindeutige Positionsnummer innerhalb des Dokuments"
    )
    line_type = models.CharField(
        max_length=20,
        choices=LINE_TYPE_CHOICES,
        verbose_name="Positionstyp"
    )
    is_selected = models.BooleanField(
        verbose_name="Ausgewählt",
        help_text="Gibt an, ob diese Position ausgewählt ist (relevant für OPTIONAL/ALTERNATIVE)"
    )
    
    # Content fields
    description = models.TextField(
        verbose_name="Beschreibung",
        help_text="Positionsbeschreibung"
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="Menge"
    )
    
    # Snapshot fields
    unit_price_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Netto-Stückpreis (Snapshot)",
        help_text="Snapshot des Netto-Stückpreises zum Zeitpunkt der Positionsanlage"
    )
    
    # Flags
    is_discountable = models.BooleanField(
        default=True,
        verbose_name="Rabattfähig",
        help_text="Gibt an, ob diese Position rabattfähig ist"
    )
    
    # Sum fields (denormalized; calculated by service, not in save())
    line_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Nettobetrag",
        help_text="Zeilenbetrag netto"
    )
    line_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Steuerbetrag",
        help_text="Zeilenbetrag Steuer"
    )
    line_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Bruttobetrag",
        help_text="Zeilenbetrag brutto"
    )
    
    class Meta:
        verbose_name = "Dokumentposition"
        verbose_name_plural = "Dokumentpositionen"
        ordering = ['document', 'position_no']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['document', 'position_no']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'position_no'],
                name='unique_position_no_per_document',
                violation_error_message='Diese Positionsnummer existiert bereits für dieses Dokument.'
            )
        ]
    
    def __str__(self):
        return f"{self.document.number} - Pos. {self.position_no}: {self.description[:50]}"
    
    def clean(self):
        """Validate sales document line data
        
        Business rules:
        1. Default is_selected based on line_type if not explicitly set
        2. For NORMAL lines, is_selected should be True (auto-corrected)
        """
        super().clean()
        
        # Set default is_selected based on line_type during creation
        # Note: This runs during validation, so we check if pk is None to detect creation
        if self.pk is None:
            if self.line_type == 'NORMAL':
                self.is_selected = True
            elif self.line_type in ('OPTIONAL', 'ALTERNATIVE'):
                # Only set default if is_selected was not explicitly set
                # Since BooleanField has no None state in Django by default,
                # we assume False as the default for OPTIONAL/ALTERNATIVE
                if not hasattr(self, '_is_selected_set'):
                    self.is_selected = False
        
        # Auto-correct is_selected for NORMAL lines
        # NORMAL lines should always be considered selected for totals calculation
        # (even if the field value is False, the business logic ignores it)
        if self.line_type == 'NORMAL':
            self.is_selected = True
    
    def is_included_in_totals(self):
        """
        Check if this line should be included in totals calculation
        
        Business logic:
        - NORMAL: always included (regardless of is_selected)
        - OPTIONAL: included only if is_selected=True
        - ALTERNATIVE: included only if is_selected=True
        
        Returns:
            bool: True if line should be included in totals
        """
        if self.line_type == 'NORMAL':
            return True
        # OPTIONAL and ALTERNATIVE
        return self.is_selected


from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

ANREDEN = [
    ('HERR', 'Herr'),
    ('FRAU', 'Frau'),
    ('DIVERS', 'Divers'),
]
ADRESSEN_TYPES = [
    ('Adresse', 'Adresse'),
    ('KUNDE', 'Kunde'),
    ('LIEFERANT', 'Lieferant'),
    ('STANDORT', 'Standort'),
    ('SONSTIGES', 'Sonstiges'),
]
KONTAKT_TYPES = [
    ('TELEFON', 'Telefon'),
    ('MOBIL', 'Mobil'),
    ('TELEFAX', 'Telefax'),
    ('EMAIL', 'E-Mail'),
]

# Create your models here.
class Adresse(models.Model):
    adressen_type = models.CharField(max_length=20, choices=ADRESSEN_TYPES, default='Adresse')
    firma = models.CharField(max_length=100, blank=True, null=True)
    anrede = models.CharField(max_length=10, choices=ANREDEN, blank=True, null=True)
    name = models.CharField(max_length=100)
    strasse = models.CharField(max_length=200)
    plz = models.CharField(max_length=10)
    ort = models.CharField(max_length=100)
    land = models.CharField(max_length=100)
    telefon = models.CharField(max_length=50, blank=True, null=True)
    mobil = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    bemerkung = models.TextField(blank=True, null=True)
    
    # Tax and accounting fields
    vat_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="USt-IdNr.",
        help_text="Umsatzsteuer-Identifikationsnummer (optional)"
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        default='DE',
        verbose_name="Ländercode",
        help_text="ISO 3166-1 Alpha-2 Ländercode (z.B. DE, AT, FR)"
    )
    is_eu = models.BooleanField(
        default=False,
        verbose_name="EU",
        help_text="Ist dies ein EU-Kunde?"
    )
    is_business = models.BooleanField(
        default=True,
        verbose_name="Unternehmer",
        help_text="Ist dies ein Unternehmer/Geschäftskunde?"
    )
    debitor_number = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Debitorennummer",
        help_text="Debitorennummer für die Buchhaltung (optional)"
    )
    
    def full_name(self):
        if self.firma:
            return f"{self.firma} - ({self.name})"
        return self.name

    def __str__(self):
        return f"{self.full_name()}, {self.strasse}, {self.plz} {self.ort}, {self.land}"
    
    def clean(self):
        """Validate and normalize address data"""
        super().clean()
        
        # Normalize and validate country_code
        if self.country_code:
            self.country_code = self.country_code.strip().upper()
            if len(self.country_code) != 2:
                raise ValidationError({
                    'country_code': 'Ländercode muss genau 2 Zeichen lang sein (z.B. DE, AT, FR).'
                })
        
        # Normalize vat_id
        if self.vat_id:
            self.vat_id = self.vat_id.strip().upper()
    
    def save(self, *args, **kwargs):
        """Override save to normalize fields before saving"""
        # Normalize country_code
        if self.country_code:
            self.country_code = self.country_code.strip().upper()
        
        # Normalize vat_id
        if self.vat_id:
            self.vat_id = self.vat_id.strip().upper()
        
        super().save(*args, **kwargs)


class AdresseKontakt(models.Model):
    """Contact information for an address (multiple contacts per address)"""
    adresse = models.ForeignKey(
        Adresse,
        on_delete=models.CASCADE,
        related_name='kontakte',
        verbose_name="Adresse"
    )
    type = models.CharField(
        max_length=20,
        choices=KONTAKT_TYPES,
        verbose_name="Kontakttyp"
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Name"
    )
    position = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Position"
    )
    kontakt = models.CharField(
        max_length=200,
        verbose_name="Kontakt"
    )
    
    class Meta:
        verbose_name = "Adresse Kontakt"
        verbose_name_plural = "Adresse Kontakte"
        ordering = ['type', 'name']
        indexes = [
            models.Index(fields=['adresse']),
            models.Index(fields=['adresse', 'type']),
        ]
    
    def __str__(self):
        if self.name:
            return f"{self.get_type_display()}: {self.name} ({self.kontakt})"
        return f"{self.get_type_display()}: {self.kontakt}"
    
    def clean(self):
        """Validate email format for EMAIL type"""
        super().clean()
        if self.type == 'EMAIL' and self.kontakt:
            # Use Django's EmailValidator
            from django.core.validators import validate_email
            try:
                validate_email(self.kontakt)
            except ValidationError:
                raise ValidationError({
                    'kontakt': 'Bitte geben Sie eine gültige E-Mail-Adresse ein.'
                })


class SmtpSettings(models.Model):
    """Singleton model for global SMTP configuration"""
    host = models.CharField(max_length=255, verbose_name="SMTP Host")
    port = models.IntegerField(default=587, verbose_name="SMTP Port")
    use_tls = models.BooleanField(default=False, verbose_name="Use STARTTLS")
    username = models.CharField(max_length=255, blank=True, verbose_name="Username")
    password = models.CharField(max_length=255, blank=True, verbose_name="Password")

    class Meta:
        verbose_name = "SMTP Einstellungen"
        verbose_name_plural = "SMTP Einstellungen"

    def save(self, *args, **kwargs):
        """Enforce singleton - only one instance allowed"""
        if not self.pk and SmtpSettings.objects.exists():
            raise ValidationError("Es kann nur eine SMTP-Konfiguration existieren.")
        return super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get the singleton instance, create default if doesn't exist"""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'host': 'localhost',
                'port': 587,
                'use_tls': False,
                'username': '',
                'password': ''
            }
        )
        return obj

    def __str__(self):
        return f"SMTP: {self.host}:{self.port}"


class MailTemplate(models.Model):
    """Template for sending emails"""
    key = models.SlugField(max_length=100, unique=True, verbose_name="Template Key", help_text="Technischer Identifier (z.B. issue-created-confirmation)")
    subject = models.CharField(max_length=255, verbose_name="Betreff", help_text="Betreff der E-Mail, Platzhalter erlaubt")
    message = models.TextField(verbose_name="Nachricht", help_text="Inhalt der E-Mail (Markdown oder HTML, Platzhalter erlaubt)")
    from_name = models.CharField(max_length=255, blank=True, verbose_name="Absendername")
    from_address = models.EmailField(blank=True, verbose_name="Absenderadresse")
    cc_address = models.EmailField(blank=True, verbose_name="CC-Adresse")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv", help_text="Template aktiv / deaktiviert")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        verbose_name = "E-Mail Template"
        verbose_name_plural = "E-Mail Templates"
        ordering = ['key']

    def __str__(self):
        return f"{self.key}: {self.subject}"


class Mandant(models.Model):
    """Entity representing a client/tenant (Mandant) with contact and legal information"""
    # Basisdaten
    name = models.CharField(max_length=200, verbose_name="Name")
    adresse = models.CharField(max_length=200, verbose_name="Adresse")
    plz = models.CharField(max_length=10, verbose_name="PLZ")
    ort = models.CharField(max_length=100, verbose_name="Ort")
    land = models.CharField(max_length=100, verbose_name="Land", default="Deutschland")
    
    # Kontakt
    telefon = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    fax = models.CharField(max_length=50, blank=True, verbose_name="Fax")
    email = models.EmailField(blank=True, verbose_name="E-Mail")
    internet = models.URLField(blank=True, verbose_name="Internet")
    
    # Rechtliches
    steuernummer = models.CharField(max_length=50, blank=True, verbose_name="Steuernummer")
    ust_id_nr = models.CharField(max_length=50, blank=True, verbose_name="UStIdNr")
    geschaeftsfuehrer = models.CharField(max_length=200, blank=True, verbose_name="Geschäftsführer")
    kreditinstitut = models.CharField(max_length=200, blank=True, verbose_name="Kreditinstitut")
    iban = models.CharField(max_length=34, blank=True, verbose_name="IBAN")
    bic = models.CharField(max_length=11, blank=True, verbose_name="BIC")
    kontoinhaber = models.CharField(max_length=200, blank=True, verbose_name="Kontoinhaber")

    class Meta:
        verbose_name = "Mandant"
        verbose_name_plural = "Mandanten"
        ordering = ['name']

    def __str__(self):
        return f"{self.name}, {self.plz} {self.ort}"


class PaymentTerm(models.Model):
    """Payment Terms (Zahlungsbedingungen) for invoices
    
    Central management of payment terms including discount (Skonto) and net payment terms.
    Each company can have multiple payment terms with one default.
    """
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Bezeichnung der Zahlungsbedingung (z.B. '2% Skonto 10 Tage, netto 30 Tage')"
    )
    discount_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Skontofrist (Tage)",
        help_text="Anzahl Tage für Skontoabzug (optional)"
    )
    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Skontosatz",
        help_text="Skontosatz als Dezimalzahl (z.B. 0.02 für 2%)"
    )
    net_days = models.IntegerField(
        verbose_name="Zahlungsziel (Tage)",
        help_text="Anzahl Tage bis zur Fälligkeit (Netto)"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Standard",
        help_text="Ist dies die Standard-Zahlungsbedingung für diesen Mandanten?"
    )
    
    class Meta:
        verbose_name = "Zahlungsbedingung"
        verbose_name_plural = "Zahlungsbedingungen"
        ordering = ['name']
        indexes = [
        
            models.Index(fields=['is_default']),
        ]
        constraints = [
            # Ensure only one default
            models.UniqueConstraint(
                fields=['is_default'],               
                condition=models.Q(is_default=True),
                name='unique_default_payment_term',
                violation_error_message='Es kann nur eine Standard-Zahlungsbedingung existieren.'
            )
        ]
    
    def __str__(self):
        if self.discount_days and self.discount_rate:
            discount_pct = (self.discount_rate * Decimal('100')).quantize(Decimal('0.01'))
            return f"{self.name} ({discount_pct}% {self.discount_days}T, netto {self.net_days}T)"
        return f"{self.name} (netto {self.net_days}T)"
    
    def clean(self):
        """Validate payment term data"""
        super().clean()
        
        # Validation 1: discount_days must be <= net_days
        if self.discount_days is not None and self.discount_days > self.net_days:
            raise ValidationError({
                'discount_days': 'Die Skontofrist darf nicht größer sein als das Zahlungsziel.'
            })
        
        # Validation 2: If discount_days is set, discount_rate must be set and > 0
        if self.discount_days is not None:
            if self.discount_rate is None:
                raise ValidationError({
                    'discount_rate': 'Wenn eine Skontofrist angegeben ist, muss auch ein Skontosatz angegeben werden.'
                })
            if self.discount_rate <= 0:
                raise ValidationError({
                    'discount_rate': 'Der Skontosatz muss größer als 0 sein.'
                })
        
        # Validation 3: If discount_rate is set, discount_days must be set
        if self.discount_rate is not None and self.discount_days is None:
            raise ValidationError({
                'discount_days': 'Wenn ein Skontosatz angegeben ist, muss auch eine Skontofrist angegeben werden.'
            })
    
    def save(self, *args, **kwargs):
        """Override save to handle default switching"""
        if self.is_default:
            # Deactivate any existing default for this company
            PaymentTerm.objects.filter(
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_default(cls):
        """Get the default payment term for a company
        
        Args:
            company: Mandant instance
            
        Returns:
            PaymentTerm instance or None if no default exists
        """
        try:
            return cls.objects.get(is_default=True)
        except cls.DoesNotExist:
            return None
    
    def calculate_due_date(self, invoice_date):
        """Calculate due date based on invoice date
        
        Args:
            invoice_date: datetime.date or datetime.datetime
            
        Returns:
            datetime.date - Due date
        """
        from datetime import timedelta
        if hasattr(invoice_date, 'date'):
            invoice_date = invoice_date.date()
        return invoice_date + timedelta(days=self.net_days)
    
    def calculate_discount_end_date(self, invoice_date):
        """Calculate discount end date based on invoice date
        
        Args:
            invoice_date: datetime.date or datetime.datetime
            
        Returns:
            datetime.date or None - Discount end date if discount is active, None otherwise
        """
        if self.discount_days is None:
            return None
        
        from datetime import timedelta
        if hasattr(invoice_date, 'date'):
            invoice_date = invoice_date.date()
        return invoice_date + timedelta(days=self.discount_days)
    
    def get_discount_rate(self):
        """Get discount rate
        
        Returns:
            Decimal or None - Discount rate if discount is active, None otherwise
        """
        return self.discount_rate
    
    def has_discount(self):
        """Check if this payment term has discount terms
        
        Returns:
            bool - True if discount is active
        """
        return self.discount_days is not None and self.discount_rate is not None


class TaxRate(models.Model):
    """Tax Rate entity (Steuersätze)
    
    Central management of tax rates. Tax rates can be referenced by other domain objects
    via ForeignKey. Tax rates must not be hardcoded (no Enum) but managed data-driven.
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Eindeutiger Code für den Steuersatz (z.B. VAT, REDUCED)"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Bezeichnung des Steuersatzes"
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        verbose_name="Steuersatz",
        help_text="Steuersatz als Dezimalzahl (z.B. 0.19 für 19%)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob dieser Steuersatz aktiv ist"
    )
    
    class Meta:
        verbose_name = "Steuersatz"
        verbose_name_plural = "Steuersätze"
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower('code'),
                name='taxrate_code_unique_case_insensitive',
                violation_error_message='Ein Steuersatz mit diesem Code existiert bereits (Groß-/Kleinschreibung wird ignoriert).'
            )
        ]
    
    def __str__(self):
        # Format rate as percentage with 2 decimal places using Decimal for precision
        percentage = (self.rate * Decimal('100')).quantize(Decimal('0.01'))
        return f"{self.code}: {self.name} ({percentage}%)"
    
    def clean(self):
        """Validate tax rate data"""
        super().clean()
        
        # Validate rate: must be between 0 and 1
        if self.rate is not None:
            if self.rate < 0:
                raise ValidationError({
                    'rate': 'Der Steuersatz darf nicht negativ sein.'
                })
            if self.rate > 1:
                raise ValidationError({
                    'rate': 'Der Steuersatz darf nicht größer als 1 sein.'
                })


class Kostenart(models.Model):
    """Kostenarten (Cost Types) with hierarchical structure
    
    Can be either:
    - Hauptkostenart (parent=None) - Main cost type
    - Unterkostenart (parent=Kostenart) - Sub cost type
    """
    UMSATZSTEUER_SAETZE = [
        ('0', '0% Umsatzsteuer (steuerfrei)'),
        ('7', '7% Umsatzsteuer (ermäßigt)'),
        ('19', '19% Umsatzsteuer (regulär)'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Name")
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Hauptkostenart"
    )
    umsatzsteuer_satz = models.CharField(
        max_length=2,
        choices=UMSATZSTEUER_SAETZE,
        default='19',
        verbose_name="Umsatzsteuer-Satz"
    )

    class Meta:
        verbose_name = "Kostenart"
        verbose_name_plural = "Kostenarten"
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def is_hauptkostenart(self):
        """Check if this is a main cost type (has no parent)"""
        return self.parent is None

    def clean(self):
        """Validate that cost type hierarchy is only one level deep"""
        super().clean()
        if self.parent and self.parent.parent:
            raise ValidationError({
                'parent': 'Kostenarten können nur eine Hierarchieebene haben. '
                         'Eine Unterkostenart kann nicht einer anderen Unterkostenart zugeordnet werden.'
            })


class AIProvider(models.Model):
    """AI Provider configuration (OpenAI, Gemini, Claude)"""
    PROVIDER_TYPES = [
        ('OpenAI', 'OpenAI'),
        ('Gemini', 'Gemini'),
        ('Claude', 'Claude'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Name")
    provider_type = models.CharField(
        max_length=20, 
        choices=PROVIDER_TYPES, 
        verbose_name="Provider Type"
    )
    api_key = models.CharField(
        max_length=500, 
        verbose_name="API Key",
        help_text="Encrypted API key for the provider"
    )
    organization_id = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name="Organization ID",
        help_text="Optional organization ID (e.g., for OpenAI)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = "AI Provider"
        verbose_name_plural = "AI Providers"
        ordering = ['provider_type', 'name']
    
    def __str__(self):
        return f"{self.provider_type}: {self.name}"


class AIModel(models.Model):
    """AI Model configuration with pricing"""
    provider = models.ForeignKey(
        AIProvider, 
        on_delete=models.CASCADE, 
        related_name='models',
        verbose_name="Provider"
    )
    name = models.CharField(max_length=100, verbose_name="Name")
    model_id = models.CharField(
        max_length=100, 
        verbose_name="Model ID",
        help_text="Provider-specific model identifier (e.g., gpt-4, gemini-pro)"
    )
    input_price_per_1m_tokens = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0,
        verbose_name="Input Price per 1M Tokens",
        help_text="Price in USD per 1 million input tokens"
    )
    output_price_per_1m_tokens = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=0,
        verbose_name="Output Price per 1M Tokens",
        help_text="Price in USD per 1 million output tokens"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    class Meta:
        verbose_name = "AI Model"
        verbose_name_plural = "AI Models"
        ordering = ['provider', 'name']
        unique_together = [['provider', 'model_id']]
    
    def __str__(self):
        return f"{self.provider.provider_type}: {self.name} ({self.model_id})"


class AIJobsHistory(models.Model):
    """History of AI API calls with usage tracking and cost calculation"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Error', 'Error'),
    ]
    
    agent = models.CharField(
        max_length=100, 
        verbose_name="Agent",
        help_text="Agent or service that initiated the call (e.g., 'core.ai', 'manual')"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ai_jobs',
        verbose_name="User"
    )
    provider = models.ForeignKey(
        AIProvider, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='jobs',
        verbose_name="Provider"
    )
    model = models.ForeignKey(
        AIModel, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='jobs',
        verbose_name="Model"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='Pending',
        verbose_name="Status"
    )
    client_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name="Client IP"
    )
    input_tokens = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Input Tokens"
    )
    output_tokens = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Output Tokens"
    )
    costs = models.DecimalField(
        max_digits=10, 
        decimal_places=6, 
        null=True, 
        blank=True,
        verbose_name="Costs (USD)",
        help_text="Calculated cost in USD"
    )
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Timestamp")
    duration_ms = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Duration (ms)",
        help_text="API call duration in milliseconds"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Error Message",
        help_text="Error details if status is Error"
    )
    
    class Meta:
        verbose_name = "AI Job History"
        verbose_name_plural = "AI Jobs History"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['status']),
            models.Index(fields=['provider']),
            models.Index(fields=['model']),
        ]
    
    def __str__(self):
        return f"{self.timestamp} - {self.agent} - {self.status}"


class ReportDocument(models.Model):
    """
    Stores generated PDF reports with context snapshot for audit trail.
    
    This model provides generic infrastructure for report generation and versioning.
    It stores:
    - The generated PDF file
    - A JSON snapshot of the context used to generate the report
    - Metadata about the report type and related object
    """
    report_key = models.CharField(
        max_length=100,
        verbose_name="Report Key",
        help_text="Report type identifier (e.g., 'change.v1', 'invoice.v1')"
    )
    object_type = models.CharField(
        max_length=100,
        verbose_name="Object Type",
        help_text="Type of the related object (e.g., 'change', 'invoice')"
    )
    object_id = models.CharField(
        max_length=100,
        verbose_name="Object ID",
        help_text="ID of the related object"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_reports',
        verbose_name="Created By"
    )
    context_json = models.JSONField(
        verbose_name="Context Snapshot",
        help_text="JSON snapshot of the data used to generate the report"
    )
    pdf_file = models.FileField(
        upload_to='reports/%Y/%m/%d/',
        verbose_name="PDF File"
    )
    template_version = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Template Version",
        help_text="Version or hash of the template used"
    )
    sha256 = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="SHA256 Hash",
        help_text="SHA256 hash of the PDF for integrity verification"
    )
    metadata = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Additional Metadata",
        help_text="Optional additional metadata"
    )
    
    class Meta:
        verbose_name = "Report Document"
        verbose_name_plural = "Report Documents"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_key', '-created_at']),
            models.Index(fields=['object_type', 'object_id', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.report_key} - {self.object_type}:{self.object_id} ({self.created_at})"


class Item(models.Model):
    """
    Item entity (Artikel/Leistung) - stub for SalesDocumentLine FK reference
    
    This is a minimal stub implementation to support SalesDocumentLine.
    Full implementation will be done in a separate issue.
    """
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Bezeichnung des Artikels/der Leistung"
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Beschreibung",
        help_text="Detaillierte Beschreibung"
    )
    unit_price_net = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Netto-Stückpreis",
        help_text="Standardpreis netto"
    )
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name="Steuersatz"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob dieser Artikel aktiv ist"
    )
    
    class Meta:
        verbose_name = "Artikel/Leistung"
        verbose_name_plural = "Artikel/Leistungen"
        ordering = ['name']
    
    def __str__(self):
        return self.name
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone

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
    def full_name(self):
        if self.firma:
            return f"{self.firma} - ({self.name})"
        return self.name

    def __str__(self):
        return f"{self.full_name()}, {self.strasse}, {self.plz} {self.ort}, {self.land}"


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
        # Format rate as percentage with 2 decimal places
        percentage = float(self.rate) * 100
        return f"{self.code}: {self.name} ({percentage:.2f}%)"
    
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
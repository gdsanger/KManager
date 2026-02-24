import logging
import os
import uuid
from pathlib import Path

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

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
    handelsregister = models.CharField(max_length=200, blank=True, verbose_name="Handelsregister")
    kreditinstitut = models.CharField(max_length=200, blank=True, verbose_name="Kreditinstitut")
    iban = models.CharField(max_length=34, blank=True, verbose_name="IBAN")
    bic = models.CharField(max_length=11, blank=True, verbose_name="BIC")
    kontoinhaber = models.CharField(max_length=200, blank=True, verbose_name="Kontoinhaber")
    
    # Logo
    logo_path = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Logo Pfad",
        help_text="Relativer Pfad zum Logo im Media-Verzeichnis"
    )

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


class ItemGroup(models.Model):
    """Item Groups (Warengruppen) with flat 2-level hierarchy
    
    Global item groups for structured classification of items with exactly
    one flat hierarchy:
    - MAIN (Hauptwarengruppe) → SUB (Unterwarengruppe)
    
    Item groups are global (not company-specific) and serve for structuring,
    filtering, and reporting.
    """
    GROUP_TYPES = [
        ('MAIN', 'Hauptwarengruppe'),
        ('SUB', 'Unterwarengruppe'),
    ]
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Eindeutiger Code für die Warengruppe"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Bezeichnung der Warengruppe"
    )
    group_type = models.CharField(
        max_length=10,
        choices=GROUP_TYPES,
        verbose_name="Gruppentyp",
        help_text="Typ der Warengruppe (Haupt- oder Untergruppe)"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Hauptwarengruppe",
        help_text="Übergeordnete Hauptwarengruppe (nur bei Untergruppen)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob diese Warengruppe aktiv ist"
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Beschreibung",
        help_text="Optional: Beschreibung der Warengruppe"
    )
    
    class Meta:
        verbose_name = "Warengruppe"
        verbose_name_plural = "Warengruppen"
        ordering = ['code']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.code} > {self.code}: {self.name}"
        return f"{self.code}: {self.name}"
    
    def clean(self):
        """Validate item group hierarchy rules"""
        super().clean()
        
        # Rule 1: MAIN must not have a parent
        if self.group_type == 'MAIN' and self.parent is not None:
            raise ValidationError({
                'parent': 'Eine Hauptwarengruppe (MAIN) darf keine übergeordnete Gruppe haben.'
            })
        
        # Rule 2: SUB must have a parent
        if self.group_type == 'SUB' and self.parent is None:
            raise ValidationError({
                'parent': 'Eine Unterwarengruppe (SUB) muss eine übergeordnete Hauptwarengruppe haben.'
            })
        
        # Rule 3: SUB's parent must be MAIN (no deeper hierarchy)
        if self.group_type == 'SUB' and self.parent is not None:
            if self.parent.group_type != 'MAIN':
                raise ValidationError({
                    'parent': 'Eine Unterwarengruppe (SUB) kann nur einer Hauptwarengruppe (MAIN) zugeordnet werden. '
                             'Tiefere Hierarchieebenen sind nicht erlaubt.'
                })


class Item(models.Model):
    """
    Item entity (Artikel/Leistung) - Global Article Master Data
    
    Central master data source for articles/services to be reused in sales document lines.
    When an item is selected in a document line, relevant values are copied as a snapshot
    to the line, ensuring that existing documents remain historically stable.
    
    Out of Scope: Inventory management, price tiers, variants, price change history
    """
    
    # Item type choices
    ITEM_TYPE_CHOICES = [
        ('MATERIAL', 'Material'),
        ('SERVICE', 'Dienstleistung'),
    ]
    
    # Core identification
    article_no = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Artikelnummer",
        help_text="Eindeutige Artikelnummer (global)"
    )
    
    # Text fields
    short_text_1 = models.CharField(
        max_length=200,
        verbose_name="Kurztext 1",
        help_text="Primärer Kurztext"
    )
    short_text_2 = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Kurztext 2",
        help_text="Optionaler zweiter Kurztext"
    )
    long_text = models.TextField(
        blank=True,
        default="",
        verbose_name="Langtext",
        help_text="Detaillierte Beschreibung"
    )
    
    # Pricing
    net_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Verkaufspreis netto",
        help_text="Netto-Verkaufspreis"
    )
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Einkaufspreis netto",
        help_text="Netto-Einkaufspreis"
    )
    
    # Foreign Keys
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,
        related_name='items',
        verbose_name="Steuersatz"
    )
    cost_type_1 = models.ForeignKey(
        Kostenart,
        on_delete=models.PROTECT,
        related_name='items_cost_type_1',
        verbose_name="Kostenart 1"
    )
    cost_type_2 = models.ForeignKey(
        Kostenart,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='items_cost_type_2',
        verbose_name="Kostenart 2"
    )
    item_group = models.ForeignKey(
        ItemGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='items',
        verbose_name="Warengruppe",
        help_text="Optional: Zuordnung zu einer Unterwarengruppe (SUB)"
    )
    
    # Classification
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        verbose_name="Artikeltyp",
        help_text="Klassifizierung: Material oder Dienstleistung"
    )
    
    # Flags
    is_discountable = models.BooleanField(
        default=True,
        verbose_name="Rabattfähig",
        help_text="Gibt an, ob dieser Artikel rabattfähig ist"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob dieser Artikel aktiv ist"
    )
    
    class Meta:
        verbose_name = "Artikel/Leistung"
        verbose_name_plural = "Artikel/Leistungen"
        ordering = ['article_no']
        indexes = [
            models.Index(fields=['article_no']),
            models.Index(fields=['is_active']),
            models.Index(fields=['item_type']),
        ]
        constraints = [
            # Ensure article_no is globally unique
            models.UniqueConstraint(
                fields=['article_no'],
                name='item_article_no_unique',
                violation_error_message='Ein Artikel mit dieser Artikelnummer existiert bereits.'
            ),
            # Ensure net_price is non-negative
            models.CheckConstraint(
                check=models.Q(net_price__gte=0),
                name='item_net_price_non_negative',
                violation_error_message='Der Verkaufspreis darf nicht negativ sein.'
            ),
            # Ensure purchase_price is non-negative
            models.CheckConstraint(
                check=models.Q(purchase_price__gte=0),
                name='item_purchase_price_non_negative',
                violation_error_message='Der Einkaufspreis darf nicht negativ sein.'
            ),
        ]
    
    def __str__(self):
        return f"{self.article_no}: {self.short_text_1}"
    
    def clean(self):
        """Validate item data"""
        super().clean()
        
        # Validate net_price >= 0
        if self.net_price is not None and self.net_price < 0:
            raise ValidationError({
                'net_price': 'Der Verkaufspreis darf nicht negativ sein.'
            })
        
        # Validate purchase_price >= 0
        if self.purchase_price is not None and self.purchase_price < 0:
            raise ValidationError({
                'purchase_price': 'Der Einkaufspreis darf nicht negativ sein.'
            })
        
        # Validate item_group: if set, must be a SUB (has parent), not a MAIN (parent is NULL)
        if self.item_group is not None:
            if self.item_group.parent is None:
                raise ValidationError({
                    'item_group': 'Ein Artikel kann nur einer Unterwarengruppe (SUB) zugeordnet werden, '
                                  'nicht einer Hauptwarengruppe (MAIN). Bitte wählen Sie eine Unterwarengruppe.'
                })


# Activity Stream choices
ACTIVITY_DOMAIN_CHOICES = [
    ('RENTAL', 'Vermietung'),
    ('ORDER', 'Auftragsverwaltung'),
    ('FINANCE', 'Finanzen'),
]

ACTIVITY_SEVERITY_CHOICES = [
    ('INFO', 'Info'),
    ('WARNING', 'Warnung'),
    ('ERROR', 'Fehler'),
]


class Activity(models.Model):
    """
    Central Activity Stream for tracking events across all modules.
    
    Activities are explicitly created where business logic happens (save + action).
    Each activity contains a clickable link (target_url) to the affected object.
    
    Design constraints:
    - No Django Signals/Events/automatic hooks
    - No GenericFK/Object-Resolution; only target_url is persisted
    - Activities are written explicitly in business logic
    """
    company = models.ForeignKey(
        Mandant,
        on_delete=models.CASCADE,
        verbose_name="Mandant",
        help_text="Zugehöriger Mandant"
    )
    domain = models.CharField(
        max_length=20,
        choices=ACTIVITY_DOMAIN_CHOICES,
        verbose_name="Bereich",
        help_text="Fachlicher Bereich (Vermietung, Auftragsverwaltung, Finanzen)"
    )
    activity_type = models.CharField(
        max_length=64,
        verbose_name="Aktivitätstyp",
        help_text="Maschinenlesbarer Code, z.B. INVOICE_CREATED, CONTRACT_RUN_FAILED"
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Titel",
        help_text="Kurze Beschreibung der Aktivität"
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Beschreibung",
        help_text="Optionale detaillierte Beschreibung"
    )
    target_url = models.CharField(
        max_length=500,
        verbose_name="Ziel-URL",
        help_text="Klickbarer Link zum betroffenen Objekt (relativ), z.B. /auftragsverwaltung/documents/123"
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Akteur",
        help_text="Benutzer, der die Aktion ausgeführt hat"
    )
    severity = models.CharField(
        max_length=10,
        choices=ACTIVITY_SEVERITY_CHOICES,
        default='INFO',
        verbose_name="Schweregrad",
        help_text="Schweregrad der Aktivität"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
        help_text="Zeitpunkt der Erstellung"
    )
    
    class Meta:
        verbose_name = "Aktivität"
        verbose_name_plural = "Aktivitäten"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='activity_created_at_idx'),
            models.Index(fields=['company', '-created_at'], name='activity_company_created_idx'),
            models.Index(fields=['company', 'domain', '-created_at'], name='activity_company_domain_idx'),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.get_domain_display()}: {self.title}"


class Unit(models.Model):
    """Unit of Measurement (Einheiten)
    
    Central master data for units of measurement (e.g., Stück, Pauschal, lfm).
    Units can be referenced by articles and sales document lines.
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code",
        help_text="Eindeutiger Code für die Einheit (z.B. STK, PAU, LFM)"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Name",
        help_text="Bezeichnung der Einheit (z.B. Stück, Pauschal, Laufender Meter)"
    )
    symbol = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Symbol",
        help_text="Optionales Symbol für die Einheit (z.B. Stk, lfm)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Gibt an, ob diese Einheit aktiv ist"
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Beschreibung",
        help_text="Optionale Beschreibung der Einheit"
    )
    
    class Meta:
        verbose_name = "Einheit"
        verbose_name_plural = "Einheiten"
        ordering = ['code']
        constraints = [
            # Ensure code is globally unique
            models.UniqueConstraint(
                fields=['code'],
                name='unit_code_unique',
                violation_error_message='Eine Einheit mit diesem Code existiert bereits.'
            ),
        ]
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    def clean(self):
        """Validate and normalize unit data"""
        super().clean()
        
        # Normalize code to uppercase
        if self.code:
            self.code = self.code.strip().upper()
    
    def save(self, *args, **kwargs):
        """Override save to normalize code before saving"""
        # Normalize code to uppercase
        if self.code:
            self.code = self.code.strip().upper()
        
        super().save(*args, **kwargs)

# ---------------------------------------------------------------------------
# Projektverwaltung
# ---------------------------------------------------------------------------

PROJEKT_STATUS_CHOICES = [
    ('NEU', 'Neu'),
    ('IN_BEARBEITUNG', 'In Bearbeitung'),
    ('WARTET', 'Wartet'),
    ('ZURUECKGESTELLT', 'Zurückgestellt'),
    ('ABGESCHLOSSEN', 'Abgeschlossen'),
]

# Max file size for project files: 25 MB
PROJEKT_MAX_FILE_SIZE = 25 * 1024 * 1024


def validate_projekt_file_size(file):
    """Validate that file size does not exceed 25 MB."""
    if file.size > PROJEKT_MAX_FILE_SIZE:
        raise ValidationError(
            f'Die Dateigröße ({file.size / (1024 * 1024):.2f} MB) überschreitet '
            f'das Maximum von {PROJEKT_MAX_FILE_SIZE / (1024 * 1024):.0f} MB.'
        )


class Projekt(models.Model):
    """
    Projekt model for project management.
    Projects can have files and folders attached to them.
    """
    titel = models.CharField(
        max_length=255,
        verbose_name="Titel",
        help_text="Projektbezeichnung"
    )
    beschreibung = models.TextField(
        blank=True,
        default="",
        verbose_name="Beschreibung",
        help_text="Beschreibung des Projekts"
    )
    status = models.CharField(
        max_length=20,
        choices=PROJEKT_STATUS_CHOICES,
        default='NEU',
        verbose_name="Status",
        help_text="Aktueller Projektstatus"
    )
    erstellt_am = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am"
    )
    erstellt_von = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projekte',
        verbose_name="Erstellt von"
    )
    aktualisiert_am = models.DateTimeField(
        auto_now=True,
        verbose_name="Aktualisiert am"
    )

    class Meta:
        verbose_name = "Projekt"
        verbose_name_plural = "Projekte"
        ordering = ['-erstellt_am']

    def __str__(self):
        return self.titel

    def get_storage_root(self):
        """Return the absolute filesystem path for this project's files."""
        return Path(settings.PROJECT_DOCUMENTS_ROOT) / str(self.pk)


class ProjektFile(models.Model):
    """
    Represents either a folder or a file within a project.

    Folders have ``is_folder=True`` and no physical file stored.
    Files are stored in the filesystem under
    ``PROJECT_DOCUMENTS_ROOT / <projekt_id> / <ordner> / <filename>``.
    """
    projekt = models.ForeignKey(
        Projekt,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name="Projekt"
    )
    filename = models.CharField(
        max_length=255,
        verbose_name="Dateiname / Ordnername"
    )
    ordner = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Ordner",
        help_text="Pfad des übergeordneten Ordners (leer = Projektwurzel)"
    )
    is_folder = models.BooleanField(
        default=False,
        verbose_name="Ist Ordner"
    )
    # Storage path relative to PROJECT_DOCUMENTS_ROOT (empty for folders)
    storage_path = models.CharField(
        max_length=1000,
        blank=True,
        default="",
        verbose_name="Speicherpfad"
    )
    file_size = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Dateigröße",
        help_text="Dateigröße in Bytes"
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="MIME-Type"
    )
    datum = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Datum"
    )
    benutzer = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projekt_files',
        verbose_name="Benutzer"
    )

    class Meta:
        verbose_name = "Projektdatei"
        verbose_name_plural = "Projektdateien"
        ordering = ['-is_folder', 'ordner', 'filename']

    def __str__(self):
        if self.ordner:
            return f"{self.ordner}/{self.filename}"
        return self.filename

    def get_absolute_path(self):
        """Return the absolute filesystem path for this file."""
        if self.is_folder:
            folder_path = self.ordner + '/' + self.filename if self.ordner else self.filename
            return Path(settings.PROJECT_DOCUMENTS_ROOT) / str(self.projekt_id) / folder_path
        return Path(settings.PROJECT_DOCUMENTS_ROOT) / self.storage_path

    def delete(self, *args, **kwargs):
        """Override delete to remove physical file/folder from filesystem."""
        if self.is_folder:
            folder_abs = self.get_absolute_path()
            if folder_abs.exists() and folder_abs.is_dir():
                import shutil
                try:
                    shutil.rmtree(folder_abs)
                except OSError:
                    pass
        else:
            file_abs = self.get_absolute_path()
            if file_abs.exists():
                try:
                    file_abs.unlink()
                    # Clean up empty parent dirs (within project root only)
                    project_root = Path(settings.PROJECT_DOCUMENTS_ROOT) / str(self.projekt_id)
                    parent = file_abs.parent
                    while parent != project_root and parent.is_relative_to(project_root):
                        if not any(parent.iterdir()):
                            parent.rmdir()
                            parent = parent.parent
                        else:
                            break
                except OSError:
                    pass
        super().delete(*args, **kwargs)

    @staticmethod
    def save_uploaded_file(uploaded_file, projekt, ordner=""):
        """
        Save an uploaded file to the filesystem and return
        (storage_path, mime_type).

        The file is stored at:
            PROJECT_DOCUMENTS_ROOT / <projekt_id> / <ordner> / <uuid>_<filename>
        """
        validate_projekt_file_size(uploaded_file)

        # Detect MIME type (best-effort, no strict whitelist for projects)
        try:
            import magic as libmagic
            uploaded_file.seek(0)
            mime_type = libmagic.from_buffer(uploaded_file.read(2048), mime=True)
            uploaded_file.seek(0)
        except Exception:
            mime_type = "application/octet-stream"

        # Build a safe filename with UUID prefix to avoid collisions
        from werkzeug.utils import secure_filename
        safe_name = secure_filename(uploaded_file.name) or 'file'
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"

        # Base directory for this project's files
        base_dir = Path(settings.PROJECT_DOCUMENTS_ROOT) / str(projekt.pk)

        # Validate and normalize the optional subfolder ("ordner")
        if ordner:
            # Normalize the user-supplied folder path and ensure it is relative
            ordner_path = Path(ordner)
            if ordner_path.is_absolute() or ordner_path.drive:
                raise ValidationError("Ungültiger Ordnerpfad.")
            # Remove any leading separators to avoid empty/absolute segments
            cleaned_ordner = str(ordner_path).lstrip("/\\")
            # Construct the candidate folder path and resolve it
            folder_path = (base_dir / cleaned_ordner).resolve()
            try:
                # Ensure the resolved folder is still within the project base directory
                folder_path.relative_to(base_dir)
            except ValueError:
                raise ValidationError("Ungültiger Ordnerpfad.")
            target_dir = folder_path
        else:
            target_dir = base_dir

        # Ensure the target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Final absolute path for the file
        abs_path = target_dir / unique_name

        # Compute storage path relative to PROJECT_DOCUMENTS_ROOT (includes projekt_id prefix)
        rel_path = str(abs_path.relative_to(Path(settings.PROJECT_DOCUMENTS_ROOT)))

        try:
            with open(abs_path, 'wb') as dst:
                for chunk in uploaded_file.chunks():
                    dst.write(chunk)
        except OSError as exc:
            raise ValidationError(f'Fehler beim Speichern der Datei: {exc}')

        return rel_path, mime_type, unique_name

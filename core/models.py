from django.db import models
from django.core.exceptions import ValidationError

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
    key = models.CharField(max_length=100, unique=True, verbose_name="Template Key")
    subject = models.CharField(max_length=255, verbose_name="Betreff")
    message_html = models.TextField(verbose_name="HTML Nachricht")
    from_address = models.EmailField(verbose_name="Von E-Mail")
    from_name = models.CharField(max_length=255, verbose_name="Von Name")
    cc_copy_to = models.EmailField(blank=True, verbose_name="CC Kopie an")

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
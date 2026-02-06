from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class CompanyAccountingSettings(models.Model):
    """
    Accounting Settings per Company/Mandant (Buchhaltungs-Einstellungen pro Mandant)
    
    Purpose:
    - DATEV consultant and client numbers for export
    - Tax number for accounting
    - Revenue accounts (Erlöskonten) per tax rate (0%, 7%, 19%)
    
    Scope: OneToOne with core.Mandant (exactly one per company)
    
    Note: All fields are stored as strings to preserve leading zeros and DATEV formats
    """
    company = models.OneToOneField(
        'core.Mandant',
        on_delete=models.PROTECT,
        related_name='accounting_settings',
        verbose_name="Mandant",
        help_text="Mandant für diese Buchhaltungseinstellungen"
    )
    
    # DATEV Configuration
    datev_consultant_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="DATEV Beraternummer",
        help_text="DATEV Beraternummer (mit führenden Nullen)"
    )
    datev_client_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="DATEV Mandantennummer",
        help_text="DATEV Mandantennummer (mit führenden Nullen)"
    )
    tax_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Steuernummer",
        help_text="Steuernummer des Mandanten"
    )
    
    # Revenue Accounts per Tax Rate (Erlöskonten je Steuersatz)
    revenue_account_0 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 0%",
        help_text="Erlöskonto für Steuersatz 0% (mit führenden Nullen)"
    )
    revenue_account_7 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 7%",
        help_text="Erlöskonto für Steuersatz 7% (mit führenden Nullen)"
    )
    revenue_account_19 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 19%",
        help_text="Erlöskonto für Steuersatz 19% (mit führenden Nullen)"
    )
    
    class Meta:
        verbose_name = "Buchhaltungseinstellungen"
        verbose_name_plural = "Buchhaltungseinstellungen"
    
    def __str__(self):
        return f"Buchhaltungseinstellungen für {self.company.name}"


class OutgoingInvoiceJournalEntry(models.Model):
    """
    Outgoing Invoice Journal Entry (Rechnungsausgangsjournal)
    
    Purpose:
    - Immutable journal for finalized invoices and credit notes
    - Snapshot-based (no retroactive changes allowed)
    - DATEV-compatible structure
    - Basis for future DATEV export
    
    Scope: One entry per finalized document (invoice or credit note)
    
    Constraints:
    - Unique (company, document)
    - Optional unique (company, document_number)
    - Snapshot approach: all relevant data is copied at creation time
    
    Tax Logic:
    - Supports only 0%, 7%, 19% tax rates
    - Tax splitting must happen before journal entry creation
    - Other tax rates should be blocked or flagged as error (out of scope)
    
    Out of Scope (NOT part of this implementation):
    - Journal entry creation logic
    - DATEV export files (CSV/XML)
    - Payment reconciliation / open item management
    - Dunning (Mahnwesen)
    - Debtor master data logic
    """
    
    # Document Kind Choices
    DOCUMENT_KIND_CHOICES = [
        ('INVOICE', 'Rechnung'),
        ('CREDIT_NOTE', 'Gutschrift'),
    ]
    
    # Export Status Choices
    EXPORT_STATUS_CHOICES = [
        ('OPEN', 'Offen'),
        ('EXPORTED', 'Exportiert'),
        ('ERROR', 'Fehler'),
    ]
    
    # References (Referenzen)
    company = models.ForeignKey(
        'core.Mandant',
        on_delete=models.PROTECT,
        related_name='journal_entries',
        verbose_name="Mandant",
        help_text="Mandant für diesen Journal-Eintrag"
    )
    document = models.ForeignKey(
        'auftragsverwaltung.SalesDocument',
        on_delete=models.PROTECT,
        related_name='journal_entries',
        verbose_name="Dokument",
        help_text="Referenziertes Verkaufsdokument"
    )
    
    # Snapshot Fields (Snapshot-Felder)
    document_number = models.CharField(
        max_length=32,
        verbose_name="Belegnummer",
        help_text="Snapshot: Belegnummer zum Zeitpunkt der Journal-Erzeugung"
    )
    document_date = models.DateField(
        verbose_name="Belegdatum",
        help_text="Snapshot: Belegdatum"
    )
    document_kind = models.CharField(
        max_length=20,
        choices=DOCUMENT_KIND_CHOICES,
        verbose_name="Belegart",
        help_text="Rechnung oder Gutschrift"
    )
    customer_name = models.CharField(
        max_length=200,
        verbose_name="Kundenname",
        help_text="Snapshot: Kundenname"
    )
    debtor_number = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="Debitorennummer",
        help_text="Snapshot: Debitorennummer (optional)"
    )
    
    # Amounts per Tax Rate (Beträge je Steuersatz)
    # All amounts in Decimal with 2 decimal places
    net_0 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Netto 0%",
        help_text="Nettobetrag mit Steuersatz 0%"
    )
    net_7 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Netto 7%",
        help_text="Nettobetrag mit Steuersatz 7%"
    )
    net_19 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Netto 19%",
        help_text="Nettobetrag mit Steuersatz 19%"
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Steuerbetrag",
        help_text="Gesamter Steuerbetrag"
    )
    gross_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Bruttobetrag",
        help_text="Gesamtbetrag brutto"
    )
    
    # Revenue Account Snapshots (Erlöskonten-Snapshots)
    revenue_account_0 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 0%",
        help_text="Snapshot: Erlöskonto für Steuersatz 0%"
    )
    revenue_account_7 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 7%",
        help_text="Snapshot: Erlöskonto für Steuersatz 7%"
    )
    revenue_account_19 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Erlöskonto 19%",
        help_text="Snapshot: Erlöskonto für Steuersatz 19%"
    )
    
    # Export Tracking (Export-Vorbereitung)
    export_status = models.CharField(
        max_length=20,
        choices=EXPORT_STATUS_CHOICES,
        default='OPEN',
        verbose_name="Export-Status",
        help_text="Status des DATEV-Exports"
    )
    exported_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Exportiert am",
        help_text="Zeitpunkt des letzten erfolgreichen Exports"
    )
    export_batch_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Export-Batch-ID",
        help_text="ID der Export-Charge (optional)"
    )
    
    # Meta
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Erstellt am",
        help_text="Zeitpunkt der Journal-Eintrag-Erzeugung"
    )
    
    class Meta:
        verbose_name = "Rechnungsausgangsjournal-Eintrag"
        verbose_name_plural = "Rechnungsausgangsjournal-Einträge"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'document_date']),
            models.Index(fields=['company', 'export_status']),
            models.Index(fields=['document_number']),
        ]
        constraints = [
            # Exactly one journal entry per company+document
            models.UniqueConstraint(
                fields=['company', 'document'],
                name='unique_journal_entry_per_company_document',
                violation_error_message='Es kann nur einen Journal-Eintrag pro Mandant und Dokument geben.'
            ),
            # Optional: unique document number per company
            models.UniqueConstraint(
                fields=['company', 'document_number'],
                name='unique_document_number_per_company',
                violation_error_message='Die Belegnummer muss pro Mandant eindeutig sein.'
            ),
        ]
    
    def __str__(self):
        return f"{self.document_number} - {self.customer_name} ({self.gross_amount})"
    
    def clean(self):
        """Validate journal entry data"""
        super().clean()
        
        # Validate that gross_amount = sum of net amounts + tax
        calculated_net_total = self.net_0 + self.net_7 + self.net_19
        calculated_gross = calculated_net_total + self.tax_amount
        
        # Allow small rounding differences (up to 0.01)
        if abs(self.gross_amount - calculated_gross) > Decimal('0.01'):
            raise ValidationError({
                'gross_amount': f'Bruttobetrag ({self.gross_amount}) stimmt nicht mit berechneter Summe ({calculated_gross}) überein.'
            })

"""
Lieferantenwesen – Supplier management and incoming invoice models.

This module provides:
- Supplier: standalone supplier master data (no Vermietung coupling)
- InvoiceIn: incoming invoice with approval workflow
- InvoiceInLine: line items for incoming invoices
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


# ---------------------------------------------------------------------------
# Workflow status choices
# ---------------------------------------------------------------------------

INVOICE_IN_STATUS = [
    ('DRAFT', 'Entwurf'),
    ('EXTRACTED', 'Extrahiert'),
    ('IN_REVIEW', 'In Prüfung'),
    ('APPROVED', 'Freigegeben'),
    ('REJECTED', 'Abgelehnt'),
]


# ---------------------------------------------------------------------------
# Supplier model
# ---------------------------------------------------------------------------

class Supplier(models.Model):
    """Standalone supplier (Lieferant) master data."""

    name = models.CharField(max_length=200, verbose_name="Name")
    ust_id = models.CharField(
        max_length=50, blank=True, default="", verbose_name="USt-IdNr."
    )
    steuer_nr = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Steuernummer"
    )
    adresse_street = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Straße"
    )
    adresse_zip = models.CharField(
        max_length=20, blank=True, default="", verbose_name="PLZ"
    )
    adresse_city = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Ort"
    )
    adresse_country = models.CharField(
        max_length=100, blank=True, default="DE", verbose_name="Land"
    )
    email = models.EmailField(blank=True, default="", verbose_name="E-Mail")
    telefon = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Telefon"
    )
    bank_iban = models.CharField(
        max_length=34, blank=True, default="", verbose_name="IBAN"
    )
    bank_bic = models.CharField(
        max_length=11, blank=True, default="", verbose_name="BIC"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    # Audit
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Geändert am")

    class Meta:
        verbose_name = "Lieferant"
        verbose_name_plural = "Lieferanten"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# InvoiceIn model
# ---------------------------------------------------------------------------

class InvoiceIn(models.Model):
    """Incoming invoice (Eingangsrechnung) with approval workflow."""

    # --- Header data ---
    invoice_no = models.CharField(
        max_length=100, verbose_name="Rechnungsnummer"
    )
    invoice_date = models.DateField(verbose_name="Rechnungsdatum")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Lieferant",
    )
    currency = models.CharField(
        max_length=3, default="EUR", verbose_name="Währung"
    )

    # --- Amounts ---
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Nettobetrag",
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Umsatzsteuer",
    )
    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bruttobetrag",
    )
    tax_rate_summary = models.JSONField(
        null=True, blank=True, verbose_name="Steuersatz-Zusammenfassung"
    )

    # --- Payment data ---
    payment_terms_text = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Zahlungsbedingungen"
    )
    due_date = models.DateField(
        null=True, blank=True, verbose_name="Fälligkeit"
    )
    payment_reference = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Verwendungszweck"
    )
    iban_from_invoice = models.CharField(
        max_length=34, blank=True, default="", verbose_name="IBAN (aus Rechnung)"
    )

    # --- Cost assignment ---
    cost_type_main = models.ForeignKey(
        "core.Kostenart",
        on_delete=models.PROTECT,
        related_name="invoicein_main",
        null=True,
        blank=True,
        limit_choices_to={"parent__isnull": True},
        verbose_name="Hauptkostenart",
    )
    cost_type_sub = models.ForeignKey(
        "core.Kostenart",
        on_delete=models.PROTECT,
        related_name="invoicein_sub",
        null=True,
        blank=True,
        limit_choices_to={"parent__isnull": False},
        verbose_name="Unterkostenart",
    )
    order = models.ForeignKey(
        "auftragsverwaltung.SalesDocument",
        on_delete=models.SET_NULL,
        related_name="incoming_invoices",
        null=True,
        blank=True,
        verbose_name="Auftrag",
        help_text="Optionale Zuordnung zu einem Auftrag (Controlling / Rentabilität)",
    )

    # --- PDF file ---
    pdf_file = models.FileField(
        upload_to="lieferantenwesen/invoices/",
        null=True,
        blank=True,
        verbose_name="PDF-Datei",
    )

    # --- Workflow ---
    status = models.CharField(
        max_length=20,
        choices=INVOICE_IN_STATUS,
        default="DRAFT",
        verbose_name="Status",
    )
    approval_comment = models.TextField(
        blank=True, default="", verbose_name="Freigabe-Kommentar"
    )

    # --- Audit fields ---
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoicein_created",
        verbose_name="Erstellt von",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Geändert am")
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoicein_updated",
        verbose_name="Geändert von",
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Freigegeben am"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoicein_approved",
        verbose_name="Freigegeben von",
    )
    rejected_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Abgelehnt am"
    )
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoicein_rejected",
        verbose_name="Abgelehnt von",
    )

    class Meta:
        verbose_name = "Eingangsrechnung"
        verbose_name_plural = "Eingangsrechnungen"
        ordering = ["-invoice_date", "-created_at"]

    def __str__(self):
        return f"{self.invoice_no} – {self.supplier} – {self.invoice_date}"

    def clean(self):
        super().clean()
        errors = {}
        # Sub cost type must belong to the selected main cost type
        if self.cost_type_sub and self.cost_type_main:
            if self.cost_type_sub.parent_id != self.cost_type_main_id:
                errors["cost_type_sub"] = (
                    "Die Unterkostenart muss zur gewählten Hauptkostenart gehören."
                )
        if errors:
            raise ValidationError(errors)

    def get_status_display_class(self):
        """Return Bootstrap badge colour class for current status."""
        mapping = {
            "DRAFT": "secondary",
            "EXTRACTED": "info",
            "IN_REVIEW": "warning",
            "APPROVED": "success",
            "REJECTED": "danger",
        }
        return mapping.get(self.status, "secondary")


# ---------------------------------------------------------------------------
# InvoiceInLine model
# ---------------------------------------------------------------------------

class InvoiceInLine(models.Model):
    """Line item (position) for an incoming invoice."""

    invoice = models.ForeignKey(
        InvoiceIn,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Rechnung",
    )
    position_no = models.PositiveSmallIntegerField(
        default=1, verbose_name="Position"
    )
    description = models.CharField(
        max_length=500, verbose_name="Beschreibung"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Menge",
    )
    unit = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Einheit"
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Einzelpreis",
    )
    net_amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Nettobetrag"
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("19.00"),
        verbose_name="Steuersatz (%)",
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Umsatzsteuer",
    )
    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bruttobetrag",
    )

    class Meta:
        verbose_name = "Rechnungsposition"
        verbose_name_plural = "Rechnungspositionen"
        ordering = ["position_no"]

    def __str__(self):
        return f"Pos. {self.position_no}: {self.description}"

    def save(self, *args, **kwargs):
        """Auto-calculate tax_amount and gross_amount if not set."""
        if self.net_amount is not None and self.tax_rate is not None:
            if self.tax_amount is None:
                self.tax_amount = (
                    self.net_amount * self.tax_rate / Decimal("100")
                ).quantize(Decimal("0.01"))
            if self.gross_amount is None:
                self.gross_amount = self.net_amount + (self.tax_amount or Decimal("0"))
        super().save(*args, **kwargs)

"""
Tests für die Feldlängen-Hilfsfunktionen (core.services.model_fields).

Hintergrund: Freitexte aus der KI-Belegerkennung sind beliebig lang. Ohne
Kürzung bricht das INSERT auf PostgreSQL mit ``value too long for type
character varying(n)`` ab.
"""
from datetime import date

from django.test import TestCase

from core.models import Adresse
from core.services.model_fields import set_truncated, truncate_to_field
from lieferantenwesen.models import InvoiceIn


class TruncateToFieldTest(TestCase):
    def test_returns_value_unchanged_when_it_fits(self):
        self.assertEqual(
            truncate_to_field(InvoiceIn, "payment_terms_text", "14 Tage netto"),
            "14 Tage netto",
        )

    def test_truncates_to_max_length(self):
        max_length = InvoiceIn._meta.get_field("payment_terms_text").max_length
        value = "x" * (max_length + 50)

        result = truncate_to_field(InvoiceIn, "payment_terms_text", value)

        self.assertEqual(len(result), max_length)
        self.assertTrue(value.startswith(result))

    def test_none_stays_none(self):
        self.assertIsNone(truncate_to_field(InvoiceIn, "payment_terms_text", None))

    def test_non_string_values_are_stringified(self):
        self.assertEqual(
            truncate_to_field(InvoiceIn, "payment_terms_text", 42), "42"
        )

    def test_field_without_max_length_is_untouched(self):
        """TextFields haben keine Längenbegrenzung – nichts kürzen."""
        long_text = "y" * 5000
        self.assertEqual(truncate_to_field(InvoiceIn, "notes", long_text), long_text)

    def test_works_with_model_instance(self):
        max_length = Adresse._meta.get_field("strasse").max_length
        adresse = Adresse(adressen_type="LIEFERANT", name="Test")

        result = truncate_to_field(adresse, "strasse", "s" * (max_length + 1))

        self.assertEqual(len(result), max_length)

    def test_set_truncated_assigns_shortened_value(self):
        max_length = InvoiceIn._meta.get_field("payment_reference").max_length
        invoice = InvoiceIn(invoice_no="RE-1", invoice_date=date(2026, 1, 1))

        set_truncated(invoice, "payment_reference", "r" * (max_length + 10))

        self.assertEqual(len(invoice.payment_reference), max_length)

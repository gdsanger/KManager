"""
Tests für die zentrale Kontoauflösung (finanzen.services.accounts)

Deckt die Regel ab: Unterkostenart vor Hauptkostenart; auf der Erlösseite
zusätzlich Kostenart vor Steuersatz-Erlöskonto.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Kostenart, Mandant
from finanzen.models import CompanyAccountingSettings
from finanzen.services.accounts import (
    EXPENSE,
    REVENUE,
    AccountResolutionError,
    resolve_account,
    resolve_expense_account,
    resolve_revenue_account,
)


class AccountResolutionTestCase(TestCase):
    """Auflösungsregel für Aufwands- und Erlöskonten"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="Test Mandant", adresse="Str. 1", plz="12345", ort="Stadt",
        )
        self.settings = CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0="8000",
            revenue_account_7="8300",
            revenue_account_19="8400",
        )
        self.haupt = Kostenart.objects.create(
            name="Betriebskosten", aufwandskonto="4900", erloeskonto="8500",
        )
        self.unter = Kostenart.objects.create(name="Bürobedarf", parent=self.haupt)

    # --- Aufwandsseite -----------------------------------------------------

    def test_sub_cost_type_wins_over_main(self):
        self.unter.aufwandskonto = "4930"
        self.unter.save()

        self.assertEqual(
            resolve_expense_account(cost_type_sub=self.unter, cost_type_main=self.haupt),
            "4930",
        )

    def test_falls_back_to_main_cost_type(self):
        """Ohne eigenes Konto gewinnt das Konto der Hauptkostenart"""
        self.assertEqual(
            resolve_expense_account(cost_type_sub=self.unter, cost_type_main=self.haupt),
            "4900",
        )

    def test_parent_is_used_when_main_not_passed(self):
        """Die Hauptkostenart wird notfalls über parent ermittelt"""
        self.assertEqual(resolve_expense_account(cost_type_sub=self.unter), "4900")

    def test_only_main_cost_type(self):
        self.assertEqual(resolve_expense_account(cost_type_main=self.haupt), "4900")

    def test_missing_expense_account_raises(self):
        self.haupt.aufwandskonto = ""
        self.haupt.save()
        self.unter.refresh_from_db()

        with self.assertRaises(AccountResolutionError) as cm:
            resolve_expense_account(
                cost_type_sub=self.unter, context="Eingangsrechnung ER-1",
            )
        self.assertIn("Eingangsrechnung ER-1", str(cm.exception))
        self.assertIn("Aufwandskonto", str(cm.exception))

    def test_no_cost_type_at_all_raises(self):
        with self.assertRaises(AccountResolutionError):
            resolve_expense_account()

    def test_expense_has_no_tax_rate_fallback(self):
        """Auf der Aufwandsseite gibt es bewusst keinen Steuersatz-Fallback"""
        self.assertIsNone(
            resolve_account(EXPENSE, tax_key='19', accounting_settings=self.settings)
        )

    # --- Erlösseite --------------------------------------------------------

    def test_revenue_falls_back_to_tax_rate_account(self):
        self.assertEqual(
            resolve_revenue_account('19', self.settings), "8400",
        )
        self.assertEqual(resolve_revenue_account('7', self.settings), "8300")
        self.assertEqual(resolve_revenue_account('0', self.settings), "8000")

    def test_cost_type_overrides_tax_rate_account(self):
        """Ist an der Kostenart ein Erlöskonto hinterlegt, gewinnt dieses"""
        self.assertEqual(
            resolve_revenue_account(
                '19', self.settings, cost_type_sub=self.unter, cost_type_main=self.haupt,
            ),
            "8500",
        )

    def test_sub_cost_type_overrides_main_on_revenue_side(self):
        self.unter.erloeskonto = "8590"
        self.unter.save()

        self.assertEqual(
            resolve_revenue_account(
                '19', self.settings, cost_type_sub=self.unter, cost_type_main=self.haupt,
            ),
            "8590",
        )

    def test_missing_revenue_account_raises(self):
        self.settings.revenue_account_19 = ""
        self.settings.save()

        with self.assertRaises(AccountResolutionError) as cm:
            resolve_revenue_account('19', self.settings, context="Beleg R-1")
        self.assertIn("Beleg R-1", str(cm.exception))
        self.assertIn("19 %", str(cm.exception))

    def test_unknown_tax_key_has_no_fallback(self):
        self.assertIsNone(
            resolve_account(REVENUE, tax_key='16', accounting_settings=self.settings)
        )

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            resolve_account('SOMETHING')

    # --- Normalisierung ----------------------------------------------------

    def test_whitespace_is_ignored(self):
        self.haupt.aufwandskonto = "  4900  "
        self.haupt.save()

        self.assertEqual(resolve_expense_account(cost_type_main=self.haupt), "4900")


class KostenartAccountValidationTestCase(TestCase):
    """Validierung der Sachkonten an der Kostenart"""

    def test_non_numeric_expense_account_rejected(self):
        kostenart = Kostenart(name="Test", aufwandskonto="49AB")
        with self.assertRaises(ValidationError) as cm:
            kostenart.clean()
        self.assertIn('aufwandskonto', cm.exception.message_dict)

    def test_non_numeric_revenue_account_rejected(self):
        kostenart = Kostenart(name="Test", erloeskonto="84-00")
        with self.assertRaises(ValidationError) as cm:
            kostenart.clean()
        self.assertIn('erloeskonto', cm.exception.message_dict)

    def test_leading_zeros_are_preserved(self):
        kostenart = Kostenart(name="Test", aufwandskonto="0490")
        kostenart.clean()
        self.assertEqual(kostenart.aufwandskonto, "0490")

    def test_empty_accounts_are_valid(self):
        Kostenart(name="Test").clean()


class AccountingSettingsValidationTestCase(TestCase):
    """Validierung der Buchhaltungseinstellungen"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="Test Mandant", adresse="Str. 1", plz="12345", ort="Stadt",
        )

    def test_placeholder_numbers_are_prefilled(self):
        settings = CompanyAccountingSettings.objects.create(company=self.company)
        self.assertEqual(settings.datev_consultant_number, '1001')
        self.assertEqual(settings.datev_client_number, '1')

    def test_default_account_length(self):
        settings = CompanyAccountingSettings.objects.create(company=self.company)
        self.assertEqual(settings.account_length, 4)

    def test_invalid_account_length_rejected(self):
        settings = CompanyAccountingSettings(company=self.company, account_length=3)
        with self.assertRaises(ValidationError) as cm:
            settings.clean()
        self.assertIn('account_length', cm.exception.message_dict)

    def test_non_numeric_account_rejected(self):
        settings = CompanyAccountingSettings(company=self.company, bank_account="12AB")
        with self.assertRaises(ValidationError) as cm:
            settings.clean()
        self.assertIn('bank_account', cm.exception.message_dict)

    def test_fiscal_year_start_defaults_to_january(self):
        from datetime import date

        settings = CompanyAccountingSettings.objects.create(company=self.company)
        self.assertEqual(settings.effective_fiscal_year_start(2026), date(2026, 1, 1))

    def test_fiscal_year_start_is_projected_onto_year(self):
        from datetime import date

        settings = CompanyAccountingSettings.objects.create(
            company=self.company, fiscal_year_start=date(2020, 7, 1),
        )
        self.assertEqual(settings.effective_fiscal_year_start(2026), date(2026, 7, 1))

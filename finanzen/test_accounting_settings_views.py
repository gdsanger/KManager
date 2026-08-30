"""
Tests für die Frontend-Pflege der Buchhaltungseinstellungen.

Die Bedienoberfläche liegt in der Auftragsverwaltung unter „Buchhaltung";
Formular und Modell bleiben im Finanzen-Modul. Geprüft werden das Anlegen beim
ersten Aufruf, das Bearbeiten eines bestehenden Datensatzes, die Wahrung der
OneToOne-Beziehung bei mehrfachem Aufruf sowie die beiden Validierungsregeln
(Sachkonten nur Ziffern, Sachkontenlänge 4–8).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Mandant
from finanzen.forms import CompanyAccountingSettingsForm
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry


class AccountingSettingsViewTestBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('tester', password='pw12345678')
        self.client.login(username='tester', password='pw12345678')

        self.company = Mandant.objects.create(
            name="Test Mandant", adresse="Str. 1", plz="12345", ort="Stadt",
        )
        self.list_url = reverse('auftragsverwaltung:accounting_settings_list')
        self.edit_url = reverse(
            'auftragsverwaltung:accounting_settings_edit', args=[self.company.pk]
        )

    def _post_data(self, **overrides):
        """Vollständiger, gültiger Formular-POST."""
        data = {
            'datev_consultant_number': '0001001',
            'datev_client_number': '00042',
            'tax_number': '123/456/78901',
            'account_length': '4',
            'fiscal_year_start': '',
            'revenue_account_0': '8000',
            'revenue_account_7': '8300',
            'revenue_account_19': '8400',
            'bank_account': '1200',
            'cash_account': '1000',
            'clearing_account': '1590',
        }
        data.update(overrides)
        return data


class AccountingSettingsListTestCase(AccountingSettingsViewTestBase):
    """Liste der Mandanten mit Pflegestand"""

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_shows_mandant_without_settings_as_not_maintained(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Mandant")
        self.assertContains(response, "noch nicht angelegt")

    def test_shows_mandant_with_settings_as_maintained(self):
        CompanyAccountingSettings.objects.create(company=self.company)

        response = self.client.get(self.list_url)

        self.assertContains(response, "gepflegt")
        self.assertNotContains(response, "noch nicht angelegt")

    def test_links_to_edit_view(self):
        response = self.client.get(self.list_url)

        self.assertContains(response, self.edit_url)


class AccountingSettingsEditTestCase(AccountingSettingsViewTestBase):
    """Anlegen, Bearbeiten und Wahrung der OneToOne-Beziehung"""

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)

    def test_unknown_mandant_returns_404(self):
        url = reverse('auftragsverwaltung:accounting_settings_edit', args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_first_call_creates_exactly_one_record(self):
        self.assertFalse(CompanyAccountingSettings.objects.exists())

        response = self.client.get(self.edit_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            CompanyAccountingSettings.objects.filter(company=self.company).count(), 1
        )

    def test_repeated_calls_create_no_duplicate(self):
        self.client.get(self.edit_url)
        self.client.get(self.edit_url)
        self.client.post(self.edit_url, self._post_data())

        self.assertEqual(
            CompanyAccountingSettings.objects.filter(company=self.company).count(), 1
        )

    def test_post_saves_existing_record(self):
        existing = CompanyAccountingSettings.objects.create(
            company=self.company, revenue_account_19='8400',
        )

        response = self.client.post(
            self.edit_url, self._post_data(revenue_account_19='8401'), follow=True
        )

        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.revenue_account_19, '8401')
        self.assertEqual(existing.tax_number, '123/456/78901')

    def test_post_redirects_to_list_with_success_message(self):
        response = self.client.post(self.edit_url, self._post_data(), follow=True)

        self.assertRedirects(response, self.list_url)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('gespeichert' in m for m in messages), messages)

    def test_leading_zeros_are_preserved(self):
        self.client.post(self.edit_url, self._post_data(
            datev_consultant_number='0001001',
            datev_client_number='00042',
            revenue_account_0='0800',
        ))

        settings_obj = CompanyAccountingSettings.objects.get(company=self.company)
        self.assertEqual(settings_obj.datev_consultant_number, '0001001')
        self.assertEqual(settings_obj.datev_client_number, '00042')
        self.assertEqual(settings_obj.revenue_account_0, '0800')

    def test_fiscal_year_start_is_saved(self):
        self.client.post(self.edit_url, self._post_data(fiscal_year_start='2026-07-01'))

        settings_obj = CompanyAccountingSettings.objects.get(company=self.company)
        self.assertEqual(settings_obj.fiscal_year_start, date(2026, 7, 1))

    def test_edit_form_prefills_stored_date(self):
        CompanyAccountingSettings.objects.create(
            company=self.company, fiscal_year_start=date(2026, 7, 1),
        )

        response = self.client.get(self.edit_url)

        self.assertContains(response, 'value="2026-07-01"')

    def test_all_fields_except_company_are_editable(self):
        response = self.client.get(self.edit_url)

        form = response.context['form']
        model_fields = {
            f.name for f in CompanyAccountingSettings._meta.fields
            if f.name not in ('id', 'company')
        }
        self.assertEqual(set(form.fields), model_fields)

    def test_help_texts_are_rendered(self):
        response = self.client.get(self.edit_url)

        self.assertContains(response, 'Personenkonten sind eine Stelle länger')
        self.assertContains(response, 'Kalenderwirtschaftsjahr')


class AccountingSettingsValidationTestCase(AccountingSettingsViewTestBase):
    """Modell-Validierung muss als Feldfehler im Formular ankommen"""

    def test_non_numeric_account_is_a_field_error(self):
        response = self.client.post(
            self.edit_url, self._post_data(revenue_account_19='84ab')
        )

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('revenue_account_19', form.errors)
        self.assertIn('nur aus Ziffern', form.errors['revenue_account_19'][0])

        settings_obj = CompanyAccountingSettings.objects.get(company=self.company)
        self.assertNotEqual(settings_obj.revenue_account_19, '84ab')

    def test_account_length_below_range_is_a_field_error(self):
        response = self.client.post(self.edit_url, self._post_data(account_length='3'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('account_length', response.context['form'].errors)

    def test_account_length_above_range_is_a_field_error(self):
        response = self.client.post(self.edit_url, self._post_data(account_length='9'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('account_length', response.context['form'].errors)

    def test_form_strips_whitespace_around_accounts(self):
        form = CompanyAccountingSettingsForm(
            self._post_data(revenue_account_19=' 8400 '),
            instance=CompanyAccountingSettings(company=self.company),
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.revenue_account_19, '8400')


class AccountingSettingsInDatevHeaderTestCase(AccountingSettingsViewTestBase):
    """Im Frontend gepflegte Werte müssen im EXTF-Kopfsatz ankommen"""

    def test_frontend_values_appear_in_booking_batch_header(self):
        self.client.post(self.edit_url, self._post_data(
            datev_consultant_number='0007007',
            datev_client_number='00042',
            account_length='5',
            fiscal_year_start='2026-07-01',
        ))

        customer = Adresse.objects.create(
            adressen_type='KUNDE', name="Kunde", strasse="Str. 1",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        document = SalesDocument.objects.create(
            company=self.company, document_type=DocumentType.objects.get(key='invoice'),
            customer=customer, number='R26-00001', status='SENT',
            issue_date=date(2026, 8, 15),
        )
        OutgoingInvoiceJournalEntry.objects.create(
            company=self.company, document=document, document_number='R26-00001',
            document_date=date(2026, 8, 15), document_kind='INVOICE',
            customer_name="Kunde", debtor_number=customer.debitor_number,
            net_19=Decimal('1000.00'), tax_amount=Decimal('190.00'),
            gross_amount=Decimal('1190.00'), revenue_account_19='8400',
        )

        response = self.client.post(
            reverse('auftragsverwaltung:datev_export_download'),
            {
                'company': self.company.pk,
                'period_type': 'MONTH',
                'year': 2026,
                'month': 8,
            },
        )

        self.assertEqual(response['Content-Type'], 'text/csv; charset=windows-1252')
        header = response.content.decode('cp1252').splitlines()[0].split(';')
        # Positionen laut EXTF-Kopfsatz: Berater, Mandant, WJ-Beginn, Sachkontenlänge
        self.assertEqual(header[10], '0007007')
        self.assertEqual(header[11], '00042')
        self.assertEqual(header[12], '20260701')
        self.assertEqual(header[13], '5')

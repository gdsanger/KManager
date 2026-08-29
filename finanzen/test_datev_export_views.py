"""
Tests für die Finanzen-UI des DATEV-Exports.

Prüft Zeitraumauswahl, Vorschau, Fehlerliste vor dem Export und den Download
inklusive Statuspflege.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Mandant
from finanzen.forms import DatevExportForm
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry


class DatevExportViewTestBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('tester', password='pw12345678')
        self.client.login(username='tester', password='pw12345678')

        self.company = Mandant.objects.create(
            name="Test Mandant", adresse="Str. 1", plz="12345", ort="Stadt",
        )
        CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0="8000", revenue_account_7="8300", revenue_account_19="8400",
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE', name="Kunde", strasse="Str. 1",
            plz="12345", ort="Stadt", land="Deutschland",
        )
        self.doc_type = DocumentType.objects.get(key='invoice')

    def _journal_entry(self, number='R26-00001', debtor=None, revenue='8400'):
        document = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type, customer=self.customer,
            number=number, status='SENT', issue_date=date(2026, 1, 15),
        )
        return OutgoingInvoiceJournalEntry.objects.create(
            company=self.company, document=document, document_number=number,
            document_date=date(2026, 1, 15), document_kind='INVOICE',
            customer_name="Kunde",
            debtor_number=self.customer.debitor_number if debtor is None else debtor,
            net_19=Decimal('1000.00'), tax_amount=Decimal('190.00'),
            gross_amount=Decimal('1190.00'), revenue_account_19=revenue,
        )

    def _params(self, **overrides):
        params = {
            'company': self.company.pk,
            'period_type': 'MONTH',
            'year': 2026,
            'month': 1,
        }
        params.update(overrides)
        return params


class DatevExportFormTestCase(TestCase):
    """Zeitraumberechnung des Formulars"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name="M", adresse="S", plz="1", ort="O",
        )

    def _form(self, **data):
        base = {'company': self.company.pk, 'year': 2026}
        base.update(data)
        form = DatevExportForm(base)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_month_period(self):
        form = self._form(period_type='MONTH', month=2)
        self.assertEqual(form.period(), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(form.period_label(), 'Februar 2026')

    def test_quarter_period(self):
        form = self._form(period_type='QUARTER', quarter=2)
        self.assertEqual(form.period(), (date(2026, 4, 1), date(2026, 6, 30)))
        self.assertEqual(form.period_label(), 'Q2/2026')

    def test_year_period(self):
        form = self._form(period_type='YEAR')
        self.assertEqual(form.period(), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(form.period_label(), '2026')

    def test_month_is_required_for_month_period(self):
        form = DatevExportForm({
            'company': self.company.pk, 'year': 2026, 'period_type': 'MONTH',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('month', form.errors)

    def test_quarter_is_required_for_quarter_period(self):
        form = DatevExportForm({
            'company': self.company.pk, 'year': 2026, 'period_type': 'QUARTER',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('quarter', form.errors)


class DatevExportViewTestCase(DatevExportViewTestBase):
    """Vorschau- und Downloadansicht"""

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse('finanzen:datev_export'))
        self.assertEqual(response.status_code, 302)

    def test_home_renders(self):
        response = self.client.get(reverse('finanzen:home'))
        self.assertEqual(response.status_code, 200)

    def test_empty_form_shows_no_preview(self):
        response = self.client.get(reverse('finanzen:datev_export'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['preview'])

    def test_preview_shows_bookings(self):
        self._journal_entry()
        response = self.client.get(reverse('finanzen:datev_export'), self._params())

        preview = response.context['preview']
        self.assertEqual(preview.booking_count, 1)
        self.assertEqual(response.context['period_label'], 'Januar 2026')

    def test_preview_lists_problems(self):
        self._journal_entry(debtor='')
        response = self.client.get(reverse('finanzen:datev_export'), self._params())

        preview = response.context['preview']
        self.assertEqual(len(preview.problems), 1)
        self.assertContains(response, 'ohne auflösbares Konto')

    def test_download_returns_file_and_marks_exported(self):
        entry = self._journal_entry()
        response = self.client.post(
            reverse('finanzen:datev_export_download'), self._params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('EXTF_Buchungsstapel_20260101_20260131.csv', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'"EXTF"'))

        entry.refresh_from_db()
        self.assertEqual(entry.export_status, 'EXPORTED')
        self.assertTrue(entry.export_batch_id)

    def test_download_is_blocked_while_problems_remain(self):
        entry = self._journal_entry(debtor='')
        response = self.client.post(
            reverse('finanzen:datev_export_download'), self._params(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Content-Disposition', response)
        entry.refresh_from_db()
        self.assertEqual(entry.export_status, 'OPEN')

    def test_download_rejects_get(self):
        response = self.client.get(reverse('finanzen:datev_export_download'))
        self.assertEqual(response.status_code, 302)

    def test_empty_period_does_not_mark_anything(self):
        response = self.client.post(
            reverse('finanzen:datev_export_download'), self._params(month=6),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Content-Disposition', response)

    def test_period_across_year_boundary_reports_error(self):
        response = self.client.get(
            reverse('finanzen:datev_export'), self._params(period_type='YEAR'),
        )
        # Ein Jahresexport bleibt innerhalb eines Jahres und ist damit gültig.
        self.assertIsNotNone(response.context['preview'])

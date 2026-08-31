"""
Tests für die Zahlungserfassung an Ausgangsrechnungen (Agira #1198).

Abgedeckt: Zahlung erfassen und zurücknehmen, Ablehnung bei Entwurf,
storniertem Beleg und Zahldatum vor Belegdatum, die abgeleitete
Überfälligkeit an ihren Grenzfällen sowie die Unversehrtheit des
Journaleintrags.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from core.models import Adresse, Mandant, TaxRate
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry
from finanzen.services.journal import create_journal_entry

User = get_user_model()


class ZahlungseingangTestBase(TestCase):
    """Gemeinsame Testdaten für die Zahlungserfassung."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='geheim123')
        self.client.force_login(self.user)

        self.company = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland",
        )
        CompanyAccountingSettings.objects.create(
            company=self.company,
            revenue_account_0="8000",
            revenue_account_7="8100",
            revenue_account_19="8400",
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            firma="Kunde GmbH",
            name="Max Mustermann",
            strasse="Kundenstraße 1",
            plz="54321",
            ort="Kundenstadt",
            land="Deutschland",
            debitor_number="10001",
        )
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.doc_type_credit = DocumentType.objects.get(key='credit')
        self.doc_type_quote = DocumentType.objects.get(key='quote')
        self.tax_19 = TaxRate.objects.create(code='VAT19', name='19%', rate=Decimal('0.1900'))

        self.today = timezone.localdate()

    def _create_document(self, document_type=None, number='R26-00001',
                         status='SENT', issue_date=None, **kwargs):
        defaults = {
            'company': self.company,
            'document_type': document_type or self.doc_type_invoice,
            'customer': self.customer,
            'number': number,
            'status': status,
            'issue_date': issue_date or (self.today - timedelta(days=10)),
            'total_net': Decimal('100.00'),
            'total_tax': Decimal('19.00'),
            'total_gross': Decimal('119.00'),
        }
        defaults.update(kwargs)
        return SalesDocument.objects.create(**defaults)

    def _mark_paid(self, document, payment_date=None, follow=False, **extra):
        data = dict(extra)
        if payment_date is not None:
            data['payment_date'] = payment_date.strftime('%Y-%m-%d')
        return self.client.post(
            reverse('auftragsverwaltung:invoice_mark_as_paid', kwargs={'pk': document.pk}),
            data,
            follow=follow,
        )

    def _unmark_paid(self, document, follow=False, **extra):
        return self.client.post(
            reverse('auftragsverwaltung:invoice_unmark_as_paid', kwargs={'pk': document.pk}),
            dict(extra),
            follow=follow,
        )

    @staticmethod
    def _messages(response):
        return [str(m) for m in response.context['messages']]


class MarkAsPaidViewTests(ZahlungseingangTestBase):
    """Zahlung erfassen (invoice_mark_as_paid)."""

    def test_mark_invoice_as_paid_sets_paid_at_and_status(self):
        invoice = self._create_document()
        payment_date = self.today - timedelta(days=2)

        response = self._mark_paid(invoice, payment_date)

        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')
        self.assertIsNotNone(invoice.paid_at)
        self.assertEqual(invoice.payment_date, payment_date)
        self.assertTrue(invoice.is_paid)

    def test_payment_date_defaults_to_today(self):
        """Ohne Angabe im POST wird der heutige Tag erfasst."""
        invoice = self._create_document()

        self._mark_paid(invoice)

        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_date, self.today)

    def test_credit_note_can_be_marked_as_paid(self):
        """Gutschriften sind journalrelevant und lassen sich ausgleichen."""
        credit = self._create_document(document_type=self.doc_type_credit, number='G26-00001')

        self._mark_paid(credit, self.today)

        credit.refresh_from_db()
        self.assertEqual(credit.status, 'PAID')
        self.assertEqual(credit.payment_date, self.today)

    def test_payment_date_before_issue_date_is_rejected(self):
        invoice = self._create_document(issue_date=self.today - timedelta(days=5))

        response = self._mark_paid(invoice, self.today - timedelta(days=6), follow=True)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)
        self.assertEqual(invoice.status, 'SENT')
        self.assertTrue(
            any('liegt vor dem' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_payment_date_equal_to_issue_date_is_accepted(self):
        """Grenzfall: Zahlung am Belegtag ist zulässig."""
        issue_date = self.today - timedelta(days=3)
        invoice = self._create_document(issue_date=issue_date)

        self._mark_paid(invoice, issue_date)

        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_date, issue_date)

    def test_draft_cannot_be_marked_as_paid(self):
        invoice = self._create_document(status='DRAFT', number='')

        response = self._mark_paid(invoice, self.today, follow=True)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)
        self.assertEqual(invoice.status, 'DRAFT')
        self.assertTrue(
            any('Entwurf' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_cancelled_cannot_be_marked_as_paid(self):
        invoice = self._create_document(status='CANCELLED')

        response = self._mark_paid(invoice, self.today, follow=True)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)
        self.assertEqual(invoice.status, 'CANCELLED')
        self.assertTrue(
            any('Storniert' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_quote_is_not_journal_relevant(self):
        """Angebote werden nicht im Rechnungsausgangsjournal geführt."""
        quote = self._create_document(document_type=self.doc_type_quote, number='A26-00001')

        response = self._mark_paid(quote, self.today, follow=True)

        quote.refresh_from_db()
        self.assertIsNone(quote.paid_at)
        self.assertTrue(
            any('weder Rechnung noch Gutschrift' in message
                for message in self._messages(response)),
            self._messages(response),
        )

    def test_already_paid_document_is_not_set_again(self):
        first_payment = self.today - timedelta(days=4)
        invoice = self._create_document()
        self._mark_paid(invoice, first_payment)

        response = self._mark_paid(invoice, self.today, follow=True)

        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_date, first_payment)
        self.assertTrue(
            any('bereits eine Zahlung' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_invalid_payment_date_gives_message_instead_of_server_error(self):
        invoice = self._create_document()

        response = self.client.post(
            reverse('auftragsverwaltung:invoice_mark_as_paid', kwargs={'pk': invoice.pk}),
            {'payment_date': '31.02.2026'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)
        self.assertTrue(
            any('kein gültiges Zahldatum' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_get_is_not_allowed(self):
        """Die Aktion verändert Zustand und ist deshalb POST-only."""
        invoice = self._create_document()

        response = self.client.get(
            reverse('auftragsverwaltung:invoice_mark_as_paid', kwargs={'pk': invoice.pk})
        )

        self.assertEqual(response.status_code, 405)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)

    def test_redirects_back_to_list_when_next_is_given(self):
        """Aus der Liste heraus soll die Liste (inkl. Filter) erhalten bleiben."""
        invoice = self._create_document()
        next_url = '/auftragsverwaltung/rechnungen/?payment_status=open'

        response = self._mark_paid(invoice, self.today, next=next_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], next_url)

    def test_next_to_foreign_host_is_ignored(self):
        """Kein Open Redirect über den next-Parameter."""
        invoice = self._create_document()

        response = self._mark_paid(invoice, self.today, next='https://evil.example.com/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('auftragsverwaltung:document_detail',
                    kwargs={'doc_key': 'invoice', 'pk': invoice.pk}),
        )


class UnmarkAsPaidViewTests(ZahlungseingangTestBase):
    """Zahlung zurücknehmen (invoice_unmark_as_paid)."""

    def test_unmark_resets_paid_at_and_status(self):
        invoice = self._create_document()
        self._mark_paid(invoice, self.today)

        response = self._unmark_paid(invoice)

        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertIsNone(invoice.paid_at)
        self.assertEqual(invoice.status, 'SENT')
        self.assertFalse(invoice.is_paid)

    def test_unmark_on_unpaid_document_gives_message(self):
        invoice = self._create_document()

        response = self._unmark_paid(invoice, follow=True)

        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'SENT')
        self.assertTrue(
            any('keine Zahlung erfasst' in message for message in self._messages(response)),
            self._messages(response),
        )

    def test_get_is_not_allowed(self):
        invoice = self._create_document()
        self._mark_paid(invoice, self.today)

        response = self.client.get(
            reverse('auftragsverwaltung:invoice_unmark_as_paid', kwargs={'pk': invoice.pk})
        )

        self.assertEqual(response.status_code, 405)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')


class IsOverdueTests(ZahlungseingangTestBase):
    """Überfälligkeit wird abgeleitet, nicht gespeichert."""

    def test_due_yesterday_is_overdue(self):
        invoice = self._create_document(due_date=self.today - timedelta(days=1))
        self.assertTrue(invoice.is_overdue)
        self.assertEqual(invoice.payment_state, 'OVERDUE')

    def test_due_today_is_not_overdue(self):
        invoice = self._create_document(due_date=self.today)
        self.assertFalse(invoice.is_overdue)
        self.assertEqual(invoice.payment_state, 'OPEN')

    def test_due_tomorrow_is_not_overdue(self):
        invoice = self._create_document(due_date=self.today + timedelta(days=1))
        self.assertFalse(invoice.is_overdue)

    def test_without_due_date_never_overdue(self):
        invoice = self._create_document(due_date=None)
        self.assertFalse(invoice.is_overdue)

    def test_paid_document_is_not_overdue(self):
        invoice = self._create_document(due_date=self.today - timedelta(days=5))
        self._mark_paid(invoice, self.today)
        invoice.refresh_from_db()

        self.assertFalse(invoice.is_overdue)
        self.assertEqual(invoice.payment_state, 'PAID')

    def test_draft_and_cancelled_are_not_overdue(self):
        draft = self._create_document(
            status='DRAFT', number='', due_date=self.today - timedelta(days=5)
        )
        cancelled = self._create_document(
            status='CANCELLED', number='R26-00002', due_date=self.today - timedelta(days=5)
        )

        self.assertFalse(draft.is_overdue)
        self.assertFalse(cancelled.is_overdue)

    def test_overdue_status_is_never_stored(self):
        """Ein Beleg wird überfällig, ohne dass sich sein Status ändert."""
        invoice = self._create_document(due_date=self.today - timedelta(days=1))

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'SENT')
        self.assertTrue(invoice.is_overdue)

    def test_overdue_filter_matches_property(self):
        overdue = self._create_document(
            number='R26-00010', due_date=self.today - timedelta(days=1)
        )
        due_today = self._create_document(number='R26-00011', due_date=self.today)
        paid = self._create_document(
            number='R26-00012', due_date=self.today - timedelta(days=1)
        )
        self._mark_paid(paid, self.today)

        overdue_pks = set(
            SalesDocument.objects.filter(SalesDocument.overdue_filter())
            .values_list('pk', flat=True)
        )

        self.assertEqual(overdue_pks, {overdue.pk})
        self.assertNotIn(due_today.pk, overdue_pks)


class UnpaidFilterTests(ZahlungseingangTestBase):
    """Offene Posten: Filterbedingung für Datenbankabfragen."""

    def test_unpaid_filter_excludes_paid_draft_and_cancelled(self):
        open_invoice = self._create_document(number='R26-00020')
        paid = self._create_document(number='R26-00021')
        self._mark_paid(paid, self.today)
        draft = self._create_document(number='', status='DRAFT')
        cancelled = self._create_document(number='R26-00022', status='CANCELLED')

        unpaid_pks = set(
            SalesDocument.objects.filter(SalesDocument.unpaid_filter())
            .values_list('pk', flat=True)
        )

        self.assertIn(open_invoice.pk, unpaid_pks)
        self.assertNotIn(paid.pk, unpaid_pks)
        self.assertNotIn(draft.pk, unpaid_pks)
        self.assertNotIn(cancelled.pk, unpaid_pks)


class DashboardKpiTests(ZahlungseingangTestBase):
    """Die Dashboard-Kennzahlen folgen dem erfassten Zahlstatus."""

    def test_kpis_drop_after_payment_is_recorded(self):
        invoice = self._create_document(number='R26-00030')
        self._create_document(number='R26-00031')

        response = self.client.get(reverse('auftragsverwaltung:home'))
        self.assertEqual(response.context['kpi_unpaid_invoices'], 2)
        self.assertEqual(response.context['kpi_open_amount'], Decimal('238.00'))

        self._mark_paid(invoice, self.today)

        response = self.client.get(reverse('auftragsverwaltung:home'))
        self.assertEqual(response.context['kpi_unpaid_invoices'], 1)
        self.assertEqual(response.context['kpi_open_amount'], Decimal('119.00'))

    def test_draft_and_cancelled_do_not_count_as_open(self):
        self._create_document(number='', status='DRAFT')
        self._create_document(number='R26-00032', status='CANCELLED')

        response = self.client.get(reverse('auftragsverwaltung:home'))

        self.assertEqual(response.context['kpi_unpaid_invoices'], 0)
        self.assertEqual(response.context['kpi_open_amount'], Decimal('0.00'))


class DocumentListPaymentFilterTests(ZahlungseingangTestBase):
    """Zahlstatus-Filter und -Spalte der Rechnungsliste."""

    def _list_pks(self, response):
        return {row.record.pk for row in response.context['table'].page.object_list}

    def test_filter_open_and_overdue(self):
        open_invoice = self._create_document(
            number='R26-00040', due_date=self.today + timedelta(days=5)
        )
        overdue_invoice = self._create_document(
            number='R26-00041', due_date=self.today - timedelta(days=5)
        )
        paid_invoice = self._create_document(number='R26-00042')
        self._mark_paid(paid_invoice, self.today)

        url = reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})

        open_response = self.client.get(url, {'payment_status': 'open'})
        self.assertEqual(self._list_pks(open_response), {open_invoice.pk, overdue_invoice.pk})

        overdue_response = self.client.get(url, {'payment_status': 'overdue'})
        self.assertEqual(self._list_pks(overdue_response), {overdue_invoice.pk})

        paid_response = self.client.get(url, {'payment_status': 'paid'})
        self.assertEqual(self._list_pks(paid_response), {paid_invoice.pk})

    def test_list_shows_payment_status_and_action(self):
        invoice = self._create_document(number='R26-00043')

        response = self.client.get(
            reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})
        )
        content = response.content.decode()

        self.assertIn('Zahlung', content)
        self.assertIn('js-mark-paid', content)
        self.assertIn(
            reverse('auftragsverwaltung:invoice_mark_as_paid', kwargs={'pk': invoice.pk}),
            content,
        )

    def test_paid_row_offers_reversal(self):
        invoice = self._create_document(number='R26-00044')
        self._mark_paid(invoice, self.today)

        response = self.client.get(
            reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})
        )
        content = response.content.decode()

        self.assertIn('js-unmark-paid', content)
        self.assertIn(
            reverse('auftragsverwaltung:invoice_unmark_as_paid', kwargs={'pk': invoice.pk}),
            content,
        )


class DocumentDetailPaymentDisplayTests(ZahlungseingangTestBase):
    """Zahlstatus und Zahldatum im Kopfbereich der Belegseite."""

    def _detail(self, document):
        return self.client.get(
            reverse('auftragsverwaltung:document_detail',
                    kwargs={'doc_key': document.document_type.key, 'pk': document.pk})
        )

    def test_open_invoice_offers_mark_as_paid(self):
        invoice = self._create_document(number='R26-00070')

        content = self._detail(invoice).content.decode()

        self.assertIn('Als bezahlt markieren', content)
        self.assertIn('Zahlstatus', content)
        self.assertIn('markPaidModal', content)
        self.assertIn('id="markPaidButton"', content)
        self.assertNotIn('id="unmarkPaidButton"', content)

    def test_paid_invoice_shows_payment_date_and_reversal(self):
        payment_date = self.today - timedelta(days=1)
        invoice = self._create_document(number='R26-00071')
        self._mark_paid(invoice, payment_date)
        invoice.refresh_from_db()

        content = self._detail(invoice).content.decode()

        self.assertIn('id="unmarkPaidButton"', content)
        self.assertIn(payment_date.strftime('%d.%m.%Y'), content)
        self.assertNotIn('id="markPaidButton"', content)

    def test_draft_offers_no_payment_action(self):
        draft = self._create_document(number='', status='DRAFT')

        content = self._detail(draft).content.decode()

        self.assertNotIn('id="markPaidButton"', content)
        self.assertIn('Kein offener Posten', content)


class JournalEntryUntouchedTests(ZahlungseingangTestBase):
    """
    Der Journaleintrag ist ein Snapshot der Finalisierung.

    Eine später erfasste Zahlung ändert daran nichts - weder am Eintrag noch an
    seinem Exportstatus. Zahlungsbuchungen entstehen im Fibu-System aus dessen
    Bankanbindung und werden von GIS bewusst nicht exportiert.
    """

    def _create_invoice_with_journal_entry(self):
        invoice = self._create_document(number='R26-00050')
        SalesDocumentLine.objects.create(
            document=invoice,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            tax_rate=self.tax_19,
            quantity=Decimal('1'),
            unit_price_net=Decimal('100.00'),
            description='Leistung',
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00'),
        )
        entry, created = create_journal_entry(invoice)
        self.assertTrue(created)
        return invoice, entry

    def test_journal_entry_unchanged_after_payment(self):
        invoice, entry = self._create_invoice_with_journal_entry()
        before = {
            field.name: getattr(entry, field.name)
            for field in OutgoingInvoiceJournalEntry._meta.fields
        }

        self._mark_paid(invoice, self.today)
        self._unmark_paid(invoice)
        self._mark_paid(invoice, self.today)

        entry.refresh_from_db()
        after = {
            field.name: getattr(entry, field.name)
            for field in OutgoingInvoiceJournalEntry._meta.fields
        }

        self.assertEqual(before, after)
        self.assertEqual(entry.export_status, 'OPEN')
        self.assertEqual(
            OutgoingInvoiceJournalEntry.objects.filter(document=invoice).count(), 1
        )


class DocumentCopyTests(ZahlungseingangTestBase):
    """Eine Kopie eines bezahlten Belegs ist selbst nicht bezahlt."""

    def test_copy_of_paid_document_is_unpaid(self):
        invoice = self._create_document(number='R26-00060')
        self._mark_paid(invoice, self.today)
        invoice.refresh_from_db()

        copy = invoice.clone_as(self.doc_type_invoice)

        self.assertIsNone(copy.paid_at)
        self.assertFalse(copy.is_paid)
        self.assertEqual(copy.status, 'DRAFT')


class MarkAsPaidModelTests(ZahlungseingangTestBase):
    """Die fachlichen Regeln sitzen am Modell, nicht nur in der View."""

    def test_mark_as_paid_stores_local_day(self):
        invoice = self._create_document()
        payment_date = date(2026, 7, 1)
        invoice.issue_date = date(2026, 6, 1)
        invoice.save()

        invoice.mark_as_paid(payment_date=payment_date)

        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_date, payment_date)

    def test_mark_as_paid_rejects_draft(self):
        invoice = self._create_document(status='DRAFT', number='')

        with self.assertRaises(ValueError) as cm:
            invoice.mark_as_paid()

        self.assertIn('Entwurf', str(cm.exception))

    def test_unmark_as_paid_rejects_unpaid(self):
        invoice = self._create_document()

        with self.assertRaises(ValueError):
            invoice.unmark_as_paid()

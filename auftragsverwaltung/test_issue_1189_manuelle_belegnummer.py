"""
Tests für die manuelle Vergabe von Belegnummern (Nacherfassung von Altbelegen)

Schwerpunkte:
- Beim Anlegen kann eine Nummer vorgegeben werden; bleibt das Feld leer, wird
  wie bisher automatisch aus dem Nummernkreis vergeben.
- Eine manuelle Nummer verbraucht keine Nummer aus dem Nummernkreis, zieht ihn
  aber nach, wenn sie zu Format und Jahr passt.
- Doppelte Nummern werden mit einer Meldung am Feld abgewiesen, nicht mit einem
  Serverfehler.
- Die Nummer ist ab Status SENT fixiert.
- Die automatische Vergabe richtet sich nach dem Belegdatum, nicht nach dem
  Erfassungstag.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, NumberRange, SalesDocument
from auftragsverwaltung.services.invoice_finalization import finalize_document
from auftragsverwaltung.services.number_range import (
    get_next_number,
    reserve_manual_number,
)
from core.models import Mandant, Adresse
from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry
from finanzen.services import datev_export


User = get_user_model()


class ManualNumberTestBase(TestCase):
    """Gemeinsame Testdaten für Belege mit manueller Nummer"""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.client = Client()
        self.client.login(username='tester', password='pass12345')

        self.company = Mandant.objects.create(
            name='Test Mandant GmbH', adresse='Str. 1', plz='12345', ort='Stadt',
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE', name='Kunde', strasse='Str. 1',
            plz='12345', ort='Stadt', land='Deutschland',
            debitor_number='10001',
        )
        self.doc_type = DocumentType.objects.get(key='invoice')
        self.today = date.today()
        self.yy = self.today.year % 100

    def _number_range(self, current_seq=0, current_year=None, **kwargs):
        """Nummernkreis für Rechnungen dieses Mandanten anlegen"""
        defaults = {
            'company': self.company,
            'target': 'DOCUMENT',
            'document_type': self.doc_type,
            'format': '{prefix}{yy}-{seq:05d}',
            'reset_policy': 'YEARLY',
            'current_year': self.yy if current_year is None else current_year,
            'current_seq': current_seq,
        }
        defaults.update(kwargs)
        return NumberRange.objects.create(**defaults)

    def _post_create(self, **overrides):
        """Anlage-Formular abschicken"""
        data = {
            'company_id': self.company.pk,
            'customer_id': self.customer.pk,
            'subject': 'Nacherfasste Rechnung',
            'issue_date': self.today.strftime('%Y-%m-%d'),
            'number': '',
        }
        data.update(overrides)
        return self.client.post(
            reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'}),
            data,
        )

    def _post_update(self, document, **overrides):
        """Bearbeiten-Formular abschicken"""
        data = {
            'company_id': self.company.pk,
            'customer_id': self.customer.pk,
            'subject': document.subject,
            'issue_date': document.issue_date.strftime('%Y-%m-%d'),
            'status': document.status,
            'number': document.number,
        }
        data.update(overrides)
        return self.client.post(
            reverse(
                'auftragsverwaltung:document_update',
                kwargs={'doc_key': 'invoice', 'pk': document.pk},
            ),
            data,
        )


class ManualNumberCreateTestCase(ManualNumberTestBase):
    """Anlage eines Belegs mit und ohne vorgegebene Nummer"""

    def test_manual_number_is_used_as_entered(self):
        response = self._post_create(number='R19-00042')

        self.assertEqual(response.status_code, 302)
        document = SalesDocument.objects.get()
        self.assertEqual(document.number, 'R19-00042')

    def test_empty_number_falls_back_to_number_range(self):
        """Ohne Eingabe bleibt es beim bisherigen Verhalten"""
        self._number_range(current_seq=4)

        response = self._post_create(number='')

        self.assertEqual(response.status_code, 302)
        document = SalesDocument.objects.get()
        self.assertEqual(document.number, f'R{self.yy:02d}-00005')

    def test_free_legacy_number_leaves_number_range_untouched(self):
        """Eine Altnummer außerhalb des Formats verbraucht keine Nummer"""
        number_range = self._number_range(current_seq=7)

        self._post_create(number='ALT-2019/0815')

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 7)
        self.assertEqual(number_range.current_year, self.yy)

    def test_format_conform_number_advances_sequence(self):
        """Eine formatkonforme Nummer wird nicht ein zweites Mal vergeben"""
        number_range = self._number_range(current_seq=3)

        self._post_create(number=f'R{self.yy:02d}-00042')

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 42)

        # Die nächste automatische Nummer liegt hinter der manuellen
        self.assertEqual(
            get_next_number(self.company, self.doc_type, self.today),
            f'R{self.yy:02d}-00043',
        )

    def test_number_year_follows_issue_date(self):
        """Ein nacherfasster Beleg bekommt die Jahreszahl seines Belegdatums"""
        last_year = date(self.today.year - 1, 11, 12)

        self._post_create(number='', issue_date=last_year.strftime('%Y-%m-%d'))

        document = SalesDocument.objects.get()
        self.assertTrue(
            document.number.startswith(f'R{last_year.year % 100:02d}-'),
            f'Erwartet Nummer aus {last_year.year}, war: {document.number}',
        )


class DuplicateNumberTestCase(ManualNumberTestBase):
    """Bereits vergebene Nummern werden am Feld abgewiesen"""

    def setUp(self):
        super().setUp()
        self.existing = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R19-00042',
            status='DRAFT',
            issue_date=date(2019, 11, 12),
            subject='Bereits erfasst',
        )

    def test_duplicate_number_is_rejected_with_message(self):
        response = self._post_create(number='R19-00042', subject='Zweiter Versuch')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bereits vergeben')
        self.assertContains(response, 'R19-00042')
        self.assertContains(
            response,
            reverse(
                'auftragsverwaltung:document_detail',
                kwargs={'doc_key': 'invoice', 'pk': self.existing.pk},
            ),
        )

    def test_duplicate_number_does_not_create_document(self):
        self._post_create(number='R19-00042')

        self.assertEqual(SalesDocument.objects.count(), 1)

    def test_duplicate_number_keeps_entered_values(self):
        response = self._post_create(number='R19-00042', subject='Zweiter Versuch')

        self.assertContains(response, 'Zweiter Versuch')

    def test_too_long_number_is_rejected(self):
        """Eine überlange Nummer wird abgewiesen statt in einen DB-Fehler zu laufen"""
        response = self._post_create(number='X' * 40)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'höchstens 32 Zeichen')
        self.assertEqual(SalesDocument.objects.count(), 1)

    def test_same_number_allowed_for_other_document_type(self):
        """Die Eindeutigkeit gilt je Mandant und Dokumenttyp"""
        response = self.client.post(
            reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'quote'}),
            {
                'company_id': self.company.pk,
                'customer_id': self.customer.pk,
                'subject': 'Angebot mit gleicher Nummer',
                'issue_date': self.today.strftime('%Y-%m-%d'),
                'number': 'R19-00042',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SalesDocument.objects.filter(number='R19-00042').count(), 2)


class ManualNumberUpdateTestCase(ManualNumberTestBase):
    """Nachträgliche Korrektur der Nummer"""

    def _document(self, status='DRAFT', number='R19-00042'):
        return SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number=number,
            status=status,
            issue_date=date(2019, 11, 12),
            subject='Nacherfassung',
        )

    def test_draft_number_can_be_corrected(self):
        document = self._document()

        response = self._post_update(document, number='R19-00043')

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.number, 'R19-00043')

    def test_sent_number_is_not_changed(self):
        document = self._document(status='SENT')

        response = self._post_update(document, number='R19-99999')

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.number, 'R19-00042')

    def test_duplicate_on_update_is_rejected(self):
        self._document(number='R19-00043')
        document = self._document()

        response = self._post_update(document, number='R19-00043')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bereits vergeben')
        document.refresh_from_db()
        self.assertEqual(document.number, 'R19-00042')

    def test_unchanged_number_is_accepted(self):
        """Das Absenden der eigenen Nummer ist keine Dublette"""
        document = self._document()

        response = self._post_update(document, subject='Geändert')

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.number, 'R19-00042')
        self.assertEqual(document.subject, 'Geändert')

    def test_number_field_is_readonly_for_sent_document(self):
        document = self._document(status='SENT')

        response = self.client.get(
            reverse(
                'auftragsverwaltung:document_detail',
                kwargs={'doc_key': 'invoice', 'pk': document.pk},
            )
        )

        self.assertNotContains(response, 'name="number"')
        self.assertContains(response, 'readonly')

    def test_number_field_is_editable_for_draft_document(self):
        document = self._document()

        response = self.client.get(
            reverse(
                'auftragsverwaltung:document_detail',
                kwargs={'doc_key': 'invoice', 'pk': document.pk},
            )
        )

        self.assertContains(response, 'name="number"')


class ReserveManualNumberTestCase(ManualNumberTestBase):
    """Direkte Tests des Nummernkreis-Nachziehens"""

    def test_sequence_is_advanced_for_matching_number(self):
        number_range = self._number_range(current_seq=3)

        self.assertTrue(
            reserve_manual_number(self.company, self.doc_type, f'R{self.yy:02d}-00010')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 10)

    def test_sequence_is_never_lowered(self):
        number_range = self._number_range(current_seq=10)

        self.assertFalse(
            reserve_manual_number(self.company, self.doc_type, f'R{self.yy:02d}-00003')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 10)

    def test_other_year_leaves_range_untouched(self):
        number_range = self._number_range(current_seq=5)
        other_year = (self.yy + 1) % 100

        self.assertFalse(
            reserve_manual_number(self.company, self.doc_type, f'R{other_year:02d}-00099')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 5)
        self.assertEqual(number_range.current_year, self.yy)

    def test_number_outside_format_leaves_range_untouched(self):
        number_range = self._number_range(current_seq=5)

        self.assertFalse(
            reserve_manual_number(self.company, self.doc_type, 'ALT-2019/0815')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 5)

    def test_wrong_prefix_leaves_range_untouched(self):
        """Nur das Präfix des eigenen Dokumenttyps zählt"""
        number_range = self._number_range(current_seq=5)

        self.assertFalse(
            reserve_manual_number(self.company, self.doc_type, f'AN{self.yy:02d}-00099')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 5)

    def test_missing_number_range_is_not_created(self):
        self.assertFalse(
            reserve_manual_number(self.company, self.doc_type, f'R{self.yy:02d}-00010')
        )
        self.assertFalse(
            NumberRange.objects.filter(
                company=self.company, target='DOCUMENT', document_type=self.doc_type
            ).exists()
        )

    def test_custom_format_is_honoured(self):
        number_range = self._number_range(current_seq=1, format='{prefix}-{yy}.{seq:04d}')

        self.assertTrue(
            reserve_manual_number(self.company, self.doc_type, f'R-{self.yy:02d}.0077')
        )

        number_range.refresh_from_db()
        self.assertEqual(number_range.current_seq, 77)


class ManualNumberFinalizationTestCase(ManualNumberTestBase):
    """Manuelle Nummer übersteht Finalisierung und DATEV-Export"""

    def setUp(self):
        super().setUp()
        CompanyAccountingSettings.objects.create(
            company=self.company,
            datev_consultant_number='1001',
            datev_client_number='1',
            revenue_account_0='8000',
            revenue_account_7='8300',
            revenue_account_19='8400',
        )
        self.issue_date = date(self.today.year - 1, 11, 12)
        self.invoice = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R19-00042',
            status='DRAFT',
            issue_date=self.issue_date,
            subject='Nacherfasste Altrechnung',
            total_net=Decimal('1000.00'),
            total_tax=Decimal('190.00'),
            total_gross=Decimal('1190.00'),
        )

    def test_finalization_keeps_manual_number(self):
        document, _ = finalize_document(self.invoice)

        self.assertEqual(document.number, 'R19-00042')
        self.assertEqual(document.status, 'SENT')

    def test_journal_entry_carries_manual_number(self):
        finalize_document(self.invoice)

        entry = OutgoingInvoiceJournalEntry.objects.get(document=self.invoice)
        self.assertEqual(entry.document_number, 'R19-00042')
        self.assertEqual(entry.document_date, self.issue_date)

    def test_datev_export_of_previous_year_uses_original_number(self):
        finalize_document(self.invoice)

        preview = datev_export.build_preview(
            self.company,
            date(self.issue_date.year, 1, 1),
            date(self.issue_date.year, 12, 31),
        )

        self.assertEqual(preview.booking_count, 1)
        booking = preview.bookings[0]
        self.assertEqual(booking.document_field_1, 'R19-00042')
        self.assertEqual(booking.document_date, self.issue_date)

"""
Tests für die Admin-Verwaltung des Rechnungsausgangsjournals.

Kernaussage: Löschen ja, Anlegen/Bearbeiten nein – und ein gelöschter Eintrag
lässt sich ohne Dublette neu erzeugen.
"""
from django.contrib import admin as django_admin
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auftragsverwaltung.models import SalesDocument
from finanzen.admin import OutgoingInvoiceJournalEntryAdmin
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services.journal import create_journal_entry

from .test_journal_service import JournalServiceTestBase


class JournalAdminTestBase(JournalServiceTestBase):
    """Journal-Testdaten plus angemeldeter Superuser für das Admin-Backend"""

    def setUp(self):
        super().setUp()
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='geheim-12345',
        )
        self.client.force_login(self.superuser)

    def _create_entry(self, number='R26-00001'):
        """Beleg mit einer 19%-Position finalisieren und Journaleintrag erzeugen"""
        document = self._create_document(number=number)
        self._add_line(document, self.tax_19)
        self._recalculate(document)
        entry, _ = create_journal_entry(document)
        return document, entry

    def _changelist_url(self):
        return reverse('admin:finanzen_outgoinginvoicejournalentry_changelist')

    def _delete_url(self, entry):
        return reverse(
            'admin:finanzen_outgoinginvoicejournalentry_delete', args=[entry.pk]
        )

    @staticmethod
    def _messages(response):
        return [str(message) for message in get_messages(response.wsgi_request)]


class JournalAdminPermissionTest(JournalAdminTestBase):
    """Berechtigungen des OutgoingInvoiceJournalEntryAdmin"""

    def setUp(self):
        super().setUp()
        self.model_admin = OutgoingInvoiceJournalEntryAdmin(
            OutgoingInvoiceJournalEntry, django_admin.site
        )

    def test_delete_permission_granted(self):
        """Löschen ist im Admin erlaubt"""
        request = self.client.get(self._changelist_url()).wsgi_request
        self.assertTrue(self.model_admin.has_delete_permission(request))

    def test_add_permission_denied(self):
        """Anlegen bleibt gesperrt"""
        request = self.client.get(self._changelist_url()).wsgi_request
        self.assertFalse(self.model_admin.has_add_permission(request))

    def test_change_permission_denied(self):
        """Bearbeiten bleibt gesperrt"""
        request = self.client.get(self._changelist_url()).wsgi_request
        self.assertFalse(self.model_admin.has_change_permission(request))

    def test_add_view_forbidden(self):
        """Die Add-View des Admins ist nicht erreichbar"""
        response = self.client.get(
            reverse('admin:finanzen_outgoinginvoicejournalentry_add')
        )
        self.assertEqual(response.status_code, 403)

    def test_change_view_is_readonly_but_offers_delete(self):
        """Die Detailansicht ist lesend, bietet aber den Löschen-Button; POST wird abgelehnt"""
        _, entry = self._create_entry()
        url = reverse(
            'admin:finanzen_outgoinginvoicejournalentry_change', args=[entry.pk]
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self._delete_url(entry))
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_delete_selected_action_available(self):
        """Die Massenaktion zum Löschen steht in der Änderungsliste bereit"""
        self._create_entry()
        response = self.client.get(self._changelist_url())

        self.assertEqual(response.status_code, 200)
        actions = self.model_admin.get_actions(response.wsgi_request)
        self.assertIn('delete_selected', actions)
        self.assertIn('_selected_action', response.content.decode())


class JournalAdminDeleteTest(JournalAdminTestBase):
    """Einzel- und Massenlöschung im Admin"""

    def test_single_delete_removes_entry_and_keeps_document(self):
        """Einzellöschung entfernt den Eintrag, der Beleg bleibt bestehen"""
        document, entry = self._create_entry()

        response = self.client.get(self._delete_url(entry))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(self._delete_url(entry), {'post': 'yes'}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(OutgoingInvoiceJournalEntry.objects.filter(pk=entry.pk).exists())
        self.assertTrue(SalesDocument.objects.filter(pk=document.pk).exists())

        document.refresh_from_db()
        self.assertEqual(document.number, 'R26-00001')
        self.assertEqual(document.status, 'SENT')

    def test_bulk_delete_action_removes_entries(self):
        """Die Massenaktion löscht die ausgewählten Einträge"""
        _, first = self._create_entry(number='R26-00001')
        _, second = self._create_entry(number='R26-00002')

        response = self.client.post(
            self._changelist_url(),
            {
                'action': 'delete_selected',
                '_selected_action': [str(first.pk), str(second.pk)],
                'post': 'yes',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)
        self.assertEqual(SalesDocument.objects.count(), 2)


class JournalAdminExportWarningTest(JournalAdminTestBase):
    """Warnung beim Löschen bereits exportierter Einträge"""

    def _create_exported_entry(self, number='R26-00001', batch_id='BATCH-2026-01'):
        document, entry = self._create_entry(number=number)
        entry.export_status = 'EXPORTED'
        entry.exported_at = timezone.now()
        entry.export_batch_id = batch_id
        entry.save(update_fields=['export_status', 'exported_at', 'export_batch_id'])
        return document, entry

    def test_single_delete_warns_about_export(self):
        """Einzellöschung eines exportierten Eintrags warnt mit Belegnummer und Batch-ID"""
        _, entry = self._create_exported_entry()

        response = self.client.post(self._delete_url(entry), {'post': 'yes'}, follow=True)
        messages = self._messages(response)

        warning = next((m for m in messages if 'BATCH-2026-01' in m), None)
        self.assertIsNotNone(warning, f'Keine Export-Warnung in {messages}')
        self.assertIn('R26-00001', warning)

        # Die Warnung verhindert das Löschen nicht
        self.assertFalse(OutgoingInvoiceJournalEntry.objects.filter(pk=entry.pk).exists())

    def test_bulk_delete_warns_about_export(self):
        """Die Massenaktion warnt für jeden exportierten Eintrag"""
        self._create_exported_entry(number='R26-00001', batch_id='BATCH-2026-01')
        self._create_exported_entry(number='R26-00002', batch_id='BATCH-2026-02')
        _, open_entry = self._create_entry(number='R26-00003')

        response = self.client.post(
            self._changelist_url(),
            {
                'action': 'delete_selected',
                '_selected_action': [
                    str(pk) for pk in
                    OutgoingInvoiceJournalEntry.objects.values_list('pk', flat=True)
                ],
                'post': 'yes',
            },
            follow=True,
        )

        messages = self._messages(response)
        self.assertTrue(any('R26-00001' in m and 'BATCH-2026-01' in m for m in messages), messages)
        self.assertTrue(any('R26-00002' in m and 'BATCH-2026-02' in m for m in messages), messages)
        # Für den offenen Eintrag gibt es keine Warnung
        self.assertFalse(any('R26-00003' in m for m in messages), messages)

        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

    def test_no_warning_for_open_entry(self):
        """Ein offener Eintrag wird ohne Export-Warnung gelöscht"""
        _, entry = self._create_entry()

        response = self.client.post(self._delete_url(entry), {'post': 'yes'}, follow=True)

        self.assertFalse(any('DATEV-Buchungsstapel' in m for m in self._messages(response)))


class JournalEntryRecreationTest(JournalAdminTestBase):
    """Wiederherstellung nach dem Löschen"""

    def test_entry_can_be_recreated_without_duplicate(self):
        """Nach dem Löschen erzeugt create_journal_entry() den Eintrag ohne Dublette neu"""
        document, entry = self._create_entry()
        original_gross = entry.gross_amount

        self.client.post(self._delete_url(entry), {'post': 'yes'}, follow=True)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

        document.refresh_from_db()
        recreated, created = create_journal_entry(document)

        self.assertTrue(created)
        self.assertEqual(recreated.document_number, 'R26-00001')
        self.assertEqual(recreated.gross_amount, original_gross)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)

        # Erneuter Aufruf legt keine zweite Buchung an (Idempotenz)
        again, created_again = create_journal_entry(document)
        self.assertFalse(created_again)
        self.assertEqual(again.pk, recreated.pk)
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 1)

    def test_backfill_command_recreates_entry(self):
        """Das Backfill-Command trägt den gelöschten Eintrag wieder nach"""
        from io import StringIO
        from django.core.management import call_command

        document, entry = self._create_entry()
        self.client.post(self._delete_url(entry), {'post': 'yes'}, follow=True)

        # Trockenlauf zeigt den fehlenden Eintrag an, schreibt aber nichts
        out = StringIO()
        call_command('backfill_journal_entries', '--dry-run', stdout=out)
        self.assertIn('R26-00001', out.getvalue())
        self.assertEqual(OutgoingInvoiceJournalEntry.objects.count(), 0)

        out = StringIO()
        call_command('backfill_journal_entries', stdout=out)
        self.assertEqual(
            OutgoingInvoiceJournalEntry.objects.filter(document=document).count(), 1
        )

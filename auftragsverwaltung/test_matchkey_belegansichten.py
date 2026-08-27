"""
Tests für den Matchkey in den Belegübersichten und im Rechnungs-PDF (#1171).

Deckt ab:
- Spalte „Kunde" in Angeboten/Aufträgen/Rechnungen, Verträgen und Zeiterfassung
  zeigt den Matchkey (inkl. Firma) und bleibt sortierbar.
- Volltextsuche findet Kunden über Firma und über Personennamen.
- Die postalische Anschrift im PDF-Kontext bleibt unverändert.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.filters import (
    ContractFilter,
    SalesDocumentFilter,
    TimeEntryFilter,
)
from auftragsverwaltung.models import (
    Contract,
    DocumentType,
    NumberRange,
    SalesDocument,
    TimeEntry,
)
from auftragsverwaltung.printing.context import SalesDocumentInvoiceContextBuilder
from auftragsverwaltung.tables import ContractTable, SalesDocumentTable, TimeEntryTable
from core.models import Adresse, Mandant


ADDRESS_DEFAULTS = {
    'strasse': 'Musterstraße 1',
    'plz': '12345',
    'ort': 'Musterstadt',
    'land': 'Deutschland',
}


class MatchkeyBelegansichtenTestCase(TestCase):
    """Belegübersichten zeigen und sortieren nach dem Matchkey."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', is_staff=True
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.company = Mandant.objects.create(
            name='Test Company GmbH', adresse='Teststraße 1', plz='12345',
            ort='Teststadt', land='Deutschland'
        )
        self.doc_type_invoice = DocumentType.objects.get(key='invoice')
        self.doc_type_order = DocumentType.objects.get(key='order')

        # Zwei Kunden mit identischem Personennamen, verschiedener Firma
        self.alpha = Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )
        self.beta = Adresse.objects.create(
            adressen_type='KUNDE', firma='Beta GmbH', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )
        self.privat = Adresse.objects.create(
            adressen_type='KUNDE', name='Erika Einzel', **ADDRESS_DEFAULTS
        )

        self.invoice_beta = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type_invoice,
            customer=self.beta, number='R-2024-002', status='OPEN',
            issue_date=date(2024, 1, 2), subject='Rechnung Beta',
            total_gross=Decimal('200.00')
        )
        self.invoice_alpha = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type_invoice,
            customer=self.alpha, number='R-2024-001', status='OPEN',
            issue_date=date(2024, 1, 1), subject='Rechnung Alpha',
            total_gross=Decimal('100.00')
        )

    def test_invoice_list_shows_matchkey_with_firma(self):
        response = self.client.get(
            reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Alpha AG (Max Mustermann)', content)
        self.assertIn('Beta GmbH (Max Mustermann)', content)

    def test_document_table_customer_column_uses_matchkey(self):
        table = SalesDocumentTable(SalesDocument.objects.all())
        self.assertEqual(str(table.columns['customer'].accessor), 'customer.matchkey')

    def test_contract_and_timeentry_tables_use_matchkey(self):
        self.assertEqual(
            str(ContractTable(Contract.objects.none()).columns['customer'].accessor),
            'customer.matchkey',
        )
        self.assertEqual(
            str(TimeEntryTable(TimeEntry.objects.none()).columns['customer'].accessor),
            'customer.matchkey',
        )

    def test_customer_column_is_sortable_by_matchkey(self):
        table = SalesDocumentTable(SalesDocument.objects.all())
        table.order_by = 'customer'
        self.assertEqual(
            [row.record.pk for row in table.rows],
            [self.invoice_alpha.pk, self.invoice_beta.pk],
        )
        table.order_by = '-customer'
        self.assertEqual(
            [row.record.pk for row in table.rows],
            [self.invoice_beta.pk, self.invoice_alpha.pk],
        )

    def test_search_finds_customer_by_firma_and_by_name(self):
        by_firma = SalesDocumentFilter(
            {'q': 'Beta GmbH'}, queryset=SalesDocument.objects.all()
        ).qs
        self.assertEqual(list(by_firma), [self.invoice_beta])

        by_person = SalesDocumentFilter(
            {'q': 'Max Mustermann'}, queryset=SalesDocument.objects.all()
        ).qs
        self.assertEqual(by_person.count(), 2)

    def test_contract_search_finds_customer_by_firma_and_by_name(self):
        NumberRange.objects.create(
            company=self.company, target='CONTRACT', reset_policy='YEARLY',
            format='V{yy}-{seq:05d}',
        )
        contract = Contract.objects.create(
            company=self.company, customer=self.alpha,
            document_type=self.doc_type_invoice, name='Wartungsvertrag',
            interval='MONTHLY', start_date=date(2024, 1, 1),
            next_run_date=date(2024, 2, 1),
        )
        for query in ('Alpha AG', 'Max Mustermann'):
            with self.subTest(query=query):
                qs = ContractFilter({'q': query}, queryset=Contract.objects.all()).qs
                self.assertEqual(list(qs), [contract])

    def test_timeentry_search_finds_customer_by_firma_and_by_name(self):
        order = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type_order,
            customer=self.alpha, number='AB-2024-001', status='DRAFT',
            issue_date=date(2024, 1, 1), subject='Auftrag Alpha',
        )
        entry = TimeEntry.objects.create(
            company=self.company, customer=self.alpha, order=order,
            performed_by=self.user, service_date=date(2024, 1, 5),
            duration_minutes=60, description='Arbeit',
        )
        for query in ('Alpha AG', 'Max Mustermann'):
            with self.subTest(query=query):
                qs = TimeEntryFilter({'q': query}, queryset=TimeEntry.objects.all()).qs
                self.assertEqual(list(qs), [entry])

    def test_timeentry_str_uses_matchkey(self):
        order = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type_order,
            customer=self.alpha, number='AB-2024-002', status='DRAFT',
            issue_date=date(2024, 1, 1), subject='Auftrag Alpha',
        )
        entry = TimeEntry.objects.create(
            company=self.company, customer=self.alpha, order=order,
            performed_by=self.user, service_date=date(2024, 1, 5),
            duration_minutes=90, description='Arbeit',
        )
        self.assertIn('Alpha AG (Max Mustermann)', str(entry))


class MatchkeyAjaxCustomerSearchTestCase(TestCase):
    """Die AJAX-Kundensuche liefert den Matchkey aus."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )

    def test_response_contains_matchkey(self):
        response = self.client.get(
            reverse('auftragsverwaltung:ajax_search_customers'), {'q': 'Alpha'}
        )
        self.assertEqual(response.status_code, 200)
        customers = response.json()['customers']
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]['matchkey'], 'Alpha AG (Max Mustermann)')
        self.assertEqual(customers[0]['full_name'], 'Alpha AG (Max Mustermann)')


class PostalAddressUnchangedTestCase(TestCase):
    """
    Regressionstest: Die postalische Anschrift im PDF-Kontext darf den Matchkey
    NICHT verwenden - Firma und Anrede/Name bleiben getrennte Zeilen.
    """

    def setUp(self):
        self.builder = SalesDocumentInvoiceContextBuilder()

    def test_business_customer_address_block(self):
        customer = Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', anrede='HERR',
            name='Max Mustermann', **ADDRESS_DEFAULTS
        )
        context = self.builder._build_customer_context(customer)
        self.assertEqual(
            context['address_lines'],
            ['Alpha AG', 'Herr Max Mustermann', 'Musterstraße 1', '12345 Musterstadt'],
        )
        self.assertEqual(context['name'], 'Alpha AG')
        for line in context['address_lines']:
            self.assertNotIn('Alpha AG (Max Mustermann)', line)

    def test_private_customer_address_block(self):
        customer = Adresse.objects.create(
            adressen_type='KUNDE', anrede='FRAU', name='Erika Einzel',
            **ADDRESS_DEFAULTS
        )
        context = self.builder._build_customer_context(customer)
        self.assertEqual(
            context['address_lines'],
            ['Frau Erika Einzel', 'Musterstraße 1', '12345 Musterstadt'],
        )
        self.assertEqual(context['name'], 'Erika Einzel')

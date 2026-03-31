from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from auftragsverwaltung.models import (
    SalesDocument,
    SalesDocumentLine,
    DocumentType,
    SalesDocumentSource,
)
from auftragsverwaltung.services import get_next_number, DocumentCalculationService
from core.models import Mandant, Adresse, TaxRate, PaymentTerm


class SalesDocumentCopyTestCase(TestCase):
    def setUp(self):
        self.company = Mandant.objects.create(
            name="Test GmbH",
            adresse="Musterstraße 1",
            plz="12345",
            ort="Berlin",
            land="Deutschland",
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name="Max Mustermann",
            strasse="Kundenweg 5",
            plz="54321",
            ort="Berlin",
            land="Deutschland",
        )
        self.tax_rate = TaxRate.objects.create(
            code="VAT19",
            name="Mehrwertsteuer 19%",
            rate=Decimal("0.19"),
            is_active=True,
        )
        self.payment_term = PaymentTerm.objects.create(
            name="14 Tage netto",
            net_days=14,
            is_default=True,
        )

        self.doc_type_quote, _ = DocumentType.objects.get_or_create(
            key="quote",
            defaults={
                "name": "Angebot",
                "prefix": "AN",
                "is_invoice": False,
                "is_correction": False,
                "requires_due_date": False,
                "is_active": True,
            },
        )
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key="invoice",
            defaults={
                "name": "Rechnung",
                "prefix": "R",
                "is_invoice": True,
                "is_correction": False,
                "requires_due_date": True,
                "is_active": True,
            },
        )

        self.original_issue_date = date(2025, 1, 15)
        self.original_due_date = self.original_issue_date + timedelta(days=14)

        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            customer=self.customer,
            number=get_next_number(self.company, self.doc_type_quote, self.original_issue_date),
            status="SENT",
            issue_date=self.original_issue_date,
            due_date=self.original_due_date,
            payment_term=self.payment_term,
            payment_term_text="Zahlbar innerhalb von 14 Tagen.",
            subject="Testangebot",
            reference_number="REF-123",
            header_text="<p>Header</p>",
            footer_text="<p>Footer</p>",
            notes_internal="Internal",
            notes_public="Public",
        )

        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type="NORMAL",
            is_selected=True,
            tax_rate=self.tax_rate,
            short_text_1="Pos 1",
            short_text_2="Sub 1",
            long_text="<p>Langtext 1</p>",
            description="Beschreibung 1",
            quantity=Decimal("2.00"),
            unit_price_net=Decimal("10.00"),
            is_discountable=True,
            discount=Decimal("5.00"),
            line_net=Decimal("20.00"),
            line_tax=Decimal("3.80"),
            line_gross=Decimal("23.80"),
        )
        SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type="OPTIONAL",
            is_selected=False,
            tax_rate=self.tax_rate,
            short_text_1="Pos 2",
            short_text_2="Sub 2",
            long_text="",
            description="Beschreibung 2",
            quantity=Decimal("1.00"),
            unit_price_net=Decimal("5.00"),
            is_discountable=False,
            discount=Decimal("0.00"),
            line_net=Decimal("5.00"),
            line_tax=Decimal("0.95"),
            line_gross=Decimal("5.95"),
        )

        DocumentCalculationService.recalculate(self.document, persist=True)

    def test_copy_sales_document_same_type(self):
        today = date.today()

        copied = self.document.clone_as(self.doc_type_quote)

        self.assertNotEqual(copied.pk, self.document.pk)
        self.assertEqual(copied.document_type, self.doc_type_quote)
        self.assertEqual(copied.status, "DRAFT")
        self.assertEqual(copied.issue_date, today)
        self.assertEqual(copied.due_date, self.document.due_date)
        self.assertEqual(copied.customer, self.document.customer)
        self.assertEqual(copied.subject, self.document.subject)
        self.assertEqual(copied.reference_number, self.document.reference_number)
        self.assertEqual(copied.header_text, self.document.header_text)
        self.assertEqual(copied.footer_text, self.document.footer_text)
        self.assertEqual(copied.payment_term, self.document.payment_term)
        self.assertEqual(copied.payment_term_text, self.document.payment_term_text)
        self.assertEqual(copied.notes_internal, self.document.notes_internal)
        self.assertEqual(copied.notes_public, self.document.notes_public)
        self.assertNotEqual(copied.number, self.document.number)
        self.assertTrue(copied.number.startswith(self.doc_type_quote.prefix))

        self.assertEqual(copied.lines.count(), self.document.lines.count())
        for original_line, copied_line in zip(
            self.document.lines.order_by("position_no"),
            copied.lines.order_by("position_no"),
        ):
            self.assertEqual(copied_line.position_no, original_line.position_no)
            self.assertEqual(copied_line.line_type, original_line.line_type)
            self.assertEqual(copied_line.is_selected, original_line.is_selected)
            self.assertEqual(copied_line.short_text_1, original_line.short_text_1)
            self.assertEqual(copied_line.short_text_2, original_line.short_text_2)
            self.assertEqual(copied_line.long_text, original_line.long_text)
            self.assertEqual(copied_line.description, original_line.description)
            self.assertEqual(copied_line.quantity, original_line.quantity)
            self.assertEqual(copied_line.unit_price_net, original_line.unit_price_net)
            self.assertEqual(copied_line.discount, original_line.discount)
            self.assertEqual(copied_line.is_discountable, original_line.is_discountable)
            self.assertEqual(copied_line.line_net, original_line.line_net)
            self.assertEqual(copied_line.line_tax, original_line.line_tax)
            self.assertEqual(copied_line.line_gross, original_line.line_gross)
            self.assertEqual(copied_line.tax_rate, original_line.tax_rate)
            self.assertEqual(copied_line.item, original_line.item)
            self.assertEqual(copied_line.unit, original_line.unit)
            self.assertEqual(copied_line.kostenart1, original_line.kostenart1)
            self.assertEqual(copied_line.kostenart2, original_line.kostenart2)

        self.assertEqual(copied.total_net, self.document.total_net)
        self.assertEqual(copied.total_tax, self.document.total_tax)
        self.assertEqual(copied.total_gross, self.document.total_gross)

        self.assertTrue(
            SalesDocumentSource.objects.filter(
                target_document=copied,
                source_document=self.document,
                role="COPIED_FROM",
            ).exists()
        )

    def test_copy_sales_document_to_other_type(self):
        today = date.today()

        copied = self.document.clone_as(self.doc_type_invoice)

        self.assertEqual(copied.document_type, self.doc_type_invoice)
        self.assertEqual(copied.status, "DRAFT")
        self.assertEqual(copied.issue_date, today)
        self.assertTrue(copied.number.startswith(self.doc_type_invoice.prefix))
        self.assertEqual(copied.lines.count(), self.document.lines.count())
        self.assertEqual(copied.customer, self.document.customer)
        self.assertEqual(copied.subject, self.document.subject)
        self.assertEqual(copied.due_date, self.document.due_date)
        self.assertEqual(copied.total_gross, self.document.total_gross)

        self.assertTrue(
            SalesDocumentSource.objects.filter(
                target_document=copied,
                source_document=self.document,
                role="COPIED_FROM",
            ).exists()
        )

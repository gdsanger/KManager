"""
Tests for SalesDocument performance date functionality.

Tests the performance date fields including validation and PDF rendering.
"""

from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, TaxRate, Unit


class PerformanceDateValidationTest(TestCase):
    """Tests for performance date field validation"""

    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland'
        )

        # Create customer
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland'
        )

        # Create document type
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True,
            requires_due_date=True
        )

    def test_performance_date_from_only_is_valid(self):
        """Test that only performance_date_from (single day) is valid"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00001',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date.today(),
            # performance_date_to is None
        )

        # Should not raise ValidationError
        doc.clean()

    def test_performance_date_range_is_valid(self):
        """Test that both performance_date_from and performance_date_to is valid"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00002',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 1),
            performance_date_to=date(2026, 4, 30),
        )

        # Should not raise ValidationError
        doc.clean()

    def test_performance_date_to_without_from_is_invalid(self):
        """Test that performance_date_to without performance_date_from is invalid"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00003',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            # performance_date_from is None
            performance_date_to=date.today(),
        )

        with self.assertRaises(ValidationError) as context:
            doc.clean()

        self.assertIn('performance_date_from', context.exception.error_dict)

    def test_performance_date_to_before_from_is_invalid(self):
        """Test that performance_date_to < performance_date_from is invalid"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00004',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 30),
            performance_date_to=date(2026, 4, 1),  # Before from_date
        )

        with self.assertRaises(ValidationError) as context:
            doc.clean()

        self.assertIn('performance_date_to', context.exception.error_dict)

    def test_performance_date_same_day_is_valid(self):
        """Test that performance_date_to == performance_date_from is valid"""
        doc = SalesDocument(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00005',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 15),
            performance_date_to=date(2026, 4, 15),  # Same day
        )

        # Should not raise ValidationError
        doc.clean()


class PerformanceDatePDFRenderingTest(TestCase):
    """Tests for performance date rendering in PDF/HTML"""

    def setUp(self):
        """Set up test data"""
        # Create company
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
            steuernummer='12/345/67890',
            ust_id_nr='DE123456789'
        )

        # Create customer
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland',
            country_code='DE'
        )

        # Create document type
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True,
            requires_due_date=True
        )

        # Create tax rate and unit
        self.tax_19 = TaxRate.objects.create(code='normal', name='Normal 19%', rate=Decimal('0.19'))
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')

    def test_context_includes_performance_dates(self):
        """Test that context builder includes performance date fields"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00001',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 1),
            performance_date_to=date(2026, 4, 30),
        )

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(doc)

        self.assertIn('doc', context)
        doc_ctx = context['doc']

        self.assertIn('performance_date_from', doc_ctx)
        self.assertIn('performance_date_to', doc_ctx)
        self.assertEqual(doc_ctx['performance_date_from'], date(2026, 4, 1))
        self.assertEqual(doc_ctx['performance_date_to'], date(2026, 4, 30))

    def test_template_renders_performance_period(self):
        """Test that template renders performance period correctly"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00002',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 1),
            performance_date_to=date(2026, 4, 30),
        )

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(doc)

        html = render_to_string('printing/orders/invoice.html', context)

        # Should contain "Leistungszeitraum:" label for period
        self.assertIn('Leistungszeitraum:', html)
        # Should contain both dates formatted
        self.assertIn('01.04.2026', html)
        self.assertIn('30.04.2026', html)

    def test_template_renders_performance_single_day(self):
        """Test that template renders single performance day correctly"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00003',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 15),
            # performance_date_to is None
        )

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(doc)

        html = render_to_string('printing/orders/invoice.html', context)

        # Should contain "Leistungsdatum:" label for single day
        self.assertIn('Leistungsdatum:', html)
        # Should contain only one date
        self.assertIn('15.04.2026', html)

    def test_template_without_performance_date(self):
        """Test that template renders correctly when no performance date is set"""
        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00004',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            # No performance dates
        )

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(doc)

        html = render_to_string('printing/orders/invoice.html', context)

        # Should not contain performance date labels when not set
        self.assertNotIn('Leistungszeitraum:', html)
        self.assertNotIn('Leistungsdatum:', html)

    def test_template_position_below_customer_number(self):
        """Test that performance date appears below customer number in template"""
        # Set customer number
        self.customer.debitor_number = '12345'
        self.customer.save()

        doc = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-00005',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            performance_date_from=date(2026, 4, 1),
            performance_date_to=date(2026, 4, 30),
        )

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(doc)

        html = render_to_string('printing/orders/invoice.html', context)

        # Both should be present
        self.assertIn('Kunden-Nr.:', html)
        self.assertIn('Leistungszeitraum:', html)

        # Performance date should appear after customer number
        customer_number_pos = html.find('Kunden-Nr.:')
        performance_date_pos = html.find('Leistungszeitraum:')

        self.assertGreater(performance_date_pos, customer_number_pos,
                          "Performance date should appear after customer number")

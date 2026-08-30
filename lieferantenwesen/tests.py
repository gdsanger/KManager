"""
Tests for the Lieferantenwesen module.

Tests cover:
- InvoiceIn model and workflow
- InvoiceInLine auto-calculation
- View access control
- Approval workflow
- Supplier (Adresse with LIEFERANT type) matching
"""
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Adresse, Kostenart
from lieferantenwesen.forms import InvoiceInForm
from lieferantenwesen.models import INVOICE_IN_STATUS, InvoiceIn, InvoiceInLine


class InvoiceInModelTest(TestCase):
    def setUp(self):
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Test Lieferant GmbH",
            strasse="Teststr. 1",
            plz="12345",
            ort="Teststadt",
            land="DE",
        )

    def _make_invoice(self, **kwargs):
        defaults = dict(
            invoice_no="RE-001",
            invoice_date=date(2026, 1, 15),
            supplier=self.supplier,
        )
        defaults.update(kwargs)
        return InvoiceIn.objects.create(**defaults)

    def test_default_status_is_draft(self):
        inv = self._make_invoice()
        self.assertEqual(inv.status, "DRAFT")

    def test_str_representation(self):
        inv = self._make_invoice()
        self.assertIn("RE-001", str(inv))
        self.assertIn("Test Lieferant GmbH", str(inv))

    def test_status_display_class(self):
        inv = self._make_invoice(status="APPROVED")
        self.assertEqual(inv.get_status_display_class(), "success")
        inv.status = "REJECTED"
        self.assertEqual(inv.get_status_display_class(), "danger")
        inv.status = "IN_REVIEW"
        self.assertEqual(inv.get_status_display_class(), "warning")

    def test_workflow_status_choices(self):
        status_values = [s[0] for s in INVOICE_IN_STATUS]
        self.assertIn("DRAFT", status_values)
        self.assertIn("EXTRACTED", status_values)
        self.assertIn("IN_REVIEW", status_values)
        self.assertIn("APPROVED", status_values)
        self.assertIn("REJECTED", status_values)

    def test_supplier_must_be_lieferant_type(self):
        """Test that only Adresse with LIEFERANT type can be assigned as supplier."""
        # Create a non-LIEFERANT Adresse
        kunde = Adresse.objects.create(
            adressen_type="KUNDE",
            name="Test Kunde GmbH",
            strasse="Kundenstr. 1",
            plz="54321",
            ort="Kundenstadt",
            land="DE",
        )
        # Try to create invoice with KUNDE type
        inv = InvoiceIn(
            invoice_no="RE-002",
            invoice_date=date(2026, 1, 20),
            supplier=kunde,
        )
        # Should raise ValidationError when clean() is called
        with self.assertRaises(ValidationError) as ctx:
            inv.clean()
        self.assertIn("supplier", ctx.exception.message_dict)


class InvoiceInLineTest(TestCase):
    def setUp(self):
        supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Auto Calc Lieferant",
            strasse="Str. 1",
            plz="11111",
            ort="Stadt",
            land="DE",
        )
        self.invoice = InvoiceIn.objects.create(
            invoice_no="RE-AUTO",
            invoice_date=date(2026, 2, 1),
            supplier=supplier,
        )

    def test_auto_calc_tax_and_gross(self):
        line = InvoiceInLine.objects.create(
            invoice=self.invoice,
            position_no=1,
            description="Test Position",
            net_amount=Decimal("100.00"),
            tax_rate=Decimal("19.00"),
        )
        self.assertEqual(line.tax_amount, Decimal("19.00"))
        self.assertEqual(line.gross_amount, Decimal("119.00"))

    def test_auto_calc_zero_vat(self):
        line = InvoiceInLine.objects.create(
            invoice=self.invoice,
            position_no=1,
            description="Steuerfreie Leistung",
            net_amount=Decimal("200.00"),
            tax_rate=Decimal("0.00"),
        )
        self.assertEqual(line.tax_amount, Decimal("0.00"))
        self.assertEqual(line.gross_amount, Decimal("200.00"))


class InvoiceViewAccessTest(TestCase):
    """Test that unauthenticated users are redirected and authenticated users can access views."""

    def setUp(self):
        self.client = Client()
        # Create a staff user for access
        self.user = User.objects.create_user(
            username="testuser", password="testpass", is_staff=True
        )
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="View Test Lieferant",
            strasse="Viewstr. 1",
            plz="22222",
            ort="Viewstadt",
            land="DE",
        )

    def test_invoice_list_requires_login(self):
        url = reverse("lieferantenwesen:invoice_list")
        response = self.client.get(url)
        self.assertRedirects(response, f"/login/?next={url}", fetch_redirect_response=False)

    def test_invoice_list_accessible_for_staff(self):
        self.client.login(username="testuser", password="testpass")
        url = reverse("lieferantenwesen:invoice_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_home_accessible_for_staff(self):
        self.client.login(username="testuser", password="testpass")
        url = reverse("lieferantenwesen:home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_pdf_upload_page_accessible_for_staff(self):
        self.client.login(username="testuser", password="testpass")
        url = reverse("lieferantenwesen:invoice_upload_pdf")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class ApprovalWorkflowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Approval Lieferant",
            strasse="Approvalstr. 1",
            plz="33333",
            ort="Approvalstadt",
            land="DE",
        )
        self.invoice = InvoiceIn.objects.create(
            invoice_no="RE-WF-001",
            invoice_date=date(2026, 2, 15),
            supplier=self.supplier,
            status="IN_REVIEW",
        )

        # Create Geschäftsleitung group and user
        self.gl_group = Group.objects.create(name="Geschäftsleitung")
        self.gl_user = User.objects.create_user(
            username="gl_user", password="glpass", is_staff=True
        )
        self.gl_user.groups.add(self.gl_group)

        # Regular staff user (no GL group)
        self.regular_user = User.objects.create_user(
            username="regular", password="regpass", is_staff=True
        )

    def test_regular_user_cannot_approve(self):
        self.client.login(username="regular", password="regpass")
        url = reverse("lieferantenwesen:invoice_approve", kwargs={"pk": self.invoice.pk})
        response = self.client.post(url, {"action": "APPROVED", "approval_comment": ""})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "IN_REVIEW")  # unchanged

    def test_gl_user_can_approve(self):
        self.client.login(username="gl_user", password="glpass")
        url = reverse("lieferantenwesen:invoice_approve", kwargs={"pk": self.invoice.pk})
        response = self.client.post(
            url, {"action": "APPROVED", "approval_comment": "Alles gut"}
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "APPROVED")
        self.assertIsNotNone(self.invoice.approved_at)
        self.assertEqual(self.invoice.approved_by, self.gl_user)

    def test_gl_user_can_reject(self):
        self.client.login(username="gl_user", password="glpass")
        url = reverse("lieferantenwesen:invoice_approve", kwargs={"pk": self.invoice.pk})
        response = self.client.post(
            url, {"action": "REJECTED", "approval_comment": "Fehler im Beleg"}
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "REJECTED")
        self.assertIsNotNone(self.invoice.rejected_at)
        self.assertEqual(self.invoice.rejected_by, self.gl_user)
        self.assertEqual(self.invoice.approval_comment, "Fehler im Beleg")

    def test_approved_invoice_cannot_be_edited(self):
        self.invoice.status = "APPROVED"
        self.invoice.save()
        self.client.login(username="gl_user", password="glpass")
        url = reverse("lieferantenwesen:invoice_edit", kwargs={"pk": self.invoice.pk})
        response = self.client.get(url)
        # Should redirect with an error message
        self.assertRedirects(
            response,
            reverse("lieferantenwesen:invoice_detail", kwargs={"pk": self.invoice.pk}),
            fetch_redirect_response=False,
        )


class _InvoiceTableParser(HTMLParser):
    """Simple table parser to extract cell text from invoice list HTML."""

    def __init__(self):
        super().__init__()
        self.in_td = False
        self.current_data = []
        self.current_row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []
        if tag == "td":
            self.in_td = True
            self.current_data = []

    def handle_endtag(self, tag):
        if tag == "td":
            self.in_td = False
            cell_text = "".join(self.current_data).strip()
            self.current_row.append(cell_text)
        if tag == "tr" and self.current_row:
            self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_td:
            self.current_data.append(data)


class InvoiceListStatusDisplayTest(TestCase):
    """Ensure list shows approval and payment flags derived from status."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="listuser", password="listpass", is_staff=True
        )
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="List Lieferant",
            strasse="Listenstr. 1",
            plz="77777",
            ort="Liststadt",
            land="DE",
        )

    def _create_invoice(self, invoice_no, status):
        return InvoiceIn.objects.create(
            invoice_no=invoice_no,
            invoice_date=date(2026, 4, 1),
            supplier=self.supplier,
            status=status,
        )

    def _parse_rows(self, response):
        parser = _InvoiceTableParser()
        parser.feed(response.content.decode())
        return parser.rows

    def test_list_shows_approval_and_payment_indicators(self):
        self._create_invoice("APP-001", "APPROVED")
        self._create_invoice("PAID-001", "PAID")
        self._create_invoice("DR-001", "DRAFT")

        self.client.login(username="listuser", password="listpass")
        response = self.client.get(reverse("lieferantenwesen:invoice_list"))
        self.assertEqual(response.status_code, 200)

        rows = self._parse_rows(response)
        row_by_no = {row[0]: row for row in rows}

        # Column order: no, supplier, date, due, gross, approved?, paid?, status, order, actions
        self.assertEqual(row_by_no["APP-001"][5], "Ja")
        self.assertEqual(row_by_no["APP-001"][6], "Nein")
        self.assertEqual(row_by_no["PAID-001"][5], "Nein")
        self.assertEqual(row_by_no["PAID-001"][6], "Ja")
        self.assertEqual(row_by_no["DR-001"][5], "Nein")
        self.assertEqual(row_by_no["DR-001"][6], "Nein")


class SupplierMatchServiceTest(TestCase):
    def setUp(self):
        Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Mustermann GmbH",
            strasse="Musterstr. 1",
            plz="80000",
            ort="München",
            land="DE",
        )

    def test_find_existing_supplier_by_name(self):
        from lieferantenwesen.services import SupplierMatchService

        service = SupplierMatchService()
        adresse, created = service.find_or_create("Mustermann GmbH")
        self.assertFalse(created)
        self.assertEqual(adresse.name, "Mustermann GmbH")
        self.assertEqual(adresse.adressen_type, "LIEFERANT")

    def test_create_new_supplier_when_no_match(self):
        from lieferantenwesen.services import SupplierMatchService

        service = SupplierMatchService()
        adresse, created = service.find_or_create(
            "Völlig Unbekannte AG", city="Berlin"
        )
        self.assertTrue(created)
        self.assertEqual(adresse.name, "Völlig Unbekannte AG")
        self.assertEqual(adresse.ort, "Berlin")
        self.assertEqual(adresse.adressen_type, "LIEFERANT")


class InvoiceExtractionServiceTest(TestCase):
    """Test the InvoiceExtractionService wrapper in lieferantenwesen."""

    def setUp(self):
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Test Extract Lieferant",
            strasse="Extractstr. 1",
            plz="44444",
            ort="Extractstadt",
            land="DE",
        )
        self.invoice = InvoiceIn.objects.create(
            invoice_no="TBD",
            invoice_date=date(2026, 3, 1),
            supplier=self.supplier,
            status="DRAFT",
        )

    def test_extraction_service_calls_correct_method(self):
        """Test that InvoiceExtractionService calls extract_invoice_data (not extract_from_pdf)."""
        from unittest.mock import patch, MagicMock
        from lieferantenwesen.services import InvoiceExtractionService
        from core.services.ai.invoice_extraction import InvoiceDataDTO

        # Mock the core extraction service
        with patch("lieferantenwesen.services.CoreExtractor") as MockExtractor:
            mock_instance = MagicMock()
            MockExtractor.return_value = mock_instance

            # Mock successful extraction
            mock_dto = InvoiceDataDTO(
                belegnummer="RE-2026-001",
                belegdatum="2026-03-01",
                lieferant_name="Test Extract Lieferant",
                nettobetrag="100.00",
            )
            mock_instance.extract_invoice_data.return_value = mock_dto

            # Run extraction
            service = InvoiceExtractionService()
            result = service.extract_and_populate(self.invoice, "/tmp/test.pdf")

            # Verify extract_invoice_data was called (not extract_from_pdf)
            mock_instance.extract_invoice_data.assert_called_once_with("/tmp/test.pdf", user=None)

            # Verify invoice was updated
            self.assertEqual(result.status, "IN_REVIEW")
            self.assertEqual(result.invoice_no, "RE-2026-001")

    def test_extraction_maps_invoice_no_correctly(self):
        """Test that invoice number is mapped to invoice_no field."""
        from unittest.mock import patch, MagicMock
        from lieferantenwesen.services import InvoiceExtractionService
        from core.services.ai.invoice_extraction import InvoiceDataDTO

        with patch("lieferantenwesen.services.CoreExtractor") as MockExtractor:
            mock_instance = MagicMock()
            MockExtractor.return_value = mock_instance

            mock_dto = InvoiceDataDTO(
                belegnummer="INV-2026-999",
                belegdatum="2026-03-15",
                lieferant_name="Test Extract Lieferant",
            )
            mock_instance.extract_invoice_data.return_value = mock_dto

            service = InvoiceExtractionService()
            result = service.extract_and_populate(self.invoice, "/tmp/test.pdf")

            # Both fields should be populated
            self.assertEqual(result.invoice_no, "INV-2026-999")
            self.assertEqual(result.payment_reference, "INV-2026-999")

    def test_extraction_maps_payment_terms_and_due_date(self):
        """Test that payment terms and due date are extracted and mapped."""
        from unittest.mock import patch, MagicMock
        from lieferantenwesen.services import InvoiceExtractionService
        from core.services.ai.invoice_extraction import InvoiceDataDTO

        with patch("lieferantenwesen.services.CoreExtractor") as MockExtractor:
            mock_instance = MagicMock()
            MockExtractor.return_value = mock_instance

            mock_dto = InvoiceDataDTO(
                belegnummer="RE-TERMS-001",
                belegdatum="2026-03-01",
                faelligkeit="2026-04-01",
                zahlungsbedingungen="30 Tage netto",
                lieferant_name="Test Extract Lieferant",
            )
            mock_instance.extract_invoice_data.return_value = mock_dto

            service = InvoiceExtractionService()
            result = service.extract_and_populate(self.invoice, "/tmp/test.pdf")

            self.assertEqual(result.payment_terms_text, "30 Tage netto")
            self.assertEqual(result.due_date, date(2026, 4, 1))

    def test_extraction_service_handles_unavailable_service(self):
        """Test graceful fallback when AI service is not configured."""
        from unittest.mock import patch
        from lieferantenwesen.services import InvoiceExtractionService
        from core.services.base import ServiceNotConfigured

        with patch("lieferantenwesen.services.CoreExtractor") as MockExtractor:
            MockExtractor.return_value.extract_invoice_data.side_effect = ServiceNotConfigured(
                "AI provider not configured"
            )

            service = InvoiceExtractionService()
            result = service.extract_and_populate(self.invoice, "/tmp/test.pdf")

            # Should stay in DRAFT status
            self.assertEqual(result.status, "DRAFT")

    def test_extraction_service_handles_general_exception(self):
        """Test graceful handling of unexpected exceptions."""
        from unittest.mock import patch
        from lieferantenwesen.services import InvoiceExtractionService

        with patch("lieferantenwesen.services.CoreExtractor") as MockExtractor:
            MockExtractor.return_value.extract_invoice_data.side_effect = Exception(
                "Unexpected error"
            )

            service = InvoiceExtractionService()
            result = service.extract_and_populate(self.invoice, "/tmp/test.pdf")

            # Should stay in DRAFT status
            self.assertEqual(result.status, "DRAFT")


class InvoiceDeleteTest(TestCase):
    """Test delete functionality for InvoiceIn."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="deleteuser", password="deletepass", is_staff=True
        )
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Delete Test Lieferant",
            strasse="Deletestr. 1",
            plz="55555",
            ort="Deletestadt",
            land="DE",
        )

    def test_delete_invoice_without_pdf(self):
        """Test deleting an invoice without a PDF file."""
        invoice = InvoiceIn.objects.create(
            invoice_no="DEL-001",
            invoice_date=date(2026, 3, 1),
            supplier=self.supplier,
        )

        self.client.login(username="deleteuser", password="deletepass")
        url = reverse("lieferantenwesen:invoice_delete", kwargs={"pk": invoice.pk})
        response = self.client.post(url)

        # Should redirect to list
        self.assertRedirects(response, reverse("lieferantenwesen:invoice_list"), fetch_redirect_response=False)

        # Invoice should be deleted
        self.assertFalse(InvoiceIn.objects.filter(pk=invoice.pk).exists())

    def test_delete_invoice_with_lines(self):
        """Test that deleting an invoice also deletes its line items (cascade)."""
        invoice = InvoiceIn.objects.create(
            invoice_no="DEL-002",
            invoice_date=date(2026, 3, 1),
            supplier=self.supplier,
        )
        line = InvoiceInLine.objects.create(
            invoice=invoice,
            position_no=1,
            description="Test Line",
            net_amount=Decimal("100.00"),
        )

        self.client.login(username="deleteuser", password="deletepass")
        url = reverse("lieferantenwesen:invoice_delete", kwargs={"pk": invoice.pk})
        response = self.client.post(url)

        # Both invoice and line should be deleted
        self.assertFalse(InvoiceIn.objects.filter(pk=invoice.pk).exists())
        self.assertFalse(InvoiceInLine.objects.filter(pk=line.pk).exists())

    def test_delete_requires_post(self):
        """Test that delete endpoint requires POST method."""
        invoice = InvoiceIn.objects.create(
            invoice_no="DEL-003",
            invoice_date=date(2026, 3, 1),
            supplier=self.supplier,
        )

        self.client.login(username="deleteuser", password="deletepass")
        url = reverse("lieferantenwesen:invoice_delete", kwargs={"pk": invoice.pk})
        response = self.client.get(url)

        # Should return method not allowed
        self.assertEqual(response.status_code, 405)

        # Invoice should still exist
        self.assertTrue(InvoiceIn.objects.filter(pk=invoice.pk).exists())


class LineItemsExtractionTest(TestCase):
    """Test extraction of line items from invoices."""

    def setUp(self):
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Line Test Lieferant",
            strasse="Linestr. 1",
            plz="66666",
            ort="Linestadt",
            land="DE",
        )

    def test_create_lines_from_dto(self):
        """Test that line items are created from DTO."""
        from unittest.mock import MagicMock
        from lieferantenwesen.services import InvoiceInService
        from core.services.ai.invoice_extraction import InvoiceDataDTO

        invoice = InvoiceIn.objects.create(
            invoice_no="LINE-001",
            invoice_date=date(2026, 3, 1),
            supplier=self.supplier,
        )

        dto = InvoiceDataDTO(
            belegnummer="LINE-001",
            positionen=[
                {
                    "position_no": 1,
                    "description": "Test Item 1",
                    "quantity": "2.0",
                    "unit": "Stk",
                    "unit_price": "50.00",
                    "net_amount": "100.00",
                    "tax_rate": "19.00",
                    "tax_amount": "19.00",
                    "gross_amount": "119.00",
                },
                {
                    "position_no": 2,
                    "description": "Test Item 2",
                    "net_amount": "200.00",
                    "tax_rate": "19.00",
                },
            ],
        )

        service = InvoiceInService()
        service._create_lines_from_dto(invoice, dto)

        # Check that lines were created
        lines = invoice.lines.all()
        self.assertEqual(lines.count(), 2)

        line1 = lines.get(position_no=1)
        self.assertEqual(line1.description, "Test Item 1")
        self.assertEqual(line1.quantity, Decimal("2.0"))
        self.assertEqual(line1.unit, "Stk")
        self.assertEqual(line1.net_amount, Decimal("100.00"))

        line2 = lines.get(position_no=2)
        self.assertEqual(line2.description, "Test Item 2")
        self.assertEqual(line2.net_amount, Decimal("200.00"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class InvoicePdfViewTest(TestCase):
    """Test the authenticated inline PDF delivery view (invoice_pdf)."""

    MINIMAL_PDF = b"%PDF-1.4\n%%EOF"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="pdfstaff", password="pdfpass", is_staff=True
        )
        self.outsider = User.objects.create_user(
            username="pdfoutsider", password="pdfpass"
        )
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="PDF Test Lieferant",
            strasse="PDFstr. 1",
            plz="77777",
            ort="PDFstadt",
            land="DE",
        )
        self.invoice_without_pdf = InvoiceIn.objects.create(
            invoice_no="PDF-000",
            invoice_date=date(2026, 4, 1),
            supplier=self.supplier,
        )
        self.invoice_with_pdf = InvoiceIn.objects.create(
            invoice_no="PDF-001",
            invoice_date=date(2026, 4, 1),
            supplier=self.supplier,
            pdf_file=SimpleUploadedFile(
                "test_invoice.pdf", self.MINIMAL_PDF, content_type="application/pdf"
            ),
        )

    def test_pdf_requires_login(self):
        url = reverse("lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_with_pdf.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"/login/?next={url}", fetch_redirect_response=False)

    def test_pdf_requires_lieferantenwesen_access(self):
        self.client.login(username="pdfoutsider", password="pdfpass")
        url = reverse("lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_with_pdf.pk})
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_pdf_streamed_inline_for_authorized_user(self):
        self.client.login(username="pdfstaff", password="pdfpass")
        url = reverse("lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_with_pdf.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertNotIn("attachment", response["Content-Disposition"])

    def test_pdf_sets_sameorigin_frame_header(self):
        self.client.login(username="pdfstaff", password="pdfpass")
        url = reverse("lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_with_pdf.pk})
        response = self.client.get(url)
        self.assertEqual(response.get("X-Frame-Options"), "SAMEORIGIN")

    def test_pdf_404_when_no_file_attached(self):
        self.client.login(username="pdfstaff", password="pdfpass")
        url = reverse("lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_without_pdf.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_detail_page_links_to_pdf_route_not_media_url(self):
        self.client.login(username="pdfstaff", password="pdfpass")
        detail_url = reverse(
            "lieferantenwesen:invoice_detail", kwargs={"pk": self.invoice_with_pdf.pk}
        )
        pdf_url = reverse(
            "lieferantenwesen:invoice_pdf", kwargs={"pk": self.invoice_with_pdf.pk}
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pdf_url)
        self.assertNotContains(response, self.invoice_with_pdf.pdf_file.url)

    def test_detail_page_shows_placeholder_without_pdf(self):
        self.client.login(username="pdfstaff", password="pdfpass")
        detail_url = reverse(
            "lieferantenwesen:invoice_detail", kwargs={"pk": self.invoice_without_pdf.pk}
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kein PDF hinterlegt")
        self.assertNotContains(response, "<iframe")


class InvoiceCostTypeFormTest(TestCase):
    """Cost types (Kostenart 1/2) must survive the create and edit forms."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="costuser", password="costpass", is_staff=True
        )
        self.client.login(username="costuser", password="costpass")
        self.supplier = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Kostenart Lieferant",
            strasse="Kostenstr. 1",
            plz="44444",
            ort="Kostenstadt",
            land="DE",
        )
        self.main_a = Kostenart.objects.create(name="Instandhaltung")
        self.sub_a = Kostenart.objects.create(name="Heizung", parent=self.main_a)
        self.main_b = Kostenart.objects.create(name="Verwaltung")
        self.sub_b = Kostenart.objects.create(name="Porto", parent=self.main_b)
        self.main_without_children = Kostenart.objects.create(name="Sonstiges")

    def _post_data(self, **overrides):
        data = {
            "invoice_no": "RE-KA-001",
            "invoice_date": "2026-03-01",
            "supplier": str(self.supplier.pk),
            "currency": "EUR",
            "net_amount": "100.00",
            "tax_amount": "19.00",
            "gross_amount": "119.00",
            "payment_terms_text": "",
            "due_date": "",
            "payment_reference": "",
            "iban_from_invoice": "",
            "cost_type_main": str(self.main_a.pk),
            "cost_type_sub": str(self.sub_a.pk),
            "order": "",
            "status": "DRAFT",
            "approval_comment": "",
            "payment_date": "",
            "lines-TOTAL_FORMS": "0",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
        }
        data.update(overrides)
        return data

    def _make_invoice(self, **kwargs):
        defaults = dict(
            invoice_no="RE-KA-EDIT",
            invoice_date=date(2026, 3, 5),
            supplier=self.supplier,
            status="DRAFT",
        )
        defaults.update(kwargs)
        return InvoiceIn.objects.create(**defaults)

    # --- Saving -----------------------------------------------------------

    def test_create_saves_cost_types(self):
        response = self.client.post(
            reverse("lieferantenwesen:invoice_create"), self._post_data()
        )
        self.assertEqual(response.status_code, 302)
        invoice = InvoiceIn.objects.get(invoice_no="RE-KA-001")
        self.assertEqual(invoice.cost_type_main, self.main_a)
        self.assertEqual(invoice.cost_type_sub, self.sub_a)

    def test_detail_page_shows_saved_cost_types(self):
        self.client.post(
            reverse("lieferantenwesen:invoice_create"), self._post_data()
        )
        invoice = InvoiceIn.objects.get(invoice_no="RE-KA-001")
        response = self.client.get(
            reverse("lieferantenwesen:invoice_detail", kwargs={"pk": invoice.pk})
        )
        self.assertContains(response, "Instandhaltung")
        self.assertContains(response, "Heizung")

    def test_edit_saves_changed_cost_types(self):
        invoice = self._make_invoice(
            cost_type_main=self.main_a, cost_type_sub=self.sub_a
        )
        response = self.client.post(
            reverse("lieferantenwesen:invoice_edit", kwargs={"pk": invoice.pk}),
            self._post_data(
                invoice_no=invoice.invoice_no,
                cost_type_main=str(self.main_b.pk),
                cost_type_sub=str(self.sub_b.pk),
            ),
        )
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.cost_type_main, self.main_b)
        self.assertEqual(invoice.cost_type_sub, self.sub_b)

    def test_edit_form_renders_payment_date(self):
        invoice = self._make_invoice(payment_date=date(2026, 3, 20))
        response = self.client.get(
            reverse("lieferantenwesen:invoice_edit", kwargs={"pk": invoice.pk})
        )
        self.assertContains(response, 'name="payment_date"')
        self.assertContains(response, "2026-03-20")

    def test_edit_keeps_existing_payment_date(self):
        """A round trip through the rendered form must not clear payment_date."""
        invoice = self._make_invoice(
            status="PAID", payment_date=date(2026, 3, 20)
        )
        form = InvoiceInForm(instance=invoice)
        data = self._post_data(
            invoice_no=invoice.invoice_no,
            status="PAID",
            payment_date=form["payment_date"].value().isoformat(),
            cost_type_main="",
            cost_type_sub="",
        )
        response = self.client.post(
            reverse("lieferantenwesen:invoice_edit", kwargs={"pk": invoice.pk}), data
        )
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_date, date(2026, 3, 20))

    def test_paid_invoice_without_payment_date_shows_visible_error(self):
        invoice = self._make_invoice()
        response = self.client.post(
            reverse("lieferantenwesen:invoice_edit", kwargs={"pk": invoice.pk}),
            self._post_data(
                invoice_no=invoice.invoice_no, status="PAID", payment_date=""
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "muss ein Zahlungsdatum angegeben werden")

    # --- Dependency between Kostenart 1 and Kostenart 2 -------------------

    def test_mismatched_combination_is_rejected_with_visible_error(self):
        response = self.client.post(
            reverse("lieferantenwesen:invoice_create"),
            self._post_data(
                cost_type_main=str(self.main_a.pk),
                cost_type_sub=str(self.sub_b.pk),
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InvoiceIn.objects.filter(invoice_no="RE-KA-001").exists())
        self.assertContains(response, "Die Eingangsrechnung konnte nicht gespeichert werden")
        self.assertContains(
            response, "Die Unterkostenart muss zur gewählten Hauptkostenart gehören."
        )

    def test_sub_queryset_is_empty_without_main_cost_type(self):
        form = InvoiceInForm()
        self.assertEqual(list(form.fields["cost_type_sub"].queryset), [])
        self.assertEqual(
            form.fields["cost_type_sub"].widget.attrs.get("disabled"), "disabled"
        )

    def test_sub_queryset_is_limited_to_children_of_main(self):
        invoice = self._make_invoice(
            cost_type_main=self.main_a, cost_type_sub=self.sub_a
        )
        form = InvoiceInForm(instance=invoice)
        self.assertEqual(list(form.fields["cost_type_sub"].queryset), [self.sub_a])
        self.assertNotIn("disabled", form.fields["cost_type_sub"].widget.attrs)

    def test_sub_selection_accepted_when_main_changed_in_same_request(self):
        """The bound form derives the allowed children from the POST data."""
        invoice = self._make_invoice(
            cost_type_main=self.main_a, cost_type_sub=self.sub_a
        )
        form = InvoiceInForm(
            self._post_data(
                invoice_no=invoice.invoice_no,
                cost_type_main=str(self.main_b.pk),
                cost_type_sub=str(self.sub_b.pk),
            ),
            instance=invoice,
        )
        self.assertTrue(form.is_valid(), form.errors.as_text())

    def test_sub_queryset_ignores_invalid_main_id(self):
        form = InvoiceInForm(self._post_data(cost_type_main="abc", cost_type_sub=""))
        self.assertEqual(list(form.fields["cost_type_sub"].queryset), [])

    # --- Line cost types --------------------------------------------------

    def test_line_cost_types_can_be_saved(self):
        data = self._post_data(
            **{
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-0-position_no": "1",
                "lines-0-description": "Heizungswartung",
                "lines-0-quantity": "1",
                "lines-0-unit": "Stk",
                "lines-0-unit_price": "100.00",
                "lines-0-net_amount": "100.00",
                "lines-0-tax_rate": "19.00",
                "lines-0-cost_type_main_line": str(self.main_b.pk),
                "lines-0-cost_type_sub_line": str(self.sub_b.pk),
            }
        )
        response = self.client.post(
            reverse("lieferantenwesen:invoice_create"), data
        )
        self.assertEqual(response.status_code, 302)
        line = InvoiceInLine.objects.get(invoice__invoice_no="RE-KA-001")
        self.assertEqual(line.cost_type_main_line, self.main_b)
        self.assertEqual(line.cost_type_sub_line, self.sub_b)

    def test_line_with_mismatched_cost_types_is_rejected(self):
        data = self._post_data(
            **{
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-0-position_no": "1",
                "lines-0-description": "Heizungswartung",
                "lines-0-net_amount": "100.00",
                "lines-0-tax_rate": "19.00",
                "lines-0-cost_type_main_line": str(self.main_a.pk),
                "lines-0-cost_type_sub_line": str(self.sub_b.pk),
            }
        )
        response = self.client.post(
            reverse("lieferantenwesen:invoice_create"), data
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InvoiceIn.objects.filter(invoice_no="RE-KA-001").exists())
        self.assertContains(
            response, "Kostenart 2 muss zur gewählten Kostenart 1 der Position gehören."
        )

    def test_form_template_contains_add_line_template_and_script(self):
        response = self.client.get(reverse("lieferantenwesen:invoice_create"))
        self.assertContains(response, 'id="empty-line-template"')
        self.assertContains(response, "id_lines-TOTAL_FORMS")
        self.assertContains(response, "ajax/get-kostenart2-options/")


class Kostenart2AjaxEndpointTest(TestCase):
    """The existing endpoint is reused for the incoming invoice form."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="ajaxuser", password="ajaxpass", is_staff=True
        )
        self.client.login(username="ajaxuser", password="ajaxpass")
        self.main = Kostenart.objects.create(name="Instandhaltung")
        self.sub = Kostenart.objects.create(name="Heizung", parent=self.main)
        self.childless = Kostenart.objects.create(name="Sonstiges")

    def test_returns_children_for_main_cost_type(self):
        response = self.client.get(
            reverse("auftragsverwaltung:ajax_get_kostenart2_options"),
            {"kostenart1_id": self.main.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["kostenarten"],
            [{"id": self.sub.pk, "name": "Heizung"}],
        )

    def test_returns_empty_list_for_main_cost_type_without_children(self):
        response = self.client.get(
            reverse("auftragsverwaltung:ajax_get_kostenart2_options"),
            {"kostenart1_id": self.childless.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kostenarten"], [])

    def test_returns_empty_list_without_parameter(self):
        response = self.client.get(
            reverse("auftragsverwaltung:ajax_get_kostenart2_options")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kostenarten"], [])

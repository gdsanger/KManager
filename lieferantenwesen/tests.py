"""
Tests for the Lieferantenwesen module.

Tests cover:
- InvoiceIn model and workflow
- InvoiceInLine auto-calculation
- View access control
- Approval workflow
- Supplier (Adresse with LIEFERANT type) matching
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Adresse
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

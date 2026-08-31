"""
Zu lange KI-Werte beim PDF-Import einer Eingangsrechnung.

Die Belegerkennung liefert Freitexte in beliebiger Länge. Ohne Kürzung
scheitert das Speichern auf PostgreSQL mit ``value too long for type
character varying(n)`` und der komplette Upload geht verloren.
"""
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Adresse
from core.services.ai.invoice_extraction import InvoiceDataDTO
from vermietung.models import Eingangsrechnung, MietObjekt


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EingangsrechnungPdfFieldLengthTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="pdflen", password="pdflenpass", is_staff=True
        )
        self.client.login(username="pdflen", password="pdflenpass")

        self.lieferant = Adresse.objects.create(
            adressen_type="LIEFERANT",
            name="Längen Lieferant",
            strasse="Langstr. 1",
            plz="12345",
            ort="Langstadt",
            land="DE",
        )
        standort = Adresse.objects.create(
            adressen_type="STANDORT",
            name="Standort Länge",
            strasse="Standortstr. 1",
            plz="54321",
            ort="Standortstadt",
            land="DE",
        )
        self.mietobjekt = MietObjekt.objects.create(
            name="Längengebäude",
            type="GEBAEUDE",
            beschreibung="Test",
            fläche=Decimal("100.00"),
            standort=standort,
            mietpreis=Decimal("1000.00"),
        )

    @staticmethod
    def _too_long(field_name, extra=50):
        return "L" * (
            Eingangsrechnung._meta.get_field(field_name).max_length + extra
        )

    def _upload(self, dto):
        with patch("vermietung.views.InvoiceExtractionService") as MockExtractor:
            mock_instance = MagicMock()
            MockExtractor.return_value = mock_instance
            mock_instance.extract_invoice_data.return_value = dto
            return self.client.post(
                reverse("vermietung:eingangsrechnung_create_from_pdf"),
                {
                    "mietobjekt": self.mietobjekt.pk,
                    "pdf_file": SimpleUploadedFile(
                        "rechnung.pdf",
                        b"%PDF-1.4 fake",
                        content_type="application/pdf",
                    ),
                },
                follow=True,
            )

    def test_overlong_extracted_texts_are_truncated(self):
        belegnummer = self._too_long("belegnummer")
        betreff = self._too_long("betreff")
        referenznummer = self._too_long("referenznummer")

        self._upload(
            InvoiceDataDTO(
                belegnummer=belegnummer,
                belegdatum="2026-05-04",
                faelligkeit="2026-06-03",
                betreff=betreff,
                referenznummer=referenznummer,
            )
        )

        rechnung = Eingangsrechnung.objects.latest("pk")
        for field, original in (
            ("belegnummer", belegnummer),
            ("betreff", betreff),
            ("referenznummer", referenznummer),
        ):
            value = getattr(rechnung, field)
            max_length = Eingangsrechnung._meta.get_field(field).max_length
            self.assertEqual(len(value), max_length)
            self.assertTrue(original.startswith(value))

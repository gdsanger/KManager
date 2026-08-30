"""
Tests für Dokumente an Verkaufsbelegen (Agira #1190).

Abgedeckt werden:
- Anhängen eines Dokuments an einen SalesDocument
- Download des Anhangs
- Löschen im Status DRAFT
- Abgelehntes Löschen nach der Finalisierung (ab SENT)
- Die Regel "genau ein Zielobjekt" mit dem neuen Fremdschlüssel
- Aufräumen der Dateien beim Löschen des Verkaufsbelegs
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Mandant
from vermietung.models import Dokument, MietObjekt, Vertrag

User = get_user_model()

# Minimales, gültiges PDF - reicht für die MIME-Erkennung via python-magic
PDF_CONTENT = (
    b'%PDF-1.4\n'
    b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
    b'2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n'
    b'trailer<</Root 1 0 R>>\n'
    b'%%EOF\n'
)


class SalesDocumentDokumentTestBase(TestCase):
    """Gemeinsames Setup: Mandant, Kunde, Dokumenttyp und Verkaufsbeleg."""

    def setUp(self):
        # Dateien landen in einem temporären Verzeichnis, nicht in data/
        self.documents_root = tempfile.mkdtemp()
        self.settings_override = override_settings(
            VERMIETUNG_DOCUMENTS_ROOT=self.documents_root
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(shutil.rmtree, self.documents_root, True)

        self.user = User.objects.create_user(
            username='belegtester',
            password='testpass123',
            is_staff=True,  # Zugriff auf den Vermietungsbereich
        )

        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
        )

        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland',
        )

        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'is_active': True,
            },
        )

        self.beleg = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number='R26-00001',
            status='DRAFT',
            customer=self.customer,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00'),
        )

        self.client = Client()
        self.client.login(username='belegtester', password='testpass123')

    def upload_url(self, beleg=None):
        return reverse(
            'vermietung:dokument_upload',
            kwargs={'entity_type': 'salesdocument', 'entity_id': (beleg or self.beleg).pk},
        )

    def detail_url(self, beleg=None):
        beleg = beleg or self.beleg
        return reverse(
            'auftragsverwaltung:document_detail',
            kwargs={'doc_key': beleg.document_type.key, 'pk': beleg.pk},
        )

    def upload_pdf(self, filename='original.pdf', beschreibung='Gescannter Originalbeleg'):
        """Lädt ein PDF über die generische Upload-View hoch."""
        return self.client.post(
            self.upload_url(),
            {
                'file': SimpleUploadedFile(filename, PDF_CONTENT, content_type='application/pdf'),
                'beschreibung': beschreibung,
            },
        )


class DokumentSalesDocumentModelTest(SalesDocumentDokumentTestBase):
    """Modellebene: Zuordnung, Validierung und Anzeige."""

    def test_dokument_kann_an_verkaufsbeleg_haengen(self):
        dokument = Dokument.objects.create(
            original_filename='original.pdf',
            storage_path=f'salesdocument/{self.beleg.pk}/original.pdf',
            file_size=len(PDF_CONTENT),
            mime_type='application/pdf',
            salesdocument=self.beleg,
            uploaded_by=self.user,
        )

        self.assertEqual(dokument.get_entity_type(), 'salesdocument')
        self.assertEqual(dokument.get_entity_id(), self.beleg.pk)
        self.assertEqual(dokument.get_entity_display(), 'Verkaufsbeleg: R26-00001')
        self.assertEqual(list(self.beleg.dokumente.all()), [dokument])

    def test_kein_zielobjekt_ist_ungueltig(self):
        dokument = Dokument(
            original_filename='original.pdf',
            storage_path='salesdocument/1/original.pdf',
            file_size=10,
            mime_type='application/pdf',
        )

        with self.assertRaises(ValidationError):
            dokument.full_clean()

    def test_zwei_zielobjekte_sind_ungueltig(self):
        """Die Ein-Ziel-Regel gilt auch für den neuen Fremdschlüssel."""
        standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstraße 1',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland',
        )
        mietobjekt = MietObjekt.objects.create(
            name='Halle 1',
            type='GEBAEUDE',
            beschreibung='Testobjekt',
            standort=standort,
            mietpreis=Decimal('100.00'),
        )
        vertrag = Vertrag.objects.create(
            mietobjekt=mietobjekt,
            mieter=self.customer,
            start=date(2026, 1, 1),
            miete=Decimal('100.00'),
            kaution=Decimal('200.00'),
        )

        dokument = Dokument(
            original_filename='original.pdf',
            storage_path='salesdocument/1/original.pdf',
            file_size=10,
            mime_type='application/pdf',
            salesdocument=self.beleg,
            vertrag=vertrag,
        )

        with self.assertRaises(ValidationError):
            dokument.full_clean()

    def test_loeschen_des_belegs_entfernt_anhang_und_datei(self):
        response = self.upload_pdf()
        self.assertEqual(response.status_code, 302)

        dokument = self.beleg.dokumente.get()
        file_path = Path(dokument.get_absolute_path())
        self.assertTrue(file_path.exists())

        self.beleg.delete()

        self.assertFalse(Dokument.objects.filter(pk=dokument.pk).exists())
        self.assertFalse(file_path.exists())


class DokumentSalesDocumentUploadViewTest(SalesDocumentDokumentTestBase):
    """Upload über die generische Dokument-View."""

    def test_upload_legt_dokument_an_und_leitet_auf_beleg_zurueck(self):
        response = self.upload_pdf()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.detail_url())

        dokument = self.beleg.dokumente.get()
        self.assertEqual(dokument.original_filename, 'original.pdf')
        self.assertEqual(dokument.beschreibung, 'Gescannter Originalbeleg')
        self.assertEqual(dokument.uploaded_by, self.user)
        self.assertEqual(dokument.mime_type, 'application/pdf')
        self.assertTrue(Path(dokument.get_absolute_path()).exists())

    def test_upload_auch_nach_finalisierung_moeglich(self):
        self.beleg.status = 'SENT'
        self.beleg.save(update_fields=['status'])

        response = self.upload_pdf(filename='nachtrag.pdf')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.beleg.dokumente.count(), 1)

    def test_mehrere_dokumente_moeglich(self):
        self.upload_pdf(filename='beleg1.pdf')
        self.upload_pdf(filename='beleg2.pdf')

        self.assertEqual(self.beleg.dokumente.count(), 2)

    def test_unerlaubter_dateityp_wird_abgelehnt(self):
        response = self.client.post(
            self.upload_url(),
            {
                'file': SimpleUploadedFile(
                    'schadcode.exe', b'MZ\x90\x00binary', content_type='application/octet-stream'
                ),
                'beschreibung': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.detail_url())
        self.assertEqual(self.beleg.dokumente.count(), 0)

    def test_zu_grosse_datei_wird_abgelehnt(self):
        oversized = PDF_CONTENT + b'0' * (10 * 1024 * 1024 + 1)

        response = self.client.post(
            self.upload_url(),
            {
                'file': SimpleUploadedFile('gross.pdf', oversized, content_type='application/pdf'),
                'beschreibung': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.beleg.dokumente.count(), 0)

    def test_upload_fuer_unbekannten_beleg_ergibt_404(self):
        response = self.client.post(
            reverse(
                'vermietung:dokument_upload',
                kwargs={'entity_type': 'salesdocument', 'entity_id': 999999},
            ),
            {'file': SimpleUploadedFile('x.pdf', PDF_CONTENT, content_type='application/pdf')},
        )

        self.assertEqual(response.status_code, 404)


class DokumentSalesDocumentDownloadTest(SalesDocumentDokumentTestBase):
    """Download eines Belegsanhangs."""

    def test_download_liefert_datei(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()

        response = self.client.get(
            reverse('vermietung:dokument_download', kwargs={'dokument_id': dokument.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), PDF_CONTENT)
        self.assertIn('original.pdf', response['Content-Disposition'])


class DokumentSalesDocumentDeleteTest(SalesDocumentDokumentTestBase):
    """Löschregeln abhängig vom Belegstatus."""

    def _delete(self, dokument):
        return self.client.post(
            reverse('vermietung:dokument_delete', kwargs={'dokument_id': dokument.pk})
        )

    def test_loeschen_im_entwurf_moeglich(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()
        file_path = Path(dokument.get_absolute_path())

        response = self._delete(dokument)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.detail_url())
        self.assertFalse(Dokument.objects.filter(pk=dokument.pk).exists())
        self.assertFalse(file_path.exists())

    def test_loeschen_nach_finalisierung_wird_abgelehnt(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()

        self.beleg.status = 'SENT'
        self.beleg.save(update_fields=['status'])

        response = self._delete(dokument)

        # Kein Serverfehler, sondern verständliche Ablehnung mit Rücksprung
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.detail_url())
        self.assertTrue(Dokument.objects.filter(pk=dokument.pk).exists())
        self.assertTrue(Path(dokument.get_absolute_path()).exists())

        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(
            any('nicht gelöscht werden' in m for m in messages),
            f'Erwartete Fehlermeldung fehlt: {messages}',
        )

    def test_loeschen_bei_bezahltem_beleg_wird_abgelehnt(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()

        self.beleg.status = 'PAID'
        self.beleg.save(update_fields=['status'])

        self._delete(dokument)

        self.assertTrue(Dokument.objects.filter(pk=dokument.pk).exists())

    def test_admin_loeschen_bleibt_in_jedem_status_moeglich(self):
        """Das Modell selbst kennt keine Statussperre - nur die Belegseite."""
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()
        file_path = Path(dokument.get_absolute_path())

        self.beleg.status = 'PAID'
        self.beleg.save(update_fields=['status'])

        dokument.delete()

        self.assertFalse(Dokument.objects.filter(pk=dokument.pk).exists())
        self.assertFalse(file_path.exists())


class DokumentSalesDocumentDetailViewTest(SalesDocumentDokumentTestBase):
    """Anzeige des Abschnitts "Dokumente" auf der Belegseite."""

    def test_belegseite_zeigt_anhang_mit_download_und_loeschen(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('original.pdf', content)
        self.assertIn('Gescannter Originalbeleg', content)
        self.assertIn(
            reverse('vermietung:dokument_download', kwargs={'dokument_id': dokument.pk}),
            content,
        )
        self.assertIn(f'confirmDeleteDokument({dokument.pk}', content)

    def test_belegseite_ohne_loeschbutton_nach_finalisierung(self):
        self.upload_pdf()
        dokument = self.beleg.dokumente.get()

        self.beleg.status = 'SENT'
        self.beleg.save(update_fields=['status'])

        response = self.client.get(self.detail_url())
        content = response.content.decode()

        self.assertIn('original.pdf', content)
        self.assertNotIn(f'confirmDeleteDokument({dokument.pk}', content)
        self.assertIn('Anhänge bleiben deshalb dauerhaft erhalten', content)

    def test_anlagemodus_zeigt_keinen_dokumentenbereich(self):
        response = self.client.get(
            reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('dokumentUploadModal', response.content.decode())

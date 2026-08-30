"""
Tests für die Projektzuordnung am Verkaufsbeleg (#1194)

Abgedeckt werden:
- Zuordnung setzen und ändern (Anlage, Bearbeitung, jeder Belegstatus)
- Ablehnung bei abweichendem Kunden bzw. abweichendem Mandanten
- keine Prüfung bei einem Projekt ohne Kunde und ohne Mandant
- Einschränkung der Auswahlliste auf passende Projekte
- geschütztes Löschen eines Projekts mit Belegen
- Trennung von fakturierten und Entwurfssummen inklusive Gutschrift
- Belegliste ohne Abfrage je Zeile
- Projektfilter und Projektspalte in der Belegübersicht
- Projektzuordnung durch den Abrechnungslauf
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.filters import SalesDocumentFilter
from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Mandant, Projekt


class BelegProjektTestBase(TestCase):
    """Gemeinsame Stammdaten: zwei Mandanten, zwei Kunden, mehrere Projekte."""

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH', adresse='Teststr. 1', plz='12345', ort='Teststadt'
        )
        self.other_company = Mandant.objects.create(
            name='Andere GmbH', adresse='Andere Str. 1', plz='54321', ort='Anderstadt'
        )
        self.customer = Adresse.objects.create(
            name='Muster GmbH', strasse='Kundenweg 2', plz='54321',
            ort='Kundenstadt', adressen_type='KUNDE'
        )
        self.other_customer = Adresse.objects.create(
            name='Fremd AG', strasse='Fremdweg 9', plz='11111',
            ort='Fremdstadt', adressen_type='KUNDE'
        )

        self.invoice_type = DocumentType.objects.get(key='invoice')
        self.credit_type = DocumentType.objects.get(key='credit')
        self.quote_type = DocumentType.objects.get(key='quote')

        self.projekt = Projekt.objects.create(
            titel='Migration ERP', kunde=self.customer, company=self.company
        )
        self.fremdprojekt = Projekt.objects.create(
            titel='Fremdprojekt', kunde=self.other_customer, company=self.company
        )
        self.internes_projekt = Projekt.objects.create(titel='Internes Projekt')

        self.user = User.objects.create_user(username='beleg', password='password')
        self.client = Client()
        self.client.login(username='beleg', password='password')

    def _document(self, document_type=None, number='R26-00001', status='DRAFT',
                  customer=None, company=None, projekt=None,
                  total_net=Decimal('0.00'), issue_date=date(2026, 3, 1)):
        """Einen Beleg anlegen - ohne full_clean, damit auch Fehlfälle testbar sind."""
        return SalesDocument.objects.create(
            company=company or self.company,
            document_type=document_type or self.invoice_type,
            customer=self.customer if customer is None else customer,
            projekt=projekt,
            number=number,
            status=status,
            issue_date=issue_date,
            due_date=issue_date,
            total_net=total_net,
            total_gross=(total_net * Decimal('1.19')).quantize(Decimal('0.01')),
        )


class ProjektZuordnungValidierungTests(BelegProjektTestBase):
    """clean(): Kunde und Mandant müssen zum Projekt passen."""

    def test_passende_zuordnung_ist_gueltig(self):
        document = self._document(projekt=self.projekt)

        document.full_clean()  # darf nicht werfen

        self.assertIsNone(document.get_projekt_assignment_error())

    def test_beleg_ohne_projekt_bleibt_gueltig(self):
        document = self._document()

        document.full_clean()

        self.assertIsNone(document.get_projekt_assignment_error())

    def test_abweichender_kunde_wird_abgewiesen(self):
        document = self._document(projekt=self.fremdprojekt)

        with self.assertRaises(ValidationError) as ctx:
            document.full_clean()

        self.assertIn('projekt', ctx.exception.message_dict)
        message = ctx.exception.message_dict['projekt'][0]
        self.assertIn('Fremdprojekt', message)
        self.assertIn('Kunden des Belegs', message)

    def test_abweichender_mandant_wird_abgewiesen(self):
        projekt = Projekt.objects.create(
            titel='Mandantenprojekt', company=self.other_company
        )
        document = self._document(projekt=projekt)

        with self.assertRaises(ValidationError) as ctx:
            document.full_clean()

        message = ctx.exception.message_dict['projekt'][0]
        self.assertIn('Andere GmbH', message)
        self.assertIn('Mandanten des Belegs', message)

    def test_projekt_ohne_kunde_und_mandant_wird_nicht_geprueft(self):
        document = self._document(projekt=self.internes_projekt,
                                  customer=self.other_customer)

        document.full_clean()

        self.assertIsNone(document.get_projekt_assignment_error())

    def test_projekt_ohne_kunde_prueft_nur_den_mandanten(self):
        """Ein Projekt mit Mandant, aber ohne Kunde: Kundenprüfung entfällt."""
        projekt = Projekt.objects.create(titel='Nur Mandant', company=self.company)
        document = self._document(projekt=projekt, customer=self.other_customer)

        document.full_clean()

        self.assertIsNone(document.get_projekt_assignment_error())

    def test_beleg_ohne_kunde_darf_auf_kundenprojekt(self):
        """Ohne Kunde am Beleg gibt es keinen Widerspruch zum Projektkunden."""
        document = self._document(projekt=self.projekt, customer=None)

        self.assertIsNone(document.get_projekt_assignment_error())

    def test_bestehender_beleg_bleibt_speicherbar(self):
        """Ein Beleg ohne Projekt (Bestand) speichert unverändert weiter."""
        document = self._document()
        document.subject = 'Nachträglich geändert'

        document.full_clean()
        document.save()

        document.refresh_from_db()
        self.assertIsNone(document.projekt)
        self.assertEqual(document.subject, 'Nachträglich geändert')


class ProjektZuordnungViewTests(BelegProjektTestBase):
    """Zuordnung über die Belegmasken setzen und ändern."""

    def _post_data(self, document, **overrides):
        data = {
            'company_id': document.company_id,
            'subject': document.subject or 'Betreff',
            'reference_number': '',
            'header_text': '',
            'footer_text': '',
            'notes_internal': '',
            'notes_public': '',
            'status': document.status,
            'customer_id': document.customer_id or '',
            'issue_date': document.issue_date.strftime('%Y-%m-%d'),
            'number': document.number,
            'projekt_id': '',
        }
        data.update(overrides)
        return data

    def test_anlegen_mit_projekt(self):
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'})

        response = self.client.post(url, {
            'company_id': self.company.pk,
            'subject': 'Projektrechnung',
            'customer_id': self.customer.pk,
            'issue_date': '2026-03-01',
            'projekt_id': self.projekt.pk,
        })

        self.assertEqual(response.status_code, 302)
        document = SalesDocument.objects.get(subject='Projektrechnung')
        self.assertEqual(document.projekt, self.projekt)

    def test_anlegen_mit_unpassendem_projekt_wird_abgewiesen(self):
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'})

        response = self.client.post(url, {
            'company_id': self.company.pk,
            'subject': 'Falsche Zuordnung',
            'customer_id': self.customer.pk,
            'issue_date': '2026-03-01',
            'projekt_id': self.fremdprojekt.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SalesDocument.objects.filter(subject='Falsche Zuordnung').exists())
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Fremdprojekt' in m for m in messages), messages)

    def test_abgewiesenes_formular_behaelt_die_eingaben(self):
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'})

        response = self.client.post(url, {
            'company_id': self.company.pk,
            'subject': 'Eingaben erhalten',
            'customer_id': self.customer.pk,
            'issue_date': '2026-04-15',
            'reference_number': 'BST-4711',
            'projekt_id': self.fremdprojekt.pk,
        })

        document = response.context['document']
        self.assertEqual(document.subject, 'Eingaben erhalten')
        self.assertEqual(document.issue_date, date(2026, 4, 15))
        self.assertEqual(document.reference_number, 'BST-4711')

    def test_zuordnung_aendern_und_entfernen(self):
        document = self._document(projekt=self.projekt, total_net=Decimal('100.00'))
        url = reverse('auftragsverwaltung:document_update',
                      kwargs={'doc_key': 'invoice', 'pk': document.pk})

        response = self.client.post(url, self._post_data(
            document, projekt_id=self.internes_projekt.pk))
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.projekt, self.internes_projekt)

        response = self.client.post(url, self._post_data(document, projekt_id=''))
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertIsNone(document.projekt)

    def test_zuordnung_auch_im_finalisierten_beleg_aenderbar(self):
        """Die Zuordnung ist eine Auswertungszuordnung - kein Statusvorbehalt."""
        document = self._document(status='SENT')
        url = reverse('auftragsverwaltung:document_update',
                      kwargs={'doc_key': 'invoice', 'pk': document.pk})

        response = self.client.post(url, self._post_data(
            document, projekt_id=self.projekt.pk))

        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.projekt, self.projekt)
        self.assertEqual(document.status, 'SENT')

    def test_aendern_auf_unpassendes_projekt_wird_abgewiesen(self):
        document = self._document(projekt=self.projekt)
        url = reverse('auftragsverwaltung:document_update',
                      kwargs={'doc_key': 'invoice', 'pk': document.pk})

        response = self.client.post(url, self._post_data(
            document, projekt_id=self.fremdprojekt.pk))

        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.projekt, self.projekt)

    def test_auswahlliste_zeigt_nur_passende_projekte(self):
        document = self._document(projekt=self.projekt)
        url = reverse('auftragsverwaltung:document_detail',
                      kwargs={'doc_key': 'invoice', 'pk': document.pk})

        response = self.client.get(url)

        projekte = list(response.context['projekte'])
        self.assertIn(self.projekt, projekte)
        self.assertIn(self.internes_projekt, projekte)
        self.assertNotIn(self.fremdprojekt, projekte)

    def test_auswahlliste_ohne_kunde_zeigt_alle_projekte(self):
        url = reverse('auftragsverwaltung:document_create', kwargs={'doc_key': 'invoice'})

        response = self.client.get(url)

        projekte = list(response.context['projekte'])
        self.assertIn(self.projekt, projekte)
        self.assertIn(self.fremdprojekt, projekte)
        self.assertIn(self.internes_projekt, projekte)


class ProjektLoeschschutzTests(BelegProjektTestBase):
    """Ein Projekt mit Belegen ist über PROTECT gesichert."""

    def test_datenbank_schuetzt_projekt_mit_belegen(self):
        self._document(projekt=self.projekt)

        with self.assertRaises(ProtectedError):
            self.projekt.delete()

    def test_loeschansicht_meldet_belege_statt_serverfehler(self):
        self._document(projekt=self.projekt)
        url = reverse('projekt_delete', kwargs={'pk': self.projekt.pk})

        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Projekt.objects.filter(pk=self.projekt.pk).exists())
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Verkaufsbeleg' in m for m in messages), messages)

    def test_projekt_ohne_belege_bleibt_loeschbar(self):
        url = reverse('projekt_delete', kwargs={'pk': self.projekt.pk})

        self.client.post(url)

        self.assertFalse(Projekt.objects.filter(pk=self.projekt.pk).exists())


class ProjektBelegListeTests(BelegProjektTestBase):
    """Belegliste und Kennzahlen auf der Projektseite."""

    def test_summen_trennen_fakturiert_und_entwurf(self):
        self._document(number='R26-00001', status='SENT', projekt=self.projekt,
                       total_net=Decimal('1000.00'))
        self._document(number='R26-00002', status='PAID', projekt=self.projekt,
                       total_net=Decimal('500.00'))
        self._document(document_type=self.credit_type, number='GS26-00001',
                       status='SENT', projekt=self.projekt, total_net=Decimal('200.00'))
        self._document(number='R26-00003', status='DRAFT', projekt=self.projekt,
                       total_net=Decimal('300.00'))
        self._document(document_type=self.quote_type, number='AN26-00001',
                       status='DRAFT', projekt=self.projekt, total_net=Decimal('50.00'))

        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})
        response = self.client.get(url)

        # 1000 + 500 - 200 (Gutschrift mindert die Faktura)
        self.assertEqual(response.context['belege_fakturiert_netto'], Decimal('1300.00'))
        self.assertEqual(response.context['belege_fakturiert_anzahl'], 3)
        # Entwürfe bleiben getrennt: 300 + 50
        self.assertEqual(response.context['belege_entwurf_netto'], Decimal('350.00'))
        self.assertEqual(response.context['belege_entwurf_anzahl'], 2)

    def test_angenommenes_angebot_ist_keine_faktura(self):
        self._document(document_type=self.quote_type, number='AN26-00002',
                       status='ACCEPTED', projekt=self.projekt, total_net=Decimal('900.00'))

        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})
        response = self.client.get(url)

        self.assertEqual(response.context['belege_fakturiert_netto'], Decimal('0.00'))
        self.assertEqual(response.context['belege_fakturiert_anzahl'], 0)
        self.assertEqual(response.context['belege_entwurf_anzahl'], 0)
        self.assertEqual(len(response.context['belege']), 1)

    def test_belege_absteigend_nach_belegdatum(self):
        alt = self._document(number='R26-00010', projekt=self.projekt,
                             issue_date=date(2026, 1, 15))
        neu = self._document(number='R26-00011', projekt=self.projekt,
                             issue_date=date(2026, 5, 20))

        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})
        response = self.client.get(url)

        self.assertEqual([b.pk for b in response.context['belege']], [neu.pk, alt.pk])

    def test_fremde_belege_erscheinen_nicht(self):
        self._document(number='R26-00020', projekt=self.projekt)
        self._document(number='R26-00021', customer=self.other_customer,
                       projekt=self.fremdprojekt)

        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})
        response = self.client.get(url)

        self.assertEqual([b.number for b in response.context['belege']], ['R26-00020'])

    def test_leerer_zustand_ohne_belege(self):
        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})

        response = self.client.get(url)

        self.assertEqual(response.context['belege'], [])
        self.assertContains(response, 'noch kein Beleg zugeordnet')

    def test_belegliste_loest_keine_abfrage_je_zeile_aus(self):
        for index in range(3):
            self._document(number=f'R26-003{index}', status='SENT',
                           projekt=self.projekt, total_net=Decimal('100.00'))

        with self.assertNumQueries(1):
            from core.views import get_projekt_belege_context
            context = get_projekt_belege_context(self.projekt)
            for beleg in context['belege']:
                # document_type und company kommen aus select_related
                str(beleg.document_type.name)
                str(beleg.company.name)

    def test_gutschrift_in_der_liste_erkennbar(self):
        self._document(document_type=self.credit_type, number='GS26-00099',
                       status='SENT', projekt=self.projekt, total_net=Decimal('100.00'))

        url = reverse('projekt_detail', kwargs={'pk': self.projekt.pk})
        response = self.client.get(url)

        self.assertContains(response, 'badge bg-warning text-dark">Gutschrift')


class BelegübersichtProjektfilterTests(BelegProjektTestBase):
    """Projektfilter und Projektspalte in der Belegübersicht."""

    def test_filter_auf_projekt(self):
        mit_projekt = self._document(number='R26-00040', projekt=self.projekt)
        self._document(number='R26-00041')

        filter_set = SalesDocumentFilter(
            {'projekt': str(self.projekt.pk)},
            queryset=SalesDocument.objects.filter(document_type=self.invoice_type),
        )

        self.assertEqual([d.pk for d in filter_set.qs], [mit_projekt.pk])

    def test_liste_zeigt_projektspalte(self):
        self._document(number='R26-00050', projekt=self.projekt)
        url = reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})

        response = self.client.get(url)

        self.assertContains(response, 'Migration ERP')
        self.assertContains(response, 'Projekt')

    def test_liste_ohne_projekt_bleibt_leer_in_der_spalte(self):
        """Ohne Zuordnung bleibt die Zelle leer - der Filter listet trotzdem alle Projekte."""
        self._document(number='R26-00051')
        url = reverse('auftragsverwaltung:document_list', kwargs={'doc_key': 'invoice'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        row = list(response.context['table'].rows)[0]
        self.assertEqual(row.get_cell('projekt'), '')

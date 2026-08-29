"""
Tests für Issue #1177 - Artikelübernahme in Beleg-/Vertragspositionen.

Abgedeckt wird:
- Die Inline-Artikelsuche einer bestehenden Belegposition übernimmt Steuersatz,
  Mengeneinheit, Rabattfähigkeit, Preis, Texte und Kostenarten aus dem Artikel.
- Der Steuersatz kommt dabei immer aus dem TaxDeterminationService (Kunde kann
  den Artikelsatz überschreiben, z.B. Reverse Charge).
- "Position hinzufügen" mit Artikel liefert dasselbe Ergebnis.
- Vertragspositionen nutzen dieselbe Logik.
"""
import json
import re
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.models import (
    Contract, ContractLine, DocumentType, NumberRange, SalesDocument, SalesDocumentLine
)
from core.models import Adresse, Item, Kostenart, Mandant, PaymentTerm, TaxRate, Unit

User = get_user_model()


class ArtikeluebernahmeTestCaseBase(TestCase):
    """Gemeinsame Stammdaten für Beleg- und Vertragstests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789',
        )

        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland',
            country_code='DE',
        )

        # EU-B2B-Kunde mit USt-IdNr. -> Reverse Charge
        self.eu_customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='French Company',
            strasse='Rue de Paris 1',
            plz='75001',
            ort='Paris',
            land='France',
            country_code='FR',
            is_business=True,
            vat_id='FR12345678901',
        )

        self.tax_rate_19 = TaxRate.objects.create(
            code='UST19', name='Umsatzsteuer 19%', rate=Decimal('0.19'), is_active=True
        )
        self.tax_rate_0 = TaxRate.objects.create(
            code='ZERO', name='Ohne Umsatzsteuer', rate=Decimal('0.00'), is_active=True
        )

        self.unit_stk = Unit.objects.create(code='STK', name='Stück', symbol='Stk')
        self.unit_pau = Unit.objects.create(code='PAU', name='Pauschal', symbol='Pau')

        self.kostenart1 = Kostenart.objects.create(name='Erlöse')
        self.kostenart2 = Kostenart.objects.create(
            name='Erlöse Dienstleistung', parent=self.kostenart1
        )

        self.item = Item.objects.create(
            article_no='ART-001',
            short_text_1='Artikel Kurztext 1',
            short_text_2='Artikel Kurztext 2',
            long_text='<p>Artikel Langtext</p>',
            net_price=Decimal('200.00'),
            purchase_price=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
            cost_type_1=self.kostenart1,
            cost_type_2=self.kostenart2,
            unit=self.unit_stk,
            item_type='SERVICE',
            is_discountable=False,
        )

        self.item_without_unit = Item.objects.create(
            article_no='ART-002',
            short_text_1='Artikel ohne Einheit',
            net_price=Decimal('50.00'),
            purchase_price=Decimal('25.00'),
            tax_rate=self.tax_rate_19,
            cost_type_1=self.kostenart1,
            item_type='MATERIAL',
        )

        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto', net_days=14, is_default=False
        )


class DocumentLineArtikeluebernahmeTests(ArtikeluebernahmeTestCaseBase):
    """Übernahme über die Inline-Artikelsuche einer bestehenden Position."""

    def setUp(self):
        super().setUp()

        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={'name': 'Rechnung', 'prefix': 'RE', 'is_invoice': True, 'is_active': True},
        )
        NumberRange.objects.get_or_create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type,
            defaults={'reset_policy': 'YEARLY', 'format': '{prefix}{yy}-{seq:05d}'},
        )

        self.document = self._create_document(self.customer, 'RE-2026-0001')
        self.line = self._create_line(self.document)

    def _create_document(self, customer, number):
        return SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            number=number,
            status='DRAFT',
            customer=customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00'),
        )

    def _create_line(self, document, **overrides):
        """Neu angelegte Position, wie sie 'Position hinzufügen' erzeugt: 0% USt."""
        defaults = dict(
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('0.00'),
            tax_rate=self.tax_rate_0,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('0.00'),
            line_tax=Decimal('0.00'),
            line_gross=Decimal('0.00'),
        )
        defaults.update(overrides)
        return SalesDocumentLine.objects.create(document=document, **defaults)

    def _update_url(self, document, line):
        return reverse(
            'auftragsverwaltung:ajax_update_line',
            kwargs={'doc_key': 'invoice', 'pk': document.pk, 'line_id': line.pk},
        )

    def _post_update(self, document, line, payload):
        return self.client.post(
            self._update_url(document, line),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_item_id_uebernimmt_steuersatz_und_einheit(self):
        """Nur item_id senden -> Server übernimmt alles aus dem Artikel."""
        response = self._post_update(self.document, self.line, {'item_id': self.item.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(json.loads(response.content)['success'])

        self.line.refresh_from_db()
        self.assertEqual(self.line.item, self.item)
        self.assertEqual(self.line.tax_rate, self.tax_rate_19)
        self.assertEqual(self.line.unit, self.unit_stk)
        self.assertEqual(self.line.unit_price_net, Decimal('200.00'))
        self.assertEqual(self.line.short_text_1, 'Artikel Kurztext 1')
        self.assertEqual(self.line.short_text_2, 'Artikel Kurztext 2')
        self.assertIn('Artikel Langtext', self.line.long_text)
        self.assertEqual(self.line.kostenart1, self.kostenart1)
        self.assertEqual(self.line.kostenart2, self.kostenart2)
        self.assertFalse(self.line.is_discountable)

    def test_reverse_charge_kunde_erhaelt_nullsatz_statt_artikelsatz(self):
        """Der Kunde überschreibt den Steuersatz des Artikels."""
        eu_document = self._create_document(self.eu_customer, 'RE-2026-0002')
        eu_line = self._create_line(eu_document)

        response = self._post_update(eu_document, eu_line, {'item_id': self.item.pk})
        self.assertEqual(response.status_code, 200, response.content)

        eu_line.refresh_from_db()
        self.assertEqual(eu_line.tax_rate.rate, Decimal('0.00'))
        self.assertNotEqual(eu_line.tax_rate, self.tax_rate_19)

    def test_antwort_enthaelt_steuersatz_und_einheit_fuer_sofortige_anzeige(self):
        """Die Antwort trägt die Werte, mit denen das JS die Dropdowns nachzieht."""
        response = self._post_update(self.document, self.line, {'item_id': self.item.pk})
        line_data = json.loads(response.content)['line']

        self.assertEqual(line_data['tax_rate_id'], self.tax_rate_19.pk)
        self.assertEqual(line_data['tax_rate_code'], 'UST19')
        self.assertEqual(line_data['unit_id'], self.unit_stk.pk)
        self.assertEqual(line_data['unit_code'], 'STK')
        self.assertEqual(line_data['unit_price_net'], '200.00')
        self.assertEqual(line_data['short_text_1'], 'Artikel Kurztext 1')
        self.assertFalse(line_data['is_discountable'])

    def test_artikel_ohne_einheit_laesst_einheit_der_position_stehen(self):
        line = self._create_line(self.document, position_no=2, unit=self.unit_pau)

        self._post_update(self.document, line, {'item_id': self.item_without_unit.pk})

        line.refresh_from_db()
        self.assertEqual(line.unit, self.unit_pau)

    def test_explizit_gesendete_werte_gewinnen_gegen_den_artikel(self):
        """Wer unit_id/tax_rate_id mitsendet, bekommt genau diese Werte."""
        response = self._post_update(
            self.document,
            self.line,
            {'item_id': self.item.pk, 'unit_id': self.unit_pau.pk, 'tax_rate_id': self.tax_rate_0.pk},
        )
        self.assertEqual(response.status_code, 200, response.content)

        self.line.refresh_from_db()
        self.assertEqual(self.line.unit, self.unit_pau)
        self.assertEqual(self.line.tax_rate, self.tax_rate_0)

    def test_belegsummen_werden_nach_uebernahme_neu_berechnet(self):
        self._post_update(self.document, self.line, {'item_id': self.item.pk})

        self.document.refresh_from_db()
        self.assertEqual(self.document.total_net, Decimal('200.00'))
        self.assertEqual(self.document.total_tax, Decimal('38.00'))
        self.assertEqual(self.document.total_gross, Decimal('238.00'))

    def test_position_hinzufuegen_liefert_dasselbe_ergebnis(self):
        """Gegenprobe: ajax_add_line mit item_id verhält sich identisch."""
        url = reverse(
            'auftragsverwaltung:ajax_add_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk},
        )
        response = self.client.post(
            url,
            data=json.dumps({'item_id': self.item.pk, 'quantity': 1.0, 'line_type': 'NORMAL'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = json.loads(response.content)
        self.assertTrue(payload['success'])

        new_line = SalesDocumentLine.objects.get(pk=payload['line_id'])
        self.assertEqual(new_line.tax_rate, self.tax_rate_19)
        self.assertEqual(new_line.unit, self.unit_stk)
        self.assertEqual(new_line.unit_price_net, Decimal('200.00'))
        self.assertFalse(new_line.is_discountable)
        self.assertEqual(payload['line']['unit_code'], 'STK')

    def test_position_hinzufuegen_respektiert_explizite_einheit(self):
        url = reverse(
            'auftragsverwaltung:ajax_add_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk},
        )
        response = self.client.post(
            url,
            data=json.dumps({
                'item_id': self.item.pk,
                'quantity': 1.0,
                'line_type': 'NORMAL',
                'unit_id': self.unit_pau.pk,
            }),
            content_type='application/json',
        )
        payload = json.loads(response.content)
        new_line = SalesDocumentLine.objects.get(pk=payload['line_id'])
        self.assertEqual(new_line.unit, self.unit_pau)


class ArticleSearchResponseTests(ArtikeluebernahmeTestCaseBase):
    """Die Artikelsuche liefert die Einheit mit aus."""

    def test_suche_liefert_einheit(self):
        response = self.client.get(
            reverse('auftragsverwaltung:ajax_search_articles'), {'q': 'ART-001'}
        )
        self.assertEqual(response.status_code, 200)
        articles = json.loads(response.content)['articles']
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['unit_id'], self.unit_stk.pk)
        self.assertEqual(articles[0]['unit_code'], 'STK')

    def test_suche_liefert_leere_einheit_fuer_artikel_ohne_einheit(self):
        response = self.client.get(
            reverse('auftragsverwaltung:ajax_search_articles'), {'q': 'ART-002'}
        )
        articles = json.loads(response.content)['articles']
        self.assertEqual(len(articles), 1)
        self.assertIsNone(articles[0]['unit_id'])
        self.assertEqual(articles[0]['unit_code'], '')


class ContractLineArtikeluebernahmeTests(ArtikeluebernahmeTestCaseBase):
    """Vertragspositionen nutzen dieselbe Übernahmelogik wie Belegpositionen."""

    def setUp(self):
        super().setUp()
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={'name': 'Rechnung', 'prefix': 'RE', 'is_invoice': True, 'is_active': True},
        )
        NumberRange.objects.get_or_create(
            company=self.company,
            target='CONTRACT',
            document_type=None,
            defaults={'reset_policy': 'YEARLY', 'format': 'V{yy}-{seq:05d}'},
        )

    def _create_contract(self, customer):
        return Contract.objects.create(
            company=self.company,
            customer=customer,
            name='Wartungsvertrag',
            document_type=self.doc_type,
            interval='MONTHLY',
            start_date=date.today(),
            next_run_date=date.today(),
        )

    def _add_line(self, contract, payload):
        return self.client.post(
            reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': contract.pk}),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_vertragsposition_uebernimmt_steuersatz_und_einheit_aus_artikel(self):
        contract = self._create_contract(self.customer)
        response = self._add_line(
            contract,
            {'item_id': self.item.pk, 'quantity': '1', 'short_text_1': 'Artikel Kurztext 1'},
        )
        self.assertEqual(response.status_code, 200, response.content)

        line = ContractLine.objects.get(contract=contract)
        self.assertEqual(line.item, self.item)
        self.assertEqual(line.tax_rate, self.tax_rate_19)
        self.assertEqual(line.unit, self.unit_stk)
        self.assertEqual(line.cost_type_1, self.kostenart1)
        self.assertEqual(line.cost_type_2, self.kostenart2)

    def test_vertragsposition_reverse_charge(self):
        contract = self._create_contract(self.eu_customer)
        response = self._add_line(
            contract,
            {'item_id': self.item.pk, 'quantity': '1', 'short_text_1': 'Artikel Kurztext 1'},
        )
        self.assertEqual(response.status_code, 200, response.content)

        line = ContractLine.objects.get(contract=contract)
        self.assertEqual(line.tax_rate.rate, Decimal('0.00'))

    def test_vertragsposition_respektiert_manuelle_rabattfaehigkeit(self):
        contract = self._create_contract(self.customer)
        self._add_line(
            contract,
            {
                'item_id': self.item.pk,
                'quantity': '1',
                'short_text_1': 'Artikel Kurztext 1',
                'is_discountable': True,
            },
        )

        line = ContractLine.objects.get(contract=contract)
        self.assertTrue(line.is_discountable)

    def test_vertragsposition_uebernimmt_rabattfaehigkeit_aus_artikel(self):
        contract = self._create_contract(self.customer)
        self._add_line(
            contract,
            {'item_id': self.item.pk, 'quantity': '1', 'short_text_1': 'Artikel Kurztext 1'},
        )

        line = ContractLine.objects.get(contract=contract)
        self.assertFalse(line.is_discountable)

    def test_vertragsposition_respektiert_manuellen_steuersatz(self):
        contract = self._create_contract(self.customer)
        self._add_line(
            contract,
            {
                'item_id': self.item.pk,
                'quantity': '1',
                'short_text_1': 'Artikel Kurztext 1',
                'tax_rate_id': self.tax_rate_0.pk,
            },
        )

        line = ContractLine.objects.get(contract=contract)
        self.assertEqual(line.tax_rate, self.tax_rate_0)


class ArtikelUebernahmeFrontendTests(TestCase):
    """
    Der Kern des Bugs war ein Frontend-Aufruf, der die Backend-Logik umging.
    Diese Tests halten die Aufrufform fest.
    """

    def _fill_line_source(self):
        source = get_template('auftragsverwaltung/documents/detail.html').template.source
        match = re.search(
            r'function fillLineFromArticle\(lineId, article\) \{.*?\n    \}', source, re.S
        )
        self.assertIsNotNone(match, 'fillLineFromArticle nicht gefunden')
        return match.group(0)

    def test_fill_line_from_article_sendet_item_id(self):
        self.assertIn('item_id: article.id', self._fill_line_source())

    def test_fill_line_from_article_sendet_keine_vom_server_gesetzten_felder(self):
        """
        unit_price_net/tax_rate_id/short_text_* dürfen nicht mitgesendet werden -
        sonst greifen die `if not provided_...`-Zweige in ajax_update_line nicht.
        """
        body = self._fill_line_source()
        payload = body.split('saveLineFieldsNow(', 1)[1]
        for field in ('unit_price_net:', 'tax_rate_id:', 'short_text_1:', 'unit_id:'):
            self.assertNotIn(field, payload, f'{field} darf nicht mitgesendet werden')

    def test_fill_line_from_article_zieht_antwort_in_die_ui_nach(self):
        self.assertIn('applyLineFromServer(lineId, result.line)', self._fill_line_source())

    def test_apply_line_from_server_setzt_steuersatz_und_einheit(self):
        source = get_template('auftragsverwaltung/documents/detail.html').template.source
        self.assertIn(".line-tax-rate'), line.tax_rate_id", source)
        self.assertIn(".line-unit'), line.unit_id", source)

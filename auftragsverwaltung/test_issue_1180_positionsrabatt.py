"""
Tests für #1180: Positionsrabatt wird verrechnet

Deckt ab:
- Berechnung: Rabattbetrag mindert den Positions-Nettobetrag, USt auf dem
  rabattierten Netto
- Belegsummen inkl. neuem Feld total_discount
- is_discountable-Absicherung (Server + UI)
- Validierung der Rabattwerte (0..100)
- Ausweis in Erfassungsmaske und PDF (nur bei vorhandenem Rabatt)
- Beleg-Kopie und Management-Command
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument, SalesDocumentLine
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from auftragsverwaltung.services import DocumentCalculationService
from core.models import Adresse, Mandant, TaxRate, Unit


class DiscountTestBase(TestCase):
    """Gemeinsame Testdaten für die Rabatt-Tests"""

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
        )
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            country_code='DE',
        )
        self.doc_type = DocumentType.objects.get(key='invoice')
        self.tax_19 = TaxRate.objects.create(code='VAT_19', name='19% USt', rate=Decimal('0.19'))
        self.tax_7 = TaxRate.objects.create(code='VAT_7', name='7% USt', rate=Decimal('0.07'))
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')

        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            # bewusst außerhalb des Nummernkreis-Formats, damit clone_as() eine
            # frische Nummer ziehen kann, ohne auf diese hier zu stoßen
            number='TEST-0001',
            status='DRAFT',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
        )

    def _line(self, position_no=1, quantity='2.0000', unit_price='45.00',
              discount='0.00', is_discountable=True, line_type='NORMAL',
              is_selected=True, tax_rate=None):
        return SalesDocumentLine.objects.create(
            document=self.document,
            position_no=position_no,
            line_type=line_type,
            is_selected=is_selected,
            short_text_1=f'Position {position_no}',
            description=f'Position {position_no}',
            unit=self.unit,
            quantity=Decimal(quantity),
            unit_price_net=Decimal(unit_price),
            discount=Decimal(discount),
            is_discountable=is_discountable,
            tax_rate=tax_rate or self.tax_19,
        )


class LineDiscountCalculationTestCase(DiscountTestBase):
    """Rabatt auf Positionsebene"""

    def test_discount_reduces_line_net(self):
        """2 × 45,00 € mit 50% Rabatt ergibt 45,00 € (Beispiel aus #1180)"""
        line = self._line(discount='50.00')

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_subtotal, Decimal('90.00'))
        self.assertEqual(amounts.line_discount, Decimal('45.00'))
        self.assertEqual(amounts.line_net, Decimal('45.00'))

    def test_tax_is_calculated_on_discounted_net(self):
        """USt wird auf den rabattierten Nettobetrag gerechnet, nicht auf den Bruttowert"""
        line = self._line(discount='50.00')

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_tax, Decimal('8.55'))  # 45,00 × 19%
        self.assertEqual(amounts.line_gross, Decimal('53.55'))

    def test_line_without_discount_is_unchanged(self):
        """Ohne Rabatt bleibt die Berechnung exakt wie bisher"""
        line = self._line(discount='0.00')

        line_net, line_tax, line_gross = DocumentCalculationService.calculate_line_totals(line)

        self.assertEqual(line_net, Decimal('90.00'))
        self.assertEqual(line_tax, Decimal('17.10'))
        self.assertEqual(line_gross, Decimal('107.10'))

    def test_discount_amount_is_rounded_half_up(self):
        """Der Rabattbetrag wird kaufmännisch auf 2 Stellen gerundet"""
        # 1 × 10,05 € - 33,33% = 3,3496... -> 3,35
        line = self._line(quantity='1.0000', unit_price='10.05', discount='33.33')

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_subtotal, Decimal('10.05'))
        self.assertEqual(amounts.line_discount, Decimal('3.35'))
        self.assertEqual(amounts.line_net, Decimal('6.70'))
        # Zwischensumme = Netto + Rabatt bleibt cent-genau
        self.assertEqual(amounts.line_net + amounts.line_discount, amounts.line_subtotal)

    def test_full_discount_results_in_zero(self):
        line = self._line(discount='100.00')

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_net, Decimal('0.00'))
        self.assertEqual(amounts.line_tax, Decimal('0.00'))
        self.assertEqual(amounts.line_gross, Decimal('0.00'))

    def test_non_discountable_line_gets_no_discount(self):
        """Nicht rabattfähige Positionen werden trotz gespeichertem Wert nicht rabattiert"""
        line = self._line(discount='50.00', is_discountable=False)

        amounts = DocumentCalculationService.calculate_line_amounts(line)

        self.assertEqual(amounts.line_discount, Decimal('0.00'))
        self.assertEqual(amounts.line_net, Decimal('90.00'))
        self.assertEqual(line.effective_discount_percent(), Decimal('0.00'))

    def test_out_of_range_legacy_values_are_clamped(self):
        """Altdaten außerhalb 0..100 lassen die Berechnung nicht entgleisen"""
        line = self._line(discount='0.00')

        line.discount = Decimal('-10.00')
        self.assertEqual(DocumentCalculationService.effective_discount_percent(line), Decimal('0.00'))

        line.discount = Decimal('150.00')
        self.assertEqual(DocumentCalculationService.effective_discount_percent(line), Decimal('100.00'))


class DocumentTotalsWithDiscountTestCase(DiscountTestBase):
    """Belegsummen inkl. Gesamtrabatt"""

    def test_totals_match_sum_of_discounted_lines(self):
        self._line(position_no=1, discount='50.00')                       # 90,00 - 45,00
        self._line(position_no=2, quantity='3.0000', unit_price='19.99',
                   discount='10.00', tax_rate=self.tax_7)                 # 59,97 - 6,00

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        lines = list(self.document.lines.order_by('position_no'))
        self.assertEqual(lines[0].line_net, Decimal('45.00'))
        self.assertEqual(lines[1].line_net, Decimal('53.97'))
        self.assertEqual(result.total_net, sum(line.line_net for line in lines))
        self.assertEqual(result.total_tax, sum(line.line_tax for line in lines))
        self.assertEqual(result.total_gross, sum(line.line_gross for line in lines))
        self.assertEqual(result.total_discount, Decimal('51.00'))

    def test_total_discount_is_persisted(self):
        self._line(discount='50.00')

        DocumentCalculationService.recalculate(self.document, persist=True)

        self.document.refresh_from_db()
        self.assertEqual(self.document.total_discount, Decimal('45.00'))
        self.assertEqual(self.document.total_net, Decimal('45.00'))
        self.assertEqual(self.document.total_net_before_discount, Decimal('90.00'))

    def test_total_discount_is_zero_without_discount(self):
        self._line(discount='0.00')

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_discount, Decimal('0.00'))
        self.assertEqual(result.total_net, Decimal('90.00'))

    def test_unselected_optional_line_does_not_add_to_total_discount(self):
        self._line(position_no=1, discount='50.00')
        self._line(position_no=2, discount='50.00', line_type='OPTIONAL', is_selected=False)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_discount, Decimal('45.00'))
        self.assertEqual(result.total_net, Decimal('45.00'))
        # Die nicht gewählte Position wird trotzdem korrekt durchgerechnet
        optional_line = self.document.lines.get(position_no=2)
        self.assertEqual(optional_line.line_net, Decimal('45.00'))

    def test_non_discountable_line_does_not_add_to_total_discount(self):
        self._line(position_no=1, discount='50.00', is_discountable=False)

        result = DocumentCalculationService.recalculate(self.document, persist=True)

        self.assertEqual(result.total_discount, Decimal('0.00'))
        self.assertEqual(result.total_net, Decimal('90.00'))


class DiscountValidationTestCase(DiscountTestBase):
    """Validierung der Rabattwerte auf Modellebene"""

    def test_negative_discount_is_rejected(self):
        line = self._line(discount='0.00')
        line.discount = Decimal('-1.00')

        with self.assertRaises(ValidationError) as ctx:
            line.full_clean()
        self.assertIn('discount', ctx.exception.message_dict)

    def test_discount_above_100_is_rejected(self):
        line = self._line(discount='0.00')
        line.discount = Decimal('101.00')

        with self.assertRaises(ValidationError) as ctx:
            line.full_clean()
        self.assertIn('discount', ctx.exception.message_dict)

    def test_discount_within_range_is_valid(self):
        line = self._line(discount='100.00')

        line.full_clean()  # darf nicht werfen


class DiscountAjaxEndpointTestCase(DiscountTestBase):
    """AJAX-Endpunkte für Positionsanlage und -änderung"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='geheim123')
        self.client = Client()
        self.client.force_login(self.user)
        self.line = self._line(discount='0.00')
        self.update_url = reverse(
            'auftragsverwaltung:ajax_update_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk}
        )
        self.add_url = reverse(
            'auftragsverwaltung:ajax_add_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk}
        )

    def _post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_update_discount_recalculates_line_and_totals(self):
        response = self._post(self.update_url, {'discount': 50})

        self.assertEqual(response.status_code, 200, response.content)
        body = json.loads(response.content)
        self.assertEqual(body['line']['line_net'], '45.00')
        self.assertEqual(body['totals']['total_net'], '45.00')
        self.assertEqual(body['totals']['total_discount'], '45.00')
        self.assertEqual(body['totals']['total_net_before_discount'], '90.00')

        self.line.refresh_from_db()
        self.assertEqual(self.line.line_net, Decimal('45.00'))

    def test_update_discount_above_100_is_rejected(self):
        response = self._post(self.update_url, {'discount': 150})

        self.assertEqual(response.status_code, 400, response.content)
        body = json.loads(response.content)
        self.assertIn('zwischen 0 und 100', body['error'])
        self.line.refresh_from_db()
        self.assertEqual(self.line.discount, Decimal('0.00'))

    def test_update_negative_discount_is_rejected(self):
        response = self._post(self.update_url, {'discount': -5})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('zwischen 0 und 100', json.loads(response.content)['error'])

    def test_update_discount_on_non_discountable_line_is_rejected(self):
        self.line.is_discountable = False
        self.line.save(update_fields=['is_discountable'])

        response = self._post(self.update_url, {'discount': 10})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('nicht rabattfähig', json.loads(response.content)['error'])

    def test_add_line_with_discount_is_calculated(self):
        response = self._post(self.add_url, {
            'short_text_1': 'Rabattierte Position',
            'quantity': '2',
            'unit_price_net': '45,00',
            'tax_rate_id': self.tax_19.pk,
            'discount': '50',
        })

        self.assertEqual(response.status_code, 200, response.content)
        body = json.loads(response.content)
        self.assertEqual(body['line']['line_net'], '45.00')
        self.assertEqual(body['totals']['total_discount'], '45.00')

    def test_add_line_with_invalid_discount_is_rejected(self):
        response = self._post(self.add_url, {
            'short_text_1': 'Position',
            'quantity': '1',
            'unit_price_net': '10,00',
            'tax_rate_id': self.tax_19.pk,
            'discount': '120',
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('zwischen 0 und 100', json.loads(response.content)['error'])

    def test_add_non_discountable_line_with_discount_is_rejected(self):
        response = self._post(self.add_url, {
            'short_text_1': 'Position',
            'quantity': '1',
            'unit_price_net': '10,00',
            'tax_rate_id': self.tax_19.pk,
            'is_discountable': False,
            'discount': '10',
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('nicht rabattfähig', json.loads(response.content)['error'])


class DiscountDetailViewTestCase(DiscountTestBase):
    """Summenbox und Rabattfeld in der Erfassungsmaske"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='geheim123')
        self.client = Client()
        self.client.force_login(self.user)
        self.detail_url = reverse(
            'auftragsverwaltung:document_detail',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk}
        )

    def test_summary_shows_discount_rows_when_discount_exists(self):
        self._line(discount='50.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        content = self.client.get(self.detail_url).content.decode()

        self.assertIn('Zwischensumme', content)
        self.assertIn('abzgl. Rabatt', content)
        self.assertNotIn('id="totalsDiscountRow" hidden', content)

    def test_summary_hides_discount_rows_without_discount(self):
        self._line(discount='0.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        content = self.client.get(self.detail_url).content.decode()

        self.assertIn('id="totalsSubtotalRow" hidden', content)
        self.assertIn('id="totalsDiscountRow" hidden', content)

    def test_discount_input_disabled_for_non_discountable_line(self):
        self._line(discount='0.00', is_discountable=False)

        content = self.client.get(self.detail_url).content.decode()

        self.assertIn('Position ist nicht rabattfähig', content)


class DiscountPrintingTestCase(DiscountTestBase):
    """Druckkontext und PDF-Fußzeile"""

    def _render_invoice(self):
        from django.template.loader import render_to_string
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        return context, render_to_string(builder.get_template_name(self.document), context)

    def test_context_contains_discount_totals(self):
        self._line(discount='50.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        context, _ = self._render_invoice()

        self.assertEqual(context['totals']['discount_total'], Decimal('45.00'))
        self.assertEqual(context['totals']['net_subtotal'], Decimal('90.00'))
        self.assertEqual(context['totals']['net_total'], Decimal('45.00'))
        self.assertEqual(context['lines'][0]['discount_percent'], Decimal('50.00'))
        self.assertEqual(context['lines'][0]['net'], Decimal('45.00'))

    def test_non_discountable_line_prints_no_discount_percentage(self):
        self._line(discount='50.00', is_discountable=False)
        DocumentCalculationService.recalculate(self.document, persist=True)

        context, html = self._render_invoice()

        self.assertEqual(context['lines'][0]['discount_percent'], Decimal('0.00'))
        self.assertNotIn('Rabatt:', html)

    def test_pdf_footer_shows_discount_block(self):
        self._line(discount='50.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        _, html = self._render_invoice()

        self.assertIn('Zwischensumme', html)
        self.assertIn('abzgl. Rabatt', html)
        self.assertIn('Rabatt: 50,00%', html.replace('.', ','))

    def test_pdf_footer_unchanged_without_discount(self):
        self._line(discount='0.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        _, html = self._render_invoice()

        self.assertNotIn('Zwischensumme', html)
        self.assertNotIn('abzgl. Rabatt', html)


class DiscountDocumentCopyTestCase(DiscountTestBase):
    """Beleg-Kopie übernimmt und verrechnet den Rabatt"""

    def test_clone_keeps_discount_and_recalculates(self):
        self._line(discount='50.00')
        DocumentCalculationService.recalculate(self.document, persist=True)

        copy = self.document.clone_as(self.doc_type)

        copied_line = copy.lines.get(position_no=1)
        self.assertEqual(copied_line.discount, Decimal('50.00'))
        self.assertEqual(copied_line.line_net, Decimal('45.00'))
        self.assertEqual(copy.total_net, Decimal('45.00'))
        self.assertEqual(copy.total_discount, Decimal('45.00'))


class RecalculateDocumentTotalsCommandTestCase(DiscountTestBase):
    """Management-Command zum Durchrechnen aller Belege"""

    def test_command_fixes_stale_totals(self):
        line = self._line(discount='50.00')
        # Altstand simulieren: Summen ohne Rabatt
        SalesDocumentLine.objects.filter(pk=line.pk).update(
            line_net=Decimal('90.00'), line_tax=Decimal('17.10'), line_gross=Decimal('107.10')
        )
        SalesDocument.objects.filter(pk=self.document.pk).update(
            total_net=Decimal('90.00'), total_tax=Decimal('17.10'),
            total_gross=Decimal('107.10'), total_discount=Decimal('0.00')
        )

        out = StringIO()
        call_command('recalculate_document_totals', stdout=out)

        self.document.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(line.line_net, Decimal('45.00'))
        self.assertEqual(self.document.total_net, Decimal('45.00'))
        self.assertEqual(self.document.total_discount, Decimal('45.00'))
        self.assertIn('1 mit geänderten Summen', out.getvalue())

    def test_dry_run_does_not_write(self):
        line = self._line(discount='50.00')
        SalesDocument.objects.filter(pk=self.document.pk).update(total_net=Decimal('90.00'))

        out = StringIO()
        call_command('recalculate_document_totals', '--dry-run', stdout=out)

        self.document.refresh_from_db()
        self.assertEqual(self.document.total_net, Decimal('90.00'))
        self.assertIn('nicht gespeichert', out.getvalue())

"""
Regression tests for Issue #721 Sub 1/4: Backend-Haertung Line-Save
(ajax_update_line / ajax_add_line).

Covers the root causes identified in the issue:
1. Overlapping saves of the same line must not lose concurrently written fields
   (no more last-writer-wins from a full-row save() without update_fields).
2. German/empty/invalid decimal input must return HTTP 400, never HTTP 500,
   and must never discard the other fields of the same request.
3. A corrupted/truncated JSON body must not be silently treated as an empty,
   successfully-applied payload.
4. An empty or fully-unrecognized payload must not report success:True.
5. Invalid tax_rate_id/item_id must return a clear 400 instead of a bare
   Http404-as-500, without corrupting the line.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from decimal import Decimal
from datetime import date
import json

from auftragsverwaltung.models import (
    SalesDocument, SalesDocumentLine, DocumentType, NumberRange
)
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class LineSaveHardeningTestCase(TestCase):
    """Shared fixtures for line-save hardening tests"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )
        self.tax_rate = TaxRate.objects.create(
            code='STANDARD',
            name='Standard-Steuersatz',
            rate=Decimal('0.19'),
            is_active=True
        )
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
            is_default=False
        )
        self.doc_type_invoice, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'RE',
                'is_invoice': True,
                'is_active': True
            }
        )
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_invoice,
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}'
        )
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_invoice,
            number='RE-2024-1001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        self.line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Original Kurztext',
            short_text_2='Original Kurztext 2',
            long_text='Original long text',
            description='Test Item',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00')
        )
        self.update_url = reverse(
            'auftragsverwaltung:ajax_update_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk, 'line_id': self.line.pk}
        )
        self.add_url = reverse(
            'auftragsverwaltung:ajax_add_line',
            kwargs={'doc_key': 'invoice', 'pk': self.document.pk}
        )

    def _post_json(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type='application/json')


class OverlappingSaveTestCase(LineSaveHardeningTestCase):
    """Root cause #1: full-row save() without update_fields loses concurrent edits"""

    def test_update_does_not_clobber_field_changed_concurrently(self):
        """
        Simulate another request writing short_text_2 directly to the DB in the
        window between our view reading the line and saving it. With update_fields
        scoped to only the fields this request actually touched, the concurrently
        written field must survive.
        """
        simulated = {'done': False}

        def simulate_concurrent_write(sender, instance, **kwargs):
            if instance.pk == self.line.pk and not simulated['done']:
                SalesDocumentLine.objects.filter(pk=self.line.pk).update(
                    short_text_2='ChangedByConcurrentRequest'
                )
                simulated['done'] = True

        pre_save.connect(simulate_concurrent_write, sender=SalesDocumentLine)
        try:
            response = self._post_json(self.update_url, {'short_text_1': 'Updated By Us'})
        finally:
            pre_save.disconnect(simulate_concurrent_write, sender=SalesDocumentLine)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(json.loads(response.content)['success'])

        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Updated By Us')
        self.assertEqual(
            self.line.short_text_2, 'ChangedByConcurrentRequest',
            "Concurrently written field must not be clobbered by our stale in-memory value"
        )


class DecimalHardeningTestCase(LineSaveHardeningTestCase):
    """Root cause #2: raw Decimal() parsing crashes on German/empty/invalid input"""

    def test_update_german_quantity_and_price_succeeds(self):
        response = self._post_json(self.update_url, {'quantity': '2,500', 'unit_price_net': '49,90'})
        self.assertEqual(response.status_code, 200, response.content)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, Decimal('2.500'))
        self.assertEqual(self.line.unit_price_net, Decimal('49.90'))

    def test_update_invalid_quantity_returns_400_not_500(self):
        response = self._post_json(self.update_url, {'quantity': 'abc', 'short_text_1': 'Should Not Save'})
        self.assertEqual(response.status_code, 400, response.content)
        body = json.loads(response.content)
        self.assertFalse(body.get('success'))
        self.assertIn('Menge', body['error'])

        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Original Kurztext')

    def test_update_invalid_price_returns_400_not_500(self):
        response = self._post_json(self.update_url, {'unit_price_net': ''})
        self.assertEqual(response.status_code, 400, response.content)
        body = json.loads(response.content)
        self.assertFalse(body.get('success'))
        self.assertIn('Stückpreis', body['error'])

    def test_update_invalid_discount_returns_400(self):
        response = self._post_json(self.update_url, {'discount': 'xyz'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Rabatt', json.loads(response.content)['error'])

    def test_add_line_german_decimal_succeeds(self):
        response = self._post_json(self.add_url, {
            'short_text_1': 'Neue Position',
            'quantity': '3,000',
            'unit_price_net': '19,99',
            'tax_rate_id': self.tax_rate.pk,
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        line = SalesDocumentLine.objects.get(pk=data['line_id'])
        self.assertEqual(line.quantity, Decimal('3.000'))
        self.assertEqual(line.unit_price_net, Decimal('19.99'))

    def test_add_line_invalid_quantity_returns_400_not_500(self):
        response = self._post_json(self.add_url, {
            'short_text_1': 'Neue Position',
            'quantity': 'invalid',
            'unit_price_net': '10.00',
            'tax_rate_id': self.tax_rate.pk,
        })
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Menge', json.loads(response.content)['error'])

    def test_add_line_invalid_price_returns_400_not_500(self):
        response = self._post_json(self.add_url, {
            'short_text_1': 'Neue Position',
            'quantity': '1',
            'unit_price_net': 'not-a-number',
            'tax_rate_id': self.tax_rate.pk,
        })
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Stückpreis', json.loads(response.content)['error'])

    def test_add_line_invalid_discount_returns_400(self):
        response = self._post_json(self.add_url, {
            'short_text_1': 'Neue Position',
            'quantity': '1',
            'unit_price_net': '10.00',
            'tax_rate_id': self.tax_rate.pk,
            'discount': 'garbage',
        })
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Rabatt', json.loads(response.content)['error'])


class PayloadHardeningTestCase(LineSaveHardeningTestCase):
    """Root cause #3/#4: corrupted or empty payloads must not report success:True"""

    def test_corrupted_json_body_returns_400_not_silent_success(self):
        response = self.client.post(
            self.update_url,
            data='{"short_text_1": "trunc',  # deliberately broken JSON
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400, response.content)
        body = json.loads(response.content)
        self.assertFalse(body.get('success'))

        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Original Kurztext')

    def test_empty_json_object_returns_400_not_success(self):
        response = self._post_json(self.update_url, {})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(json.loads(response.content).get('success'))

    def test_only_unrecognized_keys_returns_400_not_success(self):
        response = self._post_json(self.update_url, {'not_a_real_field': 'value'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(json.loads(response.content).get('success'))

    def test_empty_add_line_payload_returns_400(self):
        response = self.client.post(self.add_url, data='', content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(json.loads(response.content).get('success'))


class InvalidForeignKeyTestCase(LineSaveHardeningTestCase):
    """Root cause #5: invalid tax_rate_id/item_id must be a clean 400, not Http404-as-500"""

    def test_update_invalid_tax_rate_id_returns_400(self):
        response = self._post_json(self.update_url, {'tax_rate_id': 999999, 'short_text_1': 'Should Not Save'})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Steuersatz', json.loads(response.content)['error'])

        # The whole request is rejected atomically - the valid short_text_1
        # change is not silently applied together with the invalid tax rate.
        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Original Kurztext')

        # Resubmitting without the bad tax_rate_id must succeed.
        response = self._post_json(self.update_url, {'short_text_1': 'Should Save Now'})
        self.assertEqual(response.status_code, 200, response.content)
        self.line.refresh_from_db()
        self.assertEqual(self.line.short_text_1, 'Should Save Now')

    def test_update_invalid_item_id_returns_400(self):
        response = self._post_json(self.update_url, {'item_id': 999999})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Artikel', json.loads(response.content)['error'])

    def test_add_line_invalid_tax_rate_id_returns_400(self):
        response = self._post_json(self.add_url, {
            'short_text_1': 'Neue Position',
            'quantity': '1',
            'unit_price_net': '10.00',
            'tax_rate_id': 999999,
        })
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Steuersatz', json.loads(response.content)['error'])

    def test_add_line_invalid_item_id_returns_400(self):
        response = self._post_json(self.add_url, {'item_id': 999999})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('Artikel', json.loads(response.content)['error'])

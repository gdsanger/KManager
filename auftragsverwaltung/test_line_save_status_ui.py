"""
Regression tests for Issue #721 Sub 3/4: Sichtbarer Speicher-/Dirty-/Fehler-Status
pro Position.

Before this change, a failed line save (non-200, success:false, or a network/
session error) only reached the browser console via console.error - nothing
in the UI told the user their edit was lost, and the beforeunload guard did
not consider a failed save "unsaved". These tests pin the template contract
that closes that gap: every rendered position line ships a status element and
the surrounding page script exposes the retry/dirty-tracking hooks that make
failures visible instead of silent.
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType, NumberRange
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class LineSaveStatusUiTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.company = Mandant.objects.create(
            name='Test Company GmbH', adresse='Teststraße 123', plz='12345',
            ort='Teststadt', land='Deutschland', steuernummer='DE123456789'
        )
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE', name='Test Customer', anrede='Herr',
            strasse='Kundenstraße 1', plz='54321', ort='Kundenstadt', land='Deutschland'
        )
        self.tax_rate = TaxRate.objects.create(
            code='STANDARD', name='Standard-Steuersatz', rate=Decimal('0.19'), is_active=True
        )
        self.payment_term = PaymentTerm.objects.create(name='14 Tage netto', net_days=14, is_default=False)
        self.doc_type, _ = DocumentType.objects.get_or_create(
            key='quote', defaults={'name': 'Angebot', 'prefix': 'AN', 'is_invoice': False, 'is_active': True}
        )
        NumberRange.objects.create(
            company=self.company, target='DOCUMENT', document_type=self.doc_type,
            reset_policy='YEARLY', format='{prefix}{yy}-{seq:05d}'
        )
        self.document = SalesDocument.objects.create(
            company=self.company, document_type=self.doc_type, number='AN-2024-1001',
            status='DRAFT', customer=self.customer, payment_term=self.payment_term,
            issue_date=date.today(), total_net=Decimal('0.00'), total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        self.line = SalesDocumentLine.objects.create(
            document=self.document, position_no=1, line_type='NORMAL', is_selected=True,
            short_text_1='Position', short_text_2='', long_text='Langtext',
            description='Position', quantity=Decimal('1.0000'), unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate, is_discountable=True, discount=Decimal('0.00'),
            line_net=Decimal('100.00'), line_tax=Decimal('19.00'), line_gross=Decimal('119.00')
        )
        self.detail_url = reverse(
            'auftragsverwaltung:document_detail', kwargs={'doc_key': 'quote', 'pk': self.document.pk}
        )

    def test_line_carries_visible_save_status_element(self):
        """Every position line renders a status placeholder the JS can update
        to speichert.../gespeichert/Fehler, instead of only logging errors."""
        content = self.client.get(self.detail_url).content.decode('utf-8')
        self.assertIn(f'class="line-save-status" data-line-id="{self.line.pk}"', content)

    def test_longtext_modal_has_inline_error_area(self):
        """The Quill longtext modal has its own error slot so a failed save
        surfaces without a blocking alert() and without losing the edited text."""
        content = self.client.get(self.detail_url).content.decode('utf-8')
        self.assertIn('id="longtextEditorError"', content)

    def test_script_exposes_retry_and_dirty_tracking_hooks(self):
        """The page script must actually implement: a retry affordance for a
        failed line save, and a dirty-check that still reports pending work
        after a save has failed (not just while a request is in flight)."""
        content = self.client.get(self.detail_url).content.decode('utf-8')
        self.assertIn('retry-line-save-btn', content)
        self.assertIn('function retryLineSave', content)
        self.assertIn('entry.lastFailedPayload', content)
        self.assertIn('function flushAllLineSavesAndCheck', content)

    def test_no_more_silent_console_only_failure_paths(self):
        """The former 'Silent fail - no alert shown' comments/behaviour around
        addNewPosition() must be gone - failures there must be surfaced too."""
        content = self.client.get(self.detail_url).content.decode('utf-8')
        self.assertNotIn('Silent fail', content)

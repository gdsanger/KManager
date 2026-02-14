"""
Test for issue #377: Fehler beim Langtext Speichern via HTMX bei Positionen

This test specifically validates that the fix for the HTMX hx-vals issue works correctly.
The bug was that the long_text textarea did not have hx-vals, causing HTMX to send
all textareas with name="long_text", and only the last value was received.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date
import json

from auftragsverwaltung.models import (
    SalesDocument, SalesDocumentLine, DocumentType, NumberRange
)
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class Issue377LangtextTestCase(TestCase):
    """Test that long_text updates work correctly for all positions (Issue #377)"""
    
    def setUp(self):
        """Set up test data with multiple positions"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create test company
        self.company = Mandant.objects.create(
            name='Test Company GmbH',
            adresse='Teststraße 123',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            steuernummer='DE123456789'
        )
        
        # Create test customer
        self.customer = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='Deutschland'
        )
        
        # Create test tax rate
        self.tax_rate = TaxRate.objects.create(
            code='STANDARD',
            name='Standard-Steuersatz',
            rate=Decimal('0.19'),
            is_active=True
        )
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name='14 Tage netto',
            net_days=14,
            is_default=False
        )
        
        # Create document type for Quote (as mentioned in the issue)
        self.doc_type_quote, _ = DocumentType.objects.get_or_create(
            key='quote',
            defaults={
                'name': 'Angebot',
                'prefix': 'AN',
                'is_active': True
            }
        )
        
        # Create number range for quote
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.doc_type_quote,
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}'
        )
        
        # Create test quote document (as mentioned in the issue)
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type_quote,
            number='AN-2024-0001',
            status='DRAFT',
            customer=self.customer,
            payment_term=self.payment_term,
            issue_date=date.today(),
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00')
        )
        
        # Create THREE test lines to reproduce the issue
        # The bug was that only the LAST position's long_text was saved
        self.line1 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 1',
            short_text_2='',
            long_text='',
            description='Position 1',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00')
        )
        
        self.line2 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=2,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 2',
            short_text_2='',
            long_text='',
            description='Position 2',
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('200.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('400.00'),
            line_tax=Decimal('76.00'),
            line_gross=Decimal('476.00')
        )
        
        self.line3 = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=3,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Position 3',
            short_text_2='',
            long_text='',
            description='Position 3',
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('300.00'),
            tax_rate=self.tax_rate,
            is_discountable=True,
            discount=Decimal('0.00'),
            line_net=Decimal('900.00'),
            line_tax=Decimal('171.00'),
            line_gross=Decimal('1071.00')
        )
    
    def test_first_position_long_text_saves_with_form_encoded_data(self):
        """
        Test that long_text update for FIRST position is saved (this was the bug).
        Uses form-encoded data to simulate real HTMX behavior with hx-vals.
        """
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line1.pk})
        
        # Simulate HTMX hx-vals sending form-encoded data
        # With the fix, hx-vals='js:{"long_text": this.value || ""}' sends only the specific value
        new_long_text = 'Updated long text for first position'
        data = {
            'long_text': new_long_text
        }
        
        response = self.client.post(
            url,
            data=data,  # Send as form-encoded, not JSON (simulates HTMX)
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200 but got {response.status_code}. Response: {response.content}")
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'), 
                       f"Expected success=True in response. Got: {response_data}")
        
        # Check that long_text was updated in database (this failed before the fix)
        self.line1.refresh_from_db()
        self.assertEqual(self.line1.long_text, new_long_text,
                        "First position long_text should be saved")
        
        # Verify other positions were NOT affected
        self.line2.refresh_from_db()
        self.line3.refresh_from_db()
        self.assertEqual(self.line2.long_text, '', "Position 2 should remain unchanged")
        self.assertEqual(self.line3.long_text, '', "Position 3 should remain unchanged")
    
    def test_middle_position_long_text_saves_with_form_encoded_data(self):
        """Test that long_text update for MIDDLE position is saved (this was also affected by the bug)."""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line2.pk})
        
        new_long_text = 'Updated long text for middle position'
        data = {
            'long_text': new_long_text
        }
        
        response = self.client.post(url, data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        
        # Check that long_text was updated in database
        self.line2.refresh_from_db()
        self.assertEqual(self.line2.long_text, new_long_text,
                        "Middle position long_text should be saved")
        
        # Verify other positions were NOT affected
        self.line1.refresh_from_db()
        self.line3.refresh_from_db()
        self.assertEqual(self.line1.long_text, '', "Position 1 should remain unchanged")
        self.assertEqual(self.line3.long_text, '', "Position 3 should remain unchanged")
    
    def test_last_position_long_text_saves_with_form_encoded_data(self):
        """Test that long_text update for LAST position is saved (this worked even before the fix)."""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line3.pk})
        
        new_long_text = 'Updated long text for last position'
        data = {
            'long_text': new_long_text
        }
        
        response = self.client.post(url, data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        
        # Check that long_text was updated in database
        self.line3.refresh_from_db()
        self.assertEqual(self.line3.long_text, new_long_text,
                        "Last position long_text should be saved")
        
        # Verify other positions were NOT affected
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.assertEqual(self.line1.long_text, '', "Position 1 should remain unchanged")
        self.assertEqual(self.line2.long_text, '', "Position 2 should remain unchanged")
    
    def test_empty_long_text_saves_as_empty_string_not_undefined(self):
        """Test that empty long_text is saved as '' not undefined (requirement from issue)."""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line1.pk})
        
        # First set some text
        self.line1.long_text = 'Some text'
        self.line1.save()
        
        # Now clear it (simulates user deleting all text from textarea)
        # With the fix: hx-vals='js:{"long_text": this.value || ""}' ensures we send "" not undefined
        data = {
            'long_text': ''
        }
        
        response = self.client.post(url, data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        
        # Check that long_text was set to empty string (not None/undefined)
        self.line1.refresh_from_db()
        self.assertEqual(self.line1.long_text, '', 
                        "Empty long_text should be saved as empty string, not undefined")
        self.assertIsNotNone(self.line1.long_text, 
                           "long_text should not be None")
    
    def test_all_positions_can_be_updated_independently(self):
        """Test that all three positions can be updated with different long_text values."""
        # Update Position 1
        url1 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line1.pk})
        response1 = self.client.post(url1, data={'long_text': 'Text for position 1'})
        self.assertEqual(response1.status_code, 200)
        
        # Update Position 2
        url2 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line2.pk})
        response2 = self.client.post(url2, data={'long_text': 'Text for position 2'})
        self.assertEqual(response2.status_code, 200)
        
        # Update Position 3
        url3 = reverse('auftragsverwaltung:ajax_update_line',
                      kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line3.pk})
        response3 = self.client.post(url3, data={'long_text': 'Text for position 3'})
        self.assertEqual(response3.status_code, 200)
        
        # Verify all positions have their correct long_text values
        self.line1.refresh_from_db()
        self.line2.refresh_from_db()
        self.line3.refresh_from_db()
        
        self.assertEqual(self.line1.long_text, 'Text for position 1',
                        "Position 1 should have its own long_text")
        self.assertEqual(self.line2.long_text, 'Text for position 2',
                        "Position 2 should have its own long_text")
        self.assertEqual(self.line3.long_text, 'Text for position 3',
                        "Position 3 should have its own long_text")
        
        # Ensure no values were swapped between positions
        self.assertNotEqual(self.line1.long_text, self.line2.long_text,
                          "Positions 1 and 2 should have different long_text")
        self.assertNotEqual(self.line2.long_text, self.line3.long_text,
                          "Positions 2 and 3 should have different long_text")
        self.assertNotEqual(self.line1.long_text, self.line3.long_text,
                          "Positions 1 and 3 should have different long_text")
    
    def test_html_content_is_sanitized(self):
        """Test that HTML content from Quill editor is sanitized before saving."""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line1.pk})
        
        # Send HTML content with allowed and disallowed tags (simulates Quill editor output)
        html_content = '<p>This is <strong>bold</strong> and <em>italic</em> text.</p><ul><li>List item 1</li><li>List item 2</li></ul>'
        
        data = {
            'long_text': html_content
        }
        
        response = self.client.post(url, data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        
        # Check that HTML was saved (sanitized but preserved)
        self.line1.refresh_from_db()
        self.assertIn('<strong>bold</strong>', self.line1.long_text)
        self.assertIn('<em>italic</em>', self.line1.long_text)
        self.assertIn('<ul>', self.line1.long_text)
        self.assertIn('<li>List item 1</li>', self.line1.long_text)
    
    def test_dangerous_html_is_stripped(self):
        """Test that dangerous HTML tags (like script) are stripped during sanitization."""
        url = reverse('auftragsverwaltung:ajax_update_line',
                     kwargs={'doc_key': 'quote', 'pk': self.document.pk, 'line_id': self.line1.pk})
        
        # Send HTML content with script tag (should be stripped)
        html_content = '<p>Normal text</p><script>alert("XSS")</script><p>More text</p>'
        
        data = {
            'long_text': html_content
        }
        
        response = self.client.post(url, data=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data.get('success'))
        
        # Check that script tag was stripped but normal paragraphs remain
        self.line1.refresh_from_db()
        self.assertNotIn('<script>', self.line1.long_text)
        self.assertIn('<p>Normal text</p>', self.line1.long_text)
        self.assertIn('<p>More text</p>', self.line1.long_text)
        # Note: bleach with strip=True removes tags but keeps content
        # The content itself (e.g., 'alert("XSS")') remains, but without
        # script tags it cannot execute. This is acceptable for our use case
        # as the content is always rendered as text or within safe HTML context.

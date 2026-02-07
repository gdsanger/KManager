"""
Test cases for decimal parsing and normalization functionality
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
import json

from auftragsverwaltung.models import Contract, ContractLine, DocumentType, NumberRange
from auftragsverwaltung.views import normalize_decimal_input
from core.models import Mandant, Adresse, TaxRate, PaymentTerm
from datetime import date

User = get_user_model()


class DecimalNormalizationTestCase(TestCase):
    """Test cases for the normalize_decimal_input utility function"""
    
    def test_german_format_with_comma(self):
        """Test German format with comma as decimal separator"""
        self.assertEqual(normalize_decimal_input("1,0000"), Decimal("1.0000"))
        self.assertEqual(normalize_decimal_input("99,00"), Decimal("99.00"))
        self.assertEqual(normalize_decimal_input("0,5"), Decimal("0.5"))
        self.assertEqual(normalize_decimal_input("123,456"), Decimal("123.456"))
    
    def test_german_format_with_thousands_separator(self):
        """Test German format with dot as thousands separator and comma as decimal"""
        self.assertEqual(normalize_decimal_input("1.234,56"), Decimal("1234.56"))
        self.assertEqual(normalize_decimal_input("10.000,00"), Decimal("10000.00"))
        self.assertEqual(normalize_decimal_input("1.000.000,99"), Decimal("1000000.99"))
    
    def test_english_format_with_dot(self):
        """Test English format with dot as decimal separator"""
        self.assertEqual(normalize_decimal_input("1.0000"), Decimal("1.0000"))
        self.assertEqual(normalize_decimal_input("99.00"), Decimal("99.00"))
        self.assertEqual(normalize_decimal_input("0.5"), Decimal("0.5"))
        self.assertEqual(normalize_decimal_input("123.456"), Decimal("123.456"))
    
    def test_english_format_with_thousands_separator(self):
        """Test English format with comma as thousands separator and dot as decimal"""
        self.assertEqual(normalize_decimal_input("1,234.56"), Decimal("1234.56"))
        self.assertEqual(normalize_decimal_input("10,000.00"), Decimal("10000.00"))
        self.assertEqual(normalize_decimal_input("1,000,000.99"), Decimal("1000000.99"))
    
    def test_integer_strings(self):
        """Test integer strings without decimal separators"""
        self.assertEqual(normalize_decimal_input("100"), Decimal("100"))
        self.assertEqual(normalize_decimal_input("1234567"), Decimal("1234567"))
        self.assertEqual(normalize_decimal_input("0"), Decimal("0"))
    
    def test_numeric_inputs(self):
        """Test numeric inputs (int, float, Decimal)"""
        self.assertEqual(normalize_decimal_input(100), Decimal("100"))
        self.assertEqual(normalize_decimal_input(99.00), Decimal("99.00"))
        self.assertEqual(normalize_decimal_input(1.5), Decimal("1.5"))
        self.assertEqual(normalize_decimal_input(Decimal("123.45")), Decimal("123.45"))
    
    def test_whitespace_handling(self):
        """Test that whitespace is properly trimmed"""
        self.assertEqual(normalize_decimal_input("  99,00  "), Decimal("99.00"))
        self.assertEqual(normalize_decimal_input(" 1.234,56 "), Decimal("1234.56"))
    
    def test_invalid_inputs_raise_error(self):
        """Test that invalid inputs raise ValueError"""
        with self.assertRaises(ValueError):
            normalize_decimal_input(None)
        
        with self.assertRaises(ValueError):
            normalize_decimal_input("")
        
        with self.assertRaises(ValueError):
            normalize_decimal_input("   ")
        
        with self.assertRaises(ValueError):
            normalize_decimal_input("abc")
        
        with self.assertRaises(ValueError):
            normalize_decimal_input("12,34,56")


class ContractLineDecimalParsingTestCase(TestCase):
    """Test cases for contract line AJAX endpoints with decimal parsing"""
    
    def setUp(self):
        """Set up test data"""
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
            land='DE'
        )
        
        # Create document type
        self.document_type, _ = DocumentType.objects.get_or_create(
            key='invoice',
            defaults={
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'requires_due_date': True,
                'is_active': True
            }
        )
        
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code='USt19',
            name='Umsatzsteuer 19%',
            rate=Decimal('0.1900'),
            is_active=True
        )
        
        # Create payment term
        self.payment_term = PaymentTerm.objects.create(
            name='Net 30',
            net_days=30,
            is_default=False
        )
        
        # Create contract NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Create test contract
        self.contract = Contract.objects.create(
            company=self.company,
            customer=self.customer,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Test Monthly Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
    
    def test_ajax_add_line_german_format(self):
        """Test adding a line with German decimal format (comma separator)"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'Test Line with German Format',
            'quantity': '1,0000',
            'unit_price_net': '99,00',
            'tax_rate_id': self.tax_rate.pk,
            'is_discountable': True,
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should succeed (200)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('line', response_data)
        
        # Check that line was created with correct decimal values
        line = ContractLine.objects.get(contract=self.contract, description='Test Line with German Format')
        self.assertEqual(line.quantity, Decimal('1.0000'))
        self.assertEqual(line.unit_price_net, Decimal('99.00'))
    
    def test_ajax_add_line_german_format_with_thousands(self):
        """Test adding a line with German format including thousands separator"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'Test Line with Thousands',
            'quantity': '10,5000',
            'unit_price_net': '1.234,56',
            'tax_rate_id': self.tax_rate.pk,
            'is_discountable': True,
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        line = ContractLine.objects.get(contract=self.contract, description='Test Line with Thousands')
        self.assertEqual(line.quantity, Decimal('10.5000'))
        self.assertEqual(line.unit_price_net, Decimal('1234.56'))
    
    def test_ajax_add_line_english_format(self):
        """Test adding a line with English decimal format (dot separator)"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'Test Line with English Format',
            'quantity': '1.0000',
            'unit_price_net': '99.00',
            'tax_rate_id': self.tax_rate.pk,
            'is_discountable': True,
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        line = ContractLine.objects.get(contract=self.contract, description='Test Line with English Format')
        self.assertEqual(line.quantity, Decimal('1.0000'))
        self.assertEqual(line.unit_price_net, Decimal('99.00'))
    
    def test_ajax_update_line_german_format(self):
        """Test updating a line with German decimal format"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Original Line',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_update_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        data = {
            'description': 'Updated Line',
            'quantity': '2,5000',
            'unit_price_net': '150,75',
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check that line was updated
        line.refresh_from_db()
        self.assertEqual(line.description, 'Updated Line')
        self.assertEqual(line.quantity, Decimal('2.5000'))
        self.assertEqual(line.unit_price_net, Decimal('150.75'))
    
    def test_ajax_update_line_english_format(self):
        """Test updating a line with English decimal format"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Original Line',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_update_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        data = {
            'quantity': '3.0000',
            'unit_price_net': '200.00',
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Check that line was updated
        line.refresh_from_db()
        self.assertEqual(line.quantity, Decimal('3.0000'))
        self.assertEqual(line.unit_price_net, Decimal('200.00'))
    
    def test_ajax_add_line_invalid_quantity_returns_400(self):
        """Test that invalid quantity returns 400 (not 500)"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'Test Line',
            'quantity': 'invalid',
            'unit_price_net': '99.00',
            'tax_rate_id': self.tax_rate.pk,
            'is_discountable': True,
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return 400 (validation error), not 500
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertIn('Ungültige Menge', response_data['error'])
    
    def test_ajax_add_line_invalid_price_returns_400(self):
        """Test that invalid price returns 400 (not 500)"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'Test Line',
            'quantity': '1.0',
            'unit_price_net': 'not-a-number',
            'tax_rate_id': self.tax_rate.pk,
            'is_discountable': True,
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return 400 (validation error), not 500
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertIn('Ungültiger Netto-Stückpreis', response_data['error'])
    
    def test_ajax_update_line_invalid_quantity_returns_400(self):
        """Test that updating with invalid quantity returns 400"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Test Line',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_update_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        data = {
            'quantity': 'abc',
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return 400, not 500
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertIn('Ungültige Menge', response_data['error'])
    
    def test_ajax_update_line_invalid_price_returns_400(self):
        """Test that updating with invalid price returns 400"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Test Line',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_update_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        data = {
            'unit_price_net': 'xyz',
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should return 400, not 500
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('error', response_data)
        self.assertIn('Ungültiger Netto-Stückpreis', response_data['error'])

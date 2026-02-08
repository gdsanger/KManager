from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
import json

from auftragsverwaltung.models import (
    Contract, ContractLine, ContractRun, DocumentType, NumberRange
)
from core.models import Mandant, Adresse, TaxRate, PaymentTerm

User = get_user_model()


class ContractViewTestCase(TestCase):
    """Test cases for contract views"""
    
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
            # last_name removed
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='DE'
        )
        
        # Create or get document type
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
        
        # Create test contract line
        self.contract_line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Test Service',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
    
    def test_contract_list_view(self):
        """Test that contract list view works"""
        url = reverse('auftragsverwaltung:contract_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Monthly Contract')
    
    def test_contract_list_has_clickable_links(self):
        """Test that contract list contains clickable links to edit and detail views"""
        url = reverse('auftragsverwaltung:contract_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the contract name is a link to the update view
        update_url = reverse('auftragsverwaltung:contract_update', kwargs={'pk': self.contract.pk})
        self.assertContains(response, f'href="{update_url}"')
        
        # Check that the detail link exists in the action buttons
        detail_url = reverse('auftragsverwaltung:contract_detail', kwargs={'pk': self.contract.pk})
        self.assertContains(response, f'href="{detail_url}"')
        
        # Check that both action buttons are present (eye icon for detail, pencil for edit)
        self.assertContains(response, 'bi-eye')
        self.assertContains(response, 'bi-pencil')
    
    def test_contract_detail_view(self):
        """Test that contract detail view works"""
        url = reverse('auftragsverwaltung:contract_detail', kwargs={'pk': self.contract.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Monthly Contract')
        self.assertContains(response, 'Test Service')
        self.assertContains(response, 'Ausführungs-Historie')
    
    def test_contract_create_view_get(self):
        """Test that contract create view GET works"""
        url = reverse('auftragsverwaltung:contract_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuer Vertrag')
    
    def test_contract_create_view_post(self):
        """Test that contract create view POST works"""
        url = reverse('auftragsverwaltung:contract_create')
        
        data = {
            'company_id': self.company.pk,
            'customer_id': self.customer.pk,
            'document_type_id': self.document_type.pk,
            'payment_term_id': self.payment_term.pk,
            'name': 'New Test Contract',
            'currency': 'EUR',
            'interval': 'QUARTERLY',
            'start_date': '2026-02-01',
            'next_run_date': '2026-02-01',
            'is_active': 'on',
        }
        
        response = self.client.post(url, data)
        
        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was created
        new_contract = Contract.objects.get(name='New Test Contract')
        self.assertEqual(new_contract.interval, 'QUARTERLY')
        self.assertEqual(new_contract.customer, self.customer)
    
    def test_contract_update_view(self):
        """Test that contract update view works"""
        url = reverse('auftragsverwaltung:contract_update', kwargs={'pk': self.contract.pk})
        
        data = {
            'company_id': self.company.pk,
            'customer_id': self.customer.pk,
            'document_type_id': self.document_type.pk,
            'payment_term_id': self.payment_term.pk,
            'name': 'Updated Contract Name',
            'currency': 'EUR',
            'interval': 'ANNUAL',
            'start_date': '2026-01-01',
            'next_run_date': '2026-01-01',
            'is_active': 'on',
        }
        
        response = self.client.post(url, data)
        
        # Should redirect to detail view
        self.assertEqual(response.status_code, 302)
        
        # Check that contract was updated
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.name, 'Updated Contract Name')
        self.assertEqual(self.contract.interval, 'ANNUAL')


class ContractAjaxEndpointTestCase(TestCase):
    """Test cases for contract AJAX endpoints"""
    
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
            # last_name removed
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='DE'
        )
        
        # Create or get document type
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
    
    def test_ajax_add_line(self):
        """Test adding a line via AJAX"""
        url = reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': self.contract.pk})
        
        data = {
            'description': 'New Test Line',
            'quantity': '2.0000',
            'unit_price_net': '50.00',
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
        self.assertIn('line', response_data)
        self.assertIn('preview_totals', response_data)
        
        # Check that line was created
        line = ContractLine.objects.get(contract=self.contract, description='New Test Line')
        self.assertEqual(line.quantity, Decimal('2.0000'))
        self.assertEqual(line.unit_price_net, Decimal('50.00'))
    
    def test_ajax_update_line(self):
        """Test updating a line via AJAX"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Original Description',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_update_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        data = {
            'description': 'Updated Description',
            'quantity': '3.0000',
            'unit_price_net': '75.00',
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('line', response_data)
        self.assertIn('preview_totals', response_data)
        
        # Check that line was updated
        line.refresh_from_db()
        self.assertEqual(line.description, 'Updated Description')
        self.assertEqual(line.quantity, Decimal('3.0000'))
        self.assertEqual(line.unit_price_net, Decimal('75.00'))
    
    def test_ajax_delete_line(self):
        """Test deleting a line via AJAX"""
        # Create a line first
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='To Be Deleted',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        url = reverse('auftragsverwaltung:ajax_contract_delete_line', 
                     kwargs={'pk': self.contract.pk, 'line_id': line.pk})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('preview_totals', response_data)
        
        # Check that line was deleted
        self.assertFalse(ContractLine.objects.filter(pk=line.pk).exists())
    
    def test_ajax_calculate_next_run_date(self):
        """Test calculating next run date via AJAX"""
        url = reverse('auftragsverwaltung:ajax_contract_calculate_next_run_date', 
                     kwargs={'pk': self.contract.pk})
        
        # Test monthly interval
        response = self.client.get(url, {
            'interval': 'MONTHLY',
            'start_date': '2026-01-15',
            'current_next_run_date': '2026-01-15'
        })
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['next_run_date'], '2026-02-15')
        
        # Test quarterly interval
        response = self.client.get(url, {
            'interval': 'QUARTERLY',
            'start_date': '2026-01-15',
            'current_next_run_date': '2026-01-15'
        })
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['next_run_date'], '2026-04-15')


class ContractPreviewCalculationTestCase(TestCase):
    """Test cases for contract preview totals calculation"""
    
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
            # last_name removed
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='DE'
        )
        
        # Create or get document type
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
        self.tax_rate_19 = TaxRate.objects.create(
            code='USt19',
            name='Umsatzsteuer 19%',
            rate=Decimal('0.1900'),
            is_active=True
        )
        
        self.tax_rate_7 = TaxRate.objects.create(
            code='USt7',
            name='Umsatzsteuer 7%',
            rate=Decimal('0.0700'),
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
    
    def test_preview_calculation_single_line(self):
        """Test preview calculation with a single line"""
        # Create line: 100 EUR * 1 @ 19% = 100 EUR net, 19 EUR tax, 119 EUR gross
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Test Line',
            quantity=Decimal('1.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
            is_discountable=True
        )
        
        # Import the calculation function
        from auftragsverwaltung.views import _calculate_contract_preview_totals
        
        totals = _calculate_contract_preview_totals(self.contract)
        
        self.assertEqual(Decimal(totals['total_net']), Decimal('100.00'))
        self.assertEqual(Decimal(totals['total_tax']), Decimal('19.00'))
        self.assertEqual(Decimal(totals['total_gross']), Decimal('119.00'))
    
    def test_preview_calculation_multiple_lines(self):
        """Test preview calculation with multiple lines"""
        # Line 1: 100 EUR * 2 @ 19% = 200 EUR net, 38 EUR tax
        line1 = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Test Line 1',
            quantity=Decimal('2.0000'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate_19,
            is_discountable=True
        )
        
        # Line 2: 50 EUR * 3 @ 7% = 150 EUR net, 10.50 EUR tax
        line2 = ContractLine.objects.create(
            contract=self.contract,
            position_no=2,
            description='Test Line 2',
            quantity=Decimal('3.0000'),
            unit_price_net=Decimal('50.00'),
            tax_rate=self.tax_rate_7,
            is_discountable=True
        )
        
        # Import the calculation function
        from auftragsverwaltung.views import _calculate_contract_preview_totals
        
        totals = _calculate_contract_preview_totals(self.contract)
        
        # Total: 350 EUR net, 48.50 EUR tax, 398.50 EUR gross
        self.assertEqual(Decimal(totals['total_net']), Decimal('350.00'))
        self.assertEqual(Decimal(totals['total_tax']), Decimal('48.50'))
        self.assertEqual(Decimal(totals['total_gross']), Decimal('398.50'))
    
    def test_contract_list_shows_multiple_companies(self):
        """Test that contract list shows contracts from multiple companies (Issue #336)"""
        # Create a second company
        company2 = Mandant.objects.create(
            name='Second Company GmbH',
            adresse='Andere Strasse 2',
            plz='54321',
            ort='Andere Stadt',
            land='Deutschland',
            steuernummer='987/654/32109',
            ust_id_nr='DE987654321'
        )
        
        # Create NumberRange for second company
        NumberRange.objects.create(
            company=company2,
            target='CONTRACT',
            reset_policy='YEARLY',
            format='V{yy}-{seq:05d}'
        )
        
        # Create a second customer
        customer2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Customer Two',
            anrede='Frau',
            strasse='Customer Street 2',
            plz='98765',
            ort='Customer City 2',
            land='DE'
        )
        
        # Create contract for second company
        contract2 = Contract.objects.create(
            company=company2,
            customer=customer2,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Contract for Company 2',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 2, 1),
            next_run_date=date(2026, 2, 1),
            is_active=True
        )
        
        # Get the contract list
        url = reverse('auftragsverwaltung:contract_list')
        response = self.client.get(url)
        
        # Should show contracts from BOTH companies
        self.assertEqual(response.status_code, 200)
        table = response.context['table']
        
        # Should have at least 2 contracts (1 from each company)
        self.assertGreaterEqual(len(table.data), 2)
        
        # Verify that both companies' contracts are present
        contract_names = [c.name for c in table.data.data]
        self.assertIn('Test Monthly Contract', contract_names)  # company1
        self.assertIn('Contract for Company 2', contract_names)  # company2

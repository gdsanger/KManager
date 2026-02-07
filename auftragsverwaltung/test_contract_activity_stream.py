"""
Tests for ActivityStream integration in Contract views and services
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
import json

from auftragsverwaltung.models import (
    Contract, ContractLine, ContractRun, DocumentType, NumberRange, SalesDocument
)
from auftragsverwaltung.services.contract_billing import ContractBillingService
from core.models import Mandant, Adresse, TaxRate, PaymentTerm, Activity

User = get_user_model()


class ContractActivityStreamTestCase(TestCase):
    """Test cases for contract activity stream integration"""
    
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
        
        # Create test customers
        self.customer1 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer 1',
            anrede='Herr',
            strasse='Kundenstraße 1',
            plz='54321',
            ort='Kundenstadt',
            land='DE'
        )
        
        self.customer2 = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Customer 2',
            anrede='Frau',
            strasse='Kundenstraße 2',
            plz='54322',
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
        
        # Create document NumberRange
        NumberRange.objects.create(
            company=self.company,
            target='DOCUMENT',
            document_type=self.document_type,
            reset_policy='YEARLY',
            format='R{yy}-{seq:05d}'
        )
    
    def test_contract_creation_logs_activity(self):
        """Test that creating a contract logs an activity"""
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Create contract via POST
        response = self.client.post(reverse('auftragsverwaltung:contract_create'), {
            'company_id': self.company.pk,
            'name': 'New Test Contract',
            'customer_id': self.customer1.pk,
            'document_type_id': self.document_type.pk,
            'payment_term_id': self.payment_term.pk,
            'currency': 'EUR',
            'interval': 'MONTHLY',
            'start_date': '2026-01-01',
            'next_run_date': '2026-01-01',
            'is_active': 'on',
        })
        
        # Check that activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_CREATED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('New Test Contract', activity.title)
        self.assertIn('Test Customer 1', activity.description)
        self.assertEqual(activity.severity, 'INFO')
    
    def test_contract_status_change_logs_activity(self):
        """Test that changing contract status logs a specific activity"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            customer=self.customer1,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Status Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Update contract - change status to inactive
        response = self.client.post(
            reverse('auftragsverwaltung:contract_update', kwargs={'pk': contract.pk}),
            {
                'name': contract.name,
                'customer_id': contract.customer.pk,
                'document_type_id': contract.document_type.pk,
                'payment_term_id': contract.payment_term.pk,
                'currency': contract.currency,
                'interval': contract.interval,
                'start_date': contract.start_date.strftime('%Y-%m-%d'),
                'next_run_date': contract.next_run_date.strftime('%Y-%m-%d'),
                # is_active NOT included = unchecked = False
            }
        )
        
        # Check that status change activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_STATUS_CHANGED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('Status Test Contract', activity.title)
        self.assertIn('deaktiviert', activity.description)
        self.assertIn('vorher: aktiv', activity.description)
    
    def test_contract_customer_change_logs_activity(self):
        """Test that changing contract customer logs a specific activity"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            customer=self.customer1,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Customer Change Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Update contract - change customer
        response = self.client.post(
            reverse('auftragsverwaltung:contract_update', kwargs={'pk': contract.pk}),
            {
                'name': contract.name,
                'customer_id': self.customer2.pk,  # Changed customer
                'document_type_id': contract.document_type.pk,
                'payment_term_id': contract.payment_term.pk,
                'currency': contract.currency,
                'interval': contract.interval,
                'start_date': contract.start_date.strftime('%Y-%m-%d'),
                'next_run_date': contract.next_run_date.strftime('%Y-%m-%d'),
                'is_active': 'on',
            }
        )
        
        # Check that customer change activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_CUSTOMER_CHANGED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('Kunde geändert', activity.title)
        self.assertIn('Test Customer 2', activity.description)
        self.assertIn('Test Customer 1', activity.description)
    
    def test_contract_update_without_status_or_customer_change_logs_generic_activity(self):
        """Test that updating contract without status/customer change logs generic update"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            customer=self.customer1,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Generic Update Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Update contract - change name only
        response = self.client.post(
            reverse('auftragsverwaltung:contract_update', kwargs={'pk': contract.pk}),
            {
                'name': 'Updated Name',  # Changed name
                'customer_id': contract.customer.pk,  # Same customer
                'document_type_id': contract.document_type.pk,
                'payment_term_id': contract.payment_term.pk,
                'currency': contract.currency,
                'interval': contract.interval,
                'start_date': contract.start_date.strftime('%Y-%m-%d'),
                'next_run_date': contract.next_run_date.strftime('%Y-%m-%d'),
                'is_active': 'on',  # Same status
            }
        )
        
        # Check that generic update activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_UPDATED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        
        # Should not have logged status or customer change
        self.assertEqual(
            Activity.objects.filter(activity_type='CONTRACT_STATUS_CHANGED').count(),
            0
        )
        self.assertEqual(
            Activity.objects.filter(activity_type='CONTRACT_CUSTOMER_CHANGED').count(),
            0
        )
    
    def test_contract_line_add_logs_activity(self):
        """Test that adding a contract line logs an activity"""
        # Create contract
        contract = Contract.objects.create(
            company=self.company,
            customer=self.customer1,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Line Add Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Add line via AJAX
        response = self.client.post(
            reverse('auftragsverwaltung:ajax_contract_add_line', kwargs={'pk': contract.pk}),
            data=json.dumps({
                'description': 'Test Line Item',
                'quantity': '1',
                'unit_price_net': '100.00',
                'tax_rate_id': self.tax_rate.pk,
                'is_discountable': True,
            }),
            content_type='application/json'
        )
        
        # Check that activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_LINE_ADDED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('Vertragsposition hinzugefügt', activity.title)
    
    def test_contract_billing_success_logs_activity(self):
        """Test that successful contract billing logs an activity"""
        # Create contract with line
        contract = Contract.objects.create(
            company=self.company,
            customer=self.customer1,
            document_type=self.document_type,
            payment_term=self.payment_term,
            name='Billing Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
        
        ContractLine.objects.create(
            contract=contract,
            position_no=1,
            description='Test Service',
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Run billing service
        runs = ContractBillingService.generate_due(today=date(2026, 1, 1))
        
        # Check that activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_INVOICE_GENERATED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertIsNone(activity.actor)  # Automated process
        self.assertIn('Rechnung aus Vertrag erstellt', activity.title)
        self.assertIn('Billing Test Contract', activity.title)
        self.assertEqual(activity.severity, 'INFO')


class ContractLineActivityStreamTestCase(TestCase):
    """Test cases for contract line activity stream integration"""
    
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
            name='Line Test Contract',
            currency='EUR',
            interval='MONTHLY',
            start_date=date(2026, 1, 1),
            next_run_date=date(2026, 1, 1),
            is_active=True
        )
    
    def test_contract_line_update_logs_activity(self):
        """Test that updating a contract line logs an activity"""
        # Create line
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='Original Description',
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Update line via AJAX
        response = self.client.post(
            reverse('auftragsverwaltung:ajax_contract_update_line',
                    kwargs={'pk': self.contract.pk, 'line_id': line.pk}),
            data=json.dumps({
                'description': 'Updated Description',
                'quantity': '2.00',
                'unit_price_net': '150.00',
            }),
            content_type='application/json'
        )
        
        # Check that activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_LINE_UPDATED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('Vertragsposition aktualisiert', activity.title)
    
    def test_contract_line_delete_logs_activity(self):
        """Test that deleting a contract line logs an activity"""
        # Create line
        line = ContractLine.objects.create(
            contract=self.contract,
            position_no=1,
            description='To Be Deleted',
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            tax_rate=self.tax_rate,
            is_discountable=True
        )
        
        # Clear any existing activities
        Activity.objects.all().delete()
        
        # Delete line via AJAX
        response = self.client.post(
            reverse('auftragsverwaltung:ajax_contract_delete_line',
                    kwargs={'pk': self.contract.pk, 'line_id': line.pk}),
            content_type='application/json'
        )
        
        # Check that activity was logged
        activities = Activity.objects.filter(
            company=self.company,
            activity_type='CONTRACT_LINE_DELETED'
        )
        
        self.assertEqual(activities.count(), 1)
        activity = activities.first()
        self.assertEqual(activity.domain, 'ORDER')
        self.assertEqual(activity.actor, self.user)
        self.assertIn('Vertragsposition gelöscht', activity.title)
        self.assertIn('To Be Deleted', activity.description)

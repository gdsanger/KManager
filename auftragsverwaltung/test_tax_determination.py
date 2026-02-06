"""
Tests for TaxDeterminationService

Tests the EU tax logic implementation including:
- German customers (standard VAT)
- EU B2B customers with VAT ID (reverse charge)
- EU B2C customers (standard VAT)
- Non-EU customers (export, 0%)
"""
from django.test import TestCase
from decimal import Decimal

from core.models import TaxRate, Adresse
from auftragsverwaltung.services.tax_determination import TaxDeterminationService


class TaxDeterminationServiceTest(TestCase):
    """Test suite for TaxDeterminationService"""
    
    def setUp(self):
        """Set up test data"""
        # Create tax rates
        self.tax_rate_19 = TaxRate.objects.create(
            code='VAT',
            name='Standard VAT',
            rate=Decimal('0.19')
        )
        self.tax_rate_7 = TaxRate.objects.create(
            code='REDUCED',
            name='Reduced VAT',
            rate=Decimal('0.07')
        )
        self.tax_rate_0 = TaxRate.objects.create(
            code='ZERO',
            name='Zero VAT',
            rate=Decimal('0.00')
        )
    
    def test_no_customer_uses_item_tax_rate(self):
        """Test: No customer → use item's default tax rate"""
        result = TaxDeterminationService.determine_tax_rate(
            customer=None,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result, self.tax_rate_19)
    
    def test_german_customer_uses_item_tax_rate(self):
        """Test: German customer → use item's default tax rate"""
        customer = Adresse(
            name='Max Mustermann',
            strasse='Musterstraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
            country_code='DE',
            is_business=True
        )
        
        result = TaxDeterminationService.determine_tax_rate(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result, self.tax_rate_19)
    
    def test_eu_b2b_with_vat_id_uses_zero_tax(self):
        """Test: EU B2B customer with VAT ID → reverse charge (0%)"""
        customer = Adresse(
            name='French Company',
            strasse='Rue de Paris 1',
            plz='75001',
            ort='Paris',
            land='France',
            country_code='FR',
            is_business=True,
            vat_id='FR12345678901'
        )
        
        result = TaxDeterminationService.determine_tax_rate(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result.rate, Decimal('0.00'))
    
    def test_eu_b2c_uses_item_tax_rate(self):
        """Test: EU B2C customer → use item's default tax rate (MVP)"""
        customer = Adresse(
            name='Jean Dupont',
            strasse='Rue de Paris 1',
            plz='75001',
            ort='Paris',
            land='France',
            country_code='FR',
            is_business=False
        )
        
        result = TaxDeterminationService.determine_tax_rate(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result, self.tax_rate_19)
    
    def test_eu_business_without_vat_id_uses_item_tax_rate(self):
        """Test: EU business without VAT ID → use item's default tax rate"""
        customer = Adresse(
            name='French Company',
            strasse='Rue de Paris 1',
            plz='75001',
            ort='Paris',
            land='France',
            country_code='FR',
            is_business=True,
            vat_id=''  # No VAT ID
        )
        
        result = TaxDeterminationService.determine_tax_rate(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result, self.tax_rate_19)
    
    def test_non_eu_customer_uses_zero_tax(self):
        """Test: Non-EU customer → export (0%)"""
        customer = Adresse(
            name='US Company',
            strasse='Main Street 1',
            plz='10001',
            ort='New York',
            land='USA',
            country_code='US',
            is_business=True
        )
        
        result = TaxDeterminationService.determine_tax_rate(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(result.rate, Decimal('0.00'))
    
    def test_tax_label_german_customer(self):
        """Test: Tax label for German customer"""
        customer = Adresse(
            name='Max Mustermann',
            strasse='Musterstraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
            country_code='DE'
        )
        
        label = TaxDeterminationService.get_tax_label(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(label, "Standard (DE)")
    
    def test_tax_label_eu_b2b(self):
        """Test: Tax label for EU B2B customer"""
        customer = Adresse(
            name='French Company',
            strasse='Rue de Paris 1',
            plz='75001',
            ort='Paris',
            land='France',
            country_code='FR',
            is_business=True,
            vat_id='FR12345678901'
        )
        
        label = TaxDeterminationService.get_tax_label(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(label, "Reverse Charge (EU B2B)")
    
    def test_tax_label_export(self):
        """Test: Tax label for export customer"""
        customer = Adresse(
            name='US Company',
            strasse='Main Street 1',
            plz='10001',
            ort='New York',
            land='USA',
            country_code='US'
        )
        
        label = TaxDeterminationService.get_tax_label(
            customer=customer,
            item_tax_rate=self.tax_rate_19
        )
        self.assertEqual(label, "Export (Nicht-EU)")
    
    def test_all_eu_countries_recognized(self):
        """Test: All EU country codes are recognized"""
        # Test a selection of EU countries
        eu_countries = ['AT', 'BE', 'FR', 'IT', 'ES', 'NL', 'PL', 'SE']
        
        for country in eu_countries:
            customer = Adresse(
                name='Test Customer',
                strasse='Test Street 1',
                plz='12345',
                ort='Test City',
                land='Test Country',
                country_code=country,
                is_business=True,
                vat_id='TEST123'
            )
            
            result = TaxDeterminationService.determine_tax_rate(
                customer=customer,
                item_tax_rate=self.tax_rate_19
            )
            
            # EU B2B with VAT ID should get 0% tax
            self.assertEqual(
                result.rate,
                Decimal('0.00'),
                f"Country {country} should get 0% tax for B2B with VAT ID"
            )

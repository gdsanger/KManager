"""
Tax Determination Service

Provides centralized tax rate determination logic based on customer data (EU tax logic).
Handles B2B/B2C scenarios, reverse charge, and export cases.

Business Rules (MVP):
- Customer in DE: Use standard DE VAT rates (19%, 7%, 0% based on article)
- Customer in EU (not DE):
  * B2B with VAT ID → Reverse Charge → 0%
  * B2C → Use DE VAT rates (MVP decision)
- Customer outside EU: Export → 0%
"""
from decimal import Decimal
from typing import Optional


class TaxDeterminationService:
    """
    Service for determining tax rate based on customer and item data
    
    This service is deterministic and encapsulates all tax logic in one place.
    """
    
    # EU country codes (27 member states as of 2024)
    EU_COUNTRIES = {
        'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
        'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
        'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    }
    
    @classmethod
    def determine_tax_rate(
        cls,
        customer,
        item_tax_rate,
        company_country: str = 'DE'
    ):
        """
        Determine tax rate for a sales document line
        
        Args:
            customer: Adresse instance (customer)
            item_tax_rate: TaxRate instance from the Item
            company_country: Company's country code (default: DE)
            
        Returns:
            TaxRate instance to use for the line
            
        Business Logic:
        1. If customer is None, use item's default tax rate
        2. If customer is in DE, use item's default tax rate
        3. If customer is in EU (not DE):
           - B2B with VAT ID → Return 0% tax rate (reverse charge)
           - B2C → Use item's default tax rate (MVP)
        4. If customer is outside EU → Return 0% tax rate (export)
        """
        # Import here to avoid circular imports
        from core.models import TaxRate
        
        # Case 1: No customer → use item's default tax rate
        if customer is None:
            return item_tax_rate
        
        # Get customer country code (normalized to uppercase)
        customer_country = cls._get_customer_country(customer)
        
        # Case 2: Customer in DE → use item's default tax rate
        if customer_country == 'DE':
            return item_tax_rate
        
        # Case 3: Customer in EU (not DE)
        if customer_country in cls.EU_COUNTRIES:
            # Check if B2B with VAT ID
            if cls._is_b2b_with_vat_id(customer):
                # Reverse charge → 0% tax
                return cls._get_zero_tax_rate()
            else:
                # B2C → Use item's default tax rate (MVP decision)
                return item_tax_rate
        
        # Case 4: Customer outside EU → Export → 0% tax
        return cls._get_zero_tax_rate()
    
    @classmethod
    def _get_customer_country(cls, customer) -> str:
        """
        Get normalized country code from customer
        
        Args:
            customer: Adresse instance
            
        Returns:
            Uppercase country code (e.g., 'DE', 'FR', 'US')
        """
        if hasattr(customer, 'country_code') and customer.country_code:
            return customer.country_code.strip().upper()
        # Fallback to 'land' field if country_code is not set
        if hasattr(customer, 'land') and customer.land:
            # Try to extract country code from 'land' field
            # For MVP, we'll assume land contains the full country name
            # This is a simplification - in production, you'd use a mapping
            land = customer.land.strip().upper()
            if land in ('DEUTSCHLAND', 'GERMANY'):
                return 'DE'
            # For MVP, default to DE if we can't determine
            return 'DE'
        return 'DE'
    
    @classmethod
    def _is_b2b_with_vat_id(cls, customer) -> bool:
        """
        Check if customer is B2B with VAT ID
        
        Args:
            customer: Adresse instance
            
        Returns:
            True if customer is business and has VAT ID
        """
        # Check if customer is marked as business
        is_business = getattr(customer, 'is_business', True)
        # Check if customer has VAT ID
        has_vat_id = bool(getattr(customer, 'vat_id', None) and customer.vat_id.strip())
        
        return is_business and has_vat_id
    
    @classmethod
    def _get_zero_tax_rate(cls):
        """
        Get or create 0% tax rate
        
        Returns:
            TaxRate instance with 0% rate
        """
        from core.models import TaxRate
        
        # Try to get existing 0% tax rate
        try:
            return TaxRate.objects.get(code='ZERO', rate=Decimal('0.00'))
        except TaxRate.DoesNotExist:
            # If not found, try to get any 0% rate
            try:
                return TaxRate.objects.filter(rate=Decimal('0.00')).first()
            except:
                # Fallback: return a default (this should be set up in fixtures)
                # For MVP, we raise an error to ensure proper setup
                raise ValueError(
                    "No 0% tax rate found in database. "
                    "Please create a TaxRate with code='ZERO' and rate=0.00"
                )
    
    @classmethod
    def get_tax_label(
        cls,
        customer,
        item_tax_rate,
        company_country: str = 'DE'
    ) -> str:
        """
        Get a human-readable label for the tax logic applied
        
        Args:
            customer: Adresse instance (customer)
            item_tax_rate: TaxRate instance from the Item
            company_country: Company's country code (default: DE)
            
        Returns:
            str: Human-readable label (e.g., "Reverse Charge (EU B2B)", "Export (0%)")
        """
        if customer is None:
            return "Standard"
        
        customer_country = cls._get_customer_country(customer)
        
        if customer_country == 'DE':
            return "Standard (DE)"
        
        if customer_country in cls.EU_COUNTRIES:
            if cls._is_b2b_with_vat_id(customer):
                return "Reverse Charge (EU B2B)"
            else:
                return "Standard (EU B2C)"
        
        return "Export (Nicht-EU)"

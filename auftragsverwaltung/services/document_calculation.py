"""
Document Calculation Service

Provides central, deterministic calculation of document totals (net, tax, gross)
based on document lines. The service is UI-independent and can be called from
both UI and background jobs/tasks.

Business Rules:
- Line selection based on line_type:
  * NORMAL: always included (regardless of is_selected)
  * OPTIONAL: included only if is_selected=True
  * ALTERNATIVE: included only if is_selected=True
- Money/Tax: 2 decimal places, HALF_UP rounding
- Calculation: line-level rounding, then sum to document totals
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class TotalsResult:
    """
    Result object containing calculated totals
    
    Attributes:
        total_net: Total net amount (sum of all line_net)
        total_tax: Total tax amount (sum of all line_tax)
        total_gross: Total gross amount (sum of all line_gross)
    """
    total_net: Decimal
    total_tax: Decimal
    total_gross: Decimal


class DocumentCalculationService:
    """
    Service for calculating document totals based on lines
    
    This service is deterministic and reproduces the same results
    for the same inputs. It uses only Decimal arithmetic (no floats)
    and applies HALF_UP rounding consistently.
    """
    
    # Decimal context for rounding to 2 decimal places
    TWO_PLACES = Decimal('0.01')
    
    @classmethod
    def calculate_line_totals(cls, line) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate line totals with proper rounding (public method)
        
        Calculation steps (as per requirements):
        1. line_net = round(quantity * unit_price_net, 2)
        2. line_tax = round(line_net * tax_rate.rate, 2)
        3. line_gross = line_net + line_tax (optionally round to 2)
        
        Args:
            line: SalesDocumentLine instance
            
        Returns:
            tuple: (line_net, line_tax, line_gross) as Decimal values
            
        Example:
            >>> from auftragsverwaltung.services.document_calculation import DocumentCalculationService
            >>> line_net, line_tax, line_gross = DocumentCalculationService.calculate_line_totals(line)
        """
        return cls._calculate_line_totals(line)
    
    @classmethod
    def recalculate(cls, document, persist: bool = False) -> TotalsResult:
        """
        Recalculate totals for a sales document based on its lines
        
        Args:
            document: SalesDocument instance
            persist: If True, saves the calculated totals to the document
            
        Returns:
            TotalsResult with calculated totals
            
        Example:
            >>> from auftragsverwaltung.models import SalesDocument
            >>> from auftragsverwaltung.services.document_calculation import DocumentCalculationService
            >>> doc = SalesDocument.objects.get(pk=1)
            >>> result = DocumentCalculationService.recalculate(doc)
            >>> print(f"Net: {result.total_net}, Tax: {result.total_tax}, Gross: {result.total_gross}")
            >>> # To persist the results:
            >>> result = DocumentCalculationService.recalculate(doc, persist=True)
        """
        # Get all lines for the document (ordered by position_no for consistency)
        lines = document.lines.select_related('tax_rate').order_by('position_no')
        
        # Initialize totals
        total_net = Decimal('0.00')
        total_tax = Decimal('0.00')
        total_gross = Decimal('0.00')
        
        # Process each line
        for line in lines:
            # Apply selection logic: determine if line should be included
            if not cls._is_line_included(line):
                continue
            
            # Calculate line totals with rounding
            line_net, line_tax, line_gross = cls._calculate_line_totals(line)
            
            # Optionally update line fields (for display purposes)
            # Note: We don't save individual lines here to avoid performance issues
            # The caller can decide whether to update line fields
            line.line_net = line_net
            line.line_tax = line_tax
            line.line_gross = line_gross
            
            # Accumulate to document totals
            total_net += line_net
            total_tax += line_tax
            total_gross += line_gross
        
        # Create result object
        result = TotalsResult(
            total_net=total_net,
            total_tax=total_tax,
            total_gross=total_gross
        )
        
        # Update document fields (in-memory)
        document.total_net = result.total_net
        document.total_tax = result.total_tax
        document.total_gross = result.total_gross
        
        # Persist if requested
        if persist:
            document.save(update_fields=['total_net', 'total_tax', 'total_gross'])
        
        return result
    
    @classmethod
    def _is_line_included(cls, line) -> bool:
        """
        Determine if a line should be included in totals calculation
        
        Business logic:
        - NORMAL: always included (regardless of is_selected)
        - OPTIONAL: included only if is_selected=True
        - ALTERNATIVE: included only if is_selected=True
        
        Args:
            line: SalesDocumentLine instance
            
        Returns:
            bool: True if line should be included in totals
        """
        # Use the existing model method for consistency
        return line.is_included_in_totals()
    
    @classmethod
    def _calculate_line_totals(cls, line) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate line totals with proper rounding
        
        Calculation steps (as per requirements):
        1. line_net = round(quantity * unit_price_net, 2)
        2. line_tax = round(line_net * tax_rate.rate, 2)
        3. line_gross = line_net + line_tax (optionally round to 2)
        
        Args:
            line: SalesDocumentLine instance
            
        Returns:
            tuple: (line_net, line_tax, line_gross) as Decimal values
        """
        # Step 1: Calculate and round line_net
        line_net = (line.quantity * line.unit_price_net).quantize(
            cls.TWO_PLACES, rounding=ROUND_HALF_UP
        )
        
        # Step 2: Calculate and round line_tax
        line_tax = (line_net * line.tax_rate.rate).quantize(
            cls.TWO_PLACES, rounding=ROUND_HALF_UP
        )
        
        # Step 3: Calculate line_gross (already rounded components)
        line_gross = line_net + line_tax
        # Optional: round again for consistency
        line_gross = line_gross.quantize(cls.TWO_PLACES, rounding=ROUND_HALF_UP)
        
        return line_net, line_tax, line_gross

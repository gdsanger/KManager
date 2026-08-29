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
- Discount: percentage per line, only for lines with is_discountable=True
- Calculation: line-level rounding, then sum to document totals
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class LineAmounts:
    """
    Result object containing the calculated amounts of a single line

    Attributes:
        line_net: Net amount after discount (rounded)
        line_tax: Tax amount based on the discounted net amount (rounded)
        line_gross: Gross amount (line_net + line_tax)
        line_subtotal: Net amount before discount (quantity * unit_price_net, rounded)
        line_discount: Discount amount deducted from line_subtotal (rounded)
    """
    line_net: Decimal
    line_tax: Decimal
    line_gross: Decimal
    line_subtotal: Decimal
    line_discount: Decimal


@dataclass
class TotalsResult:
    """
    Result object containing calculated totals

    Attributes:
        total_net: Total net amount (sum of all line_net, i.e. after discount)
        total_tax: Total tax amount (sum of all line_tax)
        total_gross: Total gross amount (sum of all line_gross)
        total_discount: Total discount amount (sum of all line discount amounts)
    """
    total_net: Decimal
    total_tax: Decimal
    total_gross: Decimal
    total_discount: Decimal = field(default_factory=lambda: Decimal('0.00'))


class DocumentCalculationService:
    """
    Service for calculating document totals based on lines
    
    This service is deterministic and reproduces the same results
    for the same inputs. It uses only Decimal arithmetic (no floats)
    and applies HALF_UP rounding consistently.
    """
    
    # Decimal context for rounding to 2 decimal places
    TWO_PLACES = Decimal('0.01')

    # Discount is a percentage and therefore bounded by 0..100
    MIN_DISCOUNT_PERCENT = Decimal('0.00')
    MAX_DISCOUNT_PERCENT = Decimal('100.00')

    @classmethod
    def effective_discount_percent(cls, line) -> Decimal:
        """
        Determine the discount percentage that actually applies to a line

        A line that is not discountable (is_discountable=False) never carries a
        discount, no matter what is stored in `discount`. Values outside 0..100
        are rejected on input (see views/model validation); should legacy data
        still contain them, they are clamped here so the calculation stays sane.

        Args:
            line: SalesDocumentLine instance

        Returns:
            Decimal: effective discount percentage (0..100)
        """
        if not getattr(line, 'is_discountable', True):
            return cls.MIN_DISCOUNT_PERCENT

        discount = line.discount or cls.MIN_DISCOUNT_PERCENT
        if discount < cls.MIN_DISCOUNT_PERCENT:
            return cls.MIN_DISCOUNT_PERCENT
        if discount > cls.MAX_DISCOUNT_PERCENT:
            return cls.MAX_DISCOUNT_PERCENT
        return discount

    @classmethod
    def calculate_line_totals(cls, line) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate line totals with proper rounding (public method)

        See `calculate_line_amounts()` for the full calculation including the
        discount amount.

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
    def calculate_line_amounts(cls, line) -> LineAmounts:
        """
        Calculate all amounts of a line including the discount (public method)

        Args:
            line: SalesDocumentLine instance

        Returns:
            LineAmounts with subtotal, discount, net, tax and gross
        """
        return cls._calculate_line_amounts(line)

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
            >>> print(f"Discount: {result.total_discount}")
            >>> # To persist the results:
            >>> result = DocumentCalculationService.recalculate(doc, persist=True)
        """
        # Get all lines for the document (ordered by position_no for consistency)
        lines = document.lines.select_related('tax_rate').order_by('position_no')
        
        # Initialize totals
        total_net = Decimal('0.00')
        total_tax = Decimal('0.00')
        total_gross = Decimal('0.00')
        total_discount = Decimal('0.00')

        # Collect lines that need to be saved if persist=True
        lines_to_update = []

        # Process each line
        for line in lines:
            # Calculate line amounts with rounding. Excluded lines are calculated
            # as well, so they don't show stale 0.00 values - they just don't
            # contribute to the document totals.
            amounts = cls._calculate_line_amounts(line)

            # Update line fields in memory
            line.line_net = amounts.line_net
            line.line_tax = amounts.line_tax
            line.line_gross = amounts.line_gross

            # Track line for batch update if persist=True
            if persist:
                lines_to_update.append(line)

            # Apply selection logic: determine if line should be included
            if not cls._is_line_included(line):
                continue

            # Accumulate to document totals (only included lines)
            total_net += amounts.line_net
            total_tax += amounts.line_tax
            total_gross += amounts.line_gross
            total_discount += amounts.line_discount

        # Create result object
        result = TotalsResult(
            total_net=total_net,
            total_tax=total_tax,
            total_gross=total_gross,
            total_discount=total_discount
        )

        # Update document fields (in-memory)
        document.total_net = result.total_net
        document.total_tax = result.total_tax
        document.total_gross = result.total_gross
        document.total_discount = result.total_discount

        # Persist if requested
        if persist:
            # Bulk update all lines with their calculated totals
            # This is more efficient than saving each line individually
            if lines_to_update:
                # Use bulk_update with update_fields for performance
                # Import the model to get the correct class
                from auftragsverwaltung.models import SalesDocumentLine
                SalesDocumentLine.objects.bulk_update(
                    lines_to_update,
                    fields=['line_net', 'line_tax', 'line_gross'],
                    batch_size=100
                )

            # Save document totals
            document.save(update_fields=[
                'total_net', 'total_tax', 'total_gross', 'total_discount'
            ])

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

        Thin wrapper around `_calculate_line_amounts()` for callers that only
        need the three persisted line sums.

        Args:
            line: SalesDocumentLine instance

        Returns:
            tuple: (line_net, line_tax, line_gross) as Decimal values
        """
        amounts = cls._calculate_line_amounts(line)
        return amounts.line_net, amounts.line_tax, amounts.line_gross

    @classmethod
    def _calculate_line_amounts(cls, line) -> LineAmounts:
        """
        Calculate all line amounts with proper rounding

        Calculation steps (order and rounding are part of the contract):
        1. line_subtotal = round(quantity * unit_price_net, 2)   # before discount
        2. line_discount = round(line_subtotal * discount% / 100, 2)
           (discount% is 0 for lines with is_discountable=False)
        3. line_net = line_subtotal - line_discount              # already 2 places
        4. line_tax = round(line_net * tax_rate.rate, 2)         # on the DISCOUNTED net
        5. line_gross = line_net + line_tax

        Rounding is always HALF_UP to 2 decimal places. The discount amount is
        rounded before it is deducted, so line_subtotal = line_net + line_discount
        holds cent-exactly and the printed discount matches the printed amount.

        Args:
            line: SalesDocumentLine instance

        Returns:
            LineAmounts with subtotal, discount, net, tax and gross
        """
        # Step 1: Calculate and round the undiscounted line amount
        line_subtotal = (line.quantity * line.unit_price_net).quantize(
            cls.TWO_PLACES, rounding=ROUND_HALF_UP
        )

        # Step 2: Calculate and round the discount amount
        discount_percent = cls.effective_discount_percent(line)
        if discount_percent:
            line_discount = (
                line_subtotal * discount_percent / Decimal('100')
            ).quantize(cls.TWO_PLACES, rounding=ROUND_HALF_UP)
        else:
            line_discount = Decimal('0.00')

        # Step 3: Net after discount (both operands already rounded)
        line_net = line_subtotal - line_discount

        # Step 4: Calculate and round line_tax on the discounted net
        line_tax = (line_net * line.tax_rate.rate).quantize(
            cls.TWO_PLACES, rounding=ROUND_HALF_UP
        )

        # Step 5: Calculate line_gross (already rounded components)
        line_gross = (line_net + line_tax).quantize(
            cls.TWO_PLACES, rounding=ROUND_HALF_UP
        )

        return LineAmounts(
            line_net=line_net,
            line_tax=line_tax,
            line_gross=line_gross,
            line_subtotal=line_subtotal,
            line_discount=line_discount,
        )

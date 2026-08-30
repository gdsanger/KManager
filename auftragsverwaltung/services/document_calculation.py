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

Rounding contract:
- Net is rounded per line. Every line has to print with a cent-exact amount,
  so `line_net` (and the discount deducted from it) is rounded line by line
  and `total_net` is the sum of those rounded amounts.
- Tax is NOT rounded per line. It is calculated per tax rate on the summed net
  of that rate: `tax = round(sum(line_net of that rate) * rate, 2)`.
  `total_tax` is the sum of these per-rate amounts, `total_gross` is
  `total_net + total_tax`. Rounding each line's tax separately would let the
  half cents pile up in one direction (seven lines of 12.50 EUR at 19 % used to
  yield 38.03 instead of 38.00), so the printed tax no longer matched
  "rate x net" for a customer recomputing the invoice.
- `line_tax`/`line_gross` are still stored and printed per line. To keep them
  consistent with the document totals, the rounding difference of a tax rate
  group is put on exactly ONE line of that group: the one with the largest net
  amount, ties broken by the smallest position_no. That makes the assignment
  deterministic (recalculating a document twice yields identical line amounts)
  and guarantees cent-exactly:
      sum(line_tax) == total_tax  and  sum(line_gross) == total_gross
  The same approach is used by `finanzen.services.datev_export._split_tax()`.
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
        line_tax: Provisional tax amount of this line, rounded on the
            discounted net. `recalculate()` may shift the rounding difference
            of the tax rate group onto one line, so only the value written by
            `recalculate()` is authoritative for a stored line.
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
        total_tax: Total tax amount (sum of the per-tax-rate amounts, each
            rounded on the summed net of that rate)
        total_gross: Total gross amount (total_net + total_tax)
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

    # Tax rates are stored as factors (0.19 = 19 %); 4 places is the precision
    # used to compare them (see core.TaxRate.rate)
    RATE_PLACES = Decimal('0.0001')

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

        Net amounts are rounded per line, the tax is calculated per tax rate on
        the summed net of that rate (see module docstring). The resulting
        rounding difference is put on one line per tax rate group, so the stored
        line amounts always add up to the document totals.

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
        # Get all lines for the document. Ordering by (position_no, pk) makes
        # the calculation - and especially the tie-break when the rounding
        # difference is assigned - fully deterministic.
        lines = document.lines.select_related('tax_rate').order_by('position_no', 'pk')

        # Initialize totals
        total_net = Decimal('0.00')
        total_tax = Decimal('0.00')
        total_discount = Decimal('0.00')

        # Collect lines that need to be saved if persist=True
        lines_to_update = []

        # Included lines grouped by tax rate, so the tax can be calculated on
        # the summed net of each rate instead of line by line.
        tax_groups: dict[Decimal, list] = {}

        # Process each line
        for line in lines:
            # Calculate line amounts with rounding. Excluded lines are calculated
            # as well, so they don't show stale 0.00 values - they just don't
            # contribute to the document totals.
            amounts = cls._calculate_line_amounts(line)

            # Update line fields in memory. For included lines line_tax/line_gross
            # may still be corrected below when the group difference is assigned.
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
            total_discount += amounts.line_discount

            tax_groups.setdefault(cls._rate_key(line), []).append(line)

        # Tax per tax rate on the summed net of that rate (not per line)
        for rate in sorted(tax_groups):
            group_lines = tax_groups[rate]
            group_net = sum(
                (line.line_net for line in group_lines), Decimal('0.00')
            )
            group_tax = (group_net * rate).quantize(
                cls.TWO_PLACES, rounding=ROUND_HALF_UP
            )
            total_tax += group_tax

            # Keep the stored line amounts in sync with the group total
            cls._assign_group_tax(group_lines, group_tax)

        # Gross follows from the rounded totals; this equals sum(line_gross)
        # because the rounding difference was pushed into a line above.
        total_gross = total_net + total_tax

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
    def _rate_key(cls, line) -> Decimal:
        """
        Grouping key of a line's tax rate

        Grouping happens by the rate VALUE, not by the TaxRate row: two tax rate
        records that both stand for 19 % have to end up in one group, otherwise
        the printed "19 % of <net>" block would again be split into separately
        rounded parts. The value is normalised to 4 decimal places so that
        0.19 and 0.1900 are the same key.

        Args:
            line: SalesDocumentLine instance

        Returns:
            Decimal: normalised tax rate (e.g. Decimal('0.1900'))
        """
        rate = line.tax_rate.rate or Decimal('0')
        return rate.quantize(cls.RATE_PLACES)

    @classmethod
    def _assign_group_tax(cls, group_lines, group_tax: Decimal) -> None:
        """
        Distribute the tax of one tax rate group over its lines (in memory)

        The lines already carry their individually rounded `line_tax`. The
        difference to the group's tax - which is the authoritative amount - is
        added to a single line, so that `sum(line_tax) == group_tax` holds
        cent-exactly.

        The carrier line is the one with the largest net amount; on a tie the
        smallest position_no wins. Both criteria come from stored data only, so
        recalculating the same document again picks the same line. This mirrors
        `finanzen.services.datev_export._split_tax()`, which puts the rounding
        difference into the largest taxable bucket.

        Args:
            group_lines: lines of one tax rate (already carrying line_net/line_tax)
            group_tax: tax amount of the group, rounded on the summed net
        """
        difference = group_tax - sum(
            (line.line_tax for line in group_lines), Decimal('0.00')
        )
        if difference == Decimal('0.00'):
            return

        carrier = min(group_lines, key=cls._carrier_sort_key)
        carrier.line_tax = carrier.line_tax + difference
        carrier.line_gross = carrier.line_net + carrier.line_tax

    @staticmethod
    def _carrier_sort_key(line) -> tuple:
        """
        Sort key selecting the line that carries the rounding difference

        Sorted ascending, the first line is the one with the largest net amount
        (hence the negated absolute value) and, on a tie, the smallest
        position_no. The primary key is the final tie-break so that two lines
        with the same amount and the same position_no still resolve
        deterministically.
        """
        return (
            -abs(line.line_net),
            line.position_no if line.position_no is not None else 0,
            line.pk or 0,
        )

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

        Steps 4 and 5 give a PROVISIONAL tax for a single line, used where a
        line is calculated in isolation (e.g. the inline edit in the position
        grid). The document's tax is not the sum of these values: `recalculate()`
        computes it per tax rate on the summed net and then corrects one line per
        rate by the rounding difference (see module docstring).

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

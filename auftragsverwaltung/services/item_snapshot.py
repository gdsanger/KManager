"""
Item Snapshot Service

Provides snapshot functionality for copying Item master data to SalesDocumentLine.
When an item is selected for a document line, relevant values are copied as a snapshot
to ensure that existing documents remain historically stable even if the item master data changes.

Business Rules:
- Snapshot is applied when item is set on a line
- Changes to Item master data do NOT affect existing lines (snapshot stability)
- Service is UI-independent and can be called from UI and background jobs
"""


def apply_item_snapshot(line, item):
    """
    Apply item snapshot to a sales document line
    
    Copies relevant values from the Item master data to the SalesDocumentLine
    as a snapshot. This ensures that changes to the Item do not retroactively
    affect existing document lines.
    
    Fields copied from Item to Line:
    - unit_price_net = item.net_price
    - tax_rate = item.tax_rate
    - is_discountable = item.is_discountable
    
    Note: Description fields (short_text_1, short_text_2, long_text) are not
    automatically copied as per issue requirements. This will be handled in a
    future issue.
    
    Note: cost_type_1 and cost_type_2 are not copied because SalesDocumentLine
    does not have these fields. Cost types are managed at the Item level only.
    
    Args:
        line: SalesDocumentLine instance (must be a Django model instance)
        item: Item instance (must be a Django model instance or None)
        
    Returns:
        None - modifies line in-place (does NOT save to database)
        
    Example:
        >>> from auftragsverwaltung.models import SalesDocumentLine
        >>> from core.models import Item
        >>> from auftragsverwaltung.services.item_snapshot import apply_item_snapshot
        >>> 
        >>> item = Item.objects.get(article_no="ART-001")
        >>> line = SalesDocumentLine(document=doc, position_no=1, ...)
        >>> line.item = item
        >>> apply_item_snapshot(line, item)
        >>> line.save()  # Caller is responsible for saving
    """
    if item is None:
        # If item is None, do nothing (as per issue requirements)
        # The line keeps its current values
        return
    
    # Copy snapshot fields from item to line
    line.unit_price_net = item.net_price
    line.tax_rate = item.tax_rate
    line.is_discountable = item.is_discountable
    
    # Note: This service does NOT save the line to the database.
    # The caller is responsible for calling line.save() after applying the snapshot.

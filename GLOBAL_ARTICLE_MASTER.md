# Global Article Master Data (Item) - Technical Documentation

## Overview

The global article master data (`core.Item`) provides a central repository for managing articles and services that can be reused across sales documents (quotes, invoices, contracts). When an item is selected in a document line, its values are copied as a **snapshot** to ensure historical stability of existing documents.

## Architecture

### Data Model

The `Item` model (`core.models.Item`) represents the global article master data with the following key features:

- **Global Uniqueness**: Each article is identified by a globally unique `article_no`
- **Classification**: Items are categorized as either `MATERIAL` or `SERVICE` via `item_type`
- **Pricing**: Contains both `net_price` (sales) and `purchase_price` (cost)
- **Tax Integration**: References a `TaxRate` for VAT calculations
- **Cost Accounting**: Supports up to two cost types (`cost_type_1`, `cost_type_2`) for accounting purposes

#### Key Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `article_no` | String | Yes | Globally unique article identifier |
| `short_text_1` | String | Yes | Primary short description |
| `short_text_2` | String | No | Optional secondary short description |
| `long_text` | Text | No | Detailed description |
| `net_price` | Decimal | Yes | Sales price (net, >= 0) |
| `purchase_price` | Decimal | Yes | Cost price (net, >= 0) |
| `tax_rate` | FK | Yes | Reference to TaxRate |
| `cost_type_1` | FK | Yes | Primary cost type |
| `cost_type_2` | FK | No | Optional secondary cost type |
| `item_type` | Choice | Yes | MATERIAL or SERVICE |
| `is_discountable` | Boolean | Yes | Whether discounts apply (default: true) |
| `is_active` | Boolean | Yes | Active status (default: true) |

#### Constraints

- **Uniqueness**: `article_no` must be globally unique
- **Price Validation**: Both `net_price` and `purchase_price` must be >= 0
- **Referential Integrity**: Items cannot be deleted if referenced by sales document lines

### Snapshot Principle

The snapshot principle ensures that existing sales documents remain **historically stable** when item master data changes.

#### How It Works

1. **Item Selection**: When an item is assigned to a `SalesDocumentLine`, the snapshot service is called
2. **Snapshot Copy**: Relevant values from the `Item` are copied to the line:
   - `unit_price_net` = `item.net_price`
   - `tax_rate` = `item.tax_rate`
   - `is_discountable` = `item.is_discountable`
3. **Historical Stability**: After the snapshot is created, the line is independent of the item master data
4. **No Retroactive Changes**: Changes to the `Item` do NOT affect existing lines

#### Snapshot Service

The snapshot logic is implemented in `auftragsverwaltung.services.item_snapshot`:

```python
from auftragsverwaltung.services.item_snapshot import apply_item_snapshot

# Example usage
line.item = item
apply_item_snapshot(line, item)
line.save()  # Caller is responsible for saving
```

**Important**: The service does NOT save the line to the database. The caller must explicitly call `save()`.

#### Fields NOT in Snapshot

The following fields are intentionally NOT copied during snapshot:

- **Description fields** (`short_text_1`, `short_text_2`, `long_text`): Description handling will be addressed in a future issue
- **Cost types** (`cost_type_1`, `cost_type_2`): Not present on `SalesDocumentLine`, managed at item level only

### Integration with Sales Documents

The `SalesDocumentLine` model has a nullable foreign key to `Item`:

```python
item = models.ForeignKey(
    'core.Item',
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name='sales_document_lines',
    verbose_name="Artikel/Leistung"
)
```

- **Nullable**: Lines can exist without an item (e.g., for free-text positions)
- **Protected**: Items cannot be deleted if referenced by lines
- **Optional**: Not all lines must reference an item

## Usage Patterns

### Creating an Item

```python
from core.models import Item, TaxRate, Kostenart

# Get references
tax_rate = TaxRate.objects.get(code="VAT")
cost_type = Kostenart.objects.get(name="Material")

# Create item
item = Item.objects.create(
    article_no="ART-12345",
    short_text_1="Premium Widget",
    short_text_2="Type A",
    long_text="High-quality widget for industrial use",
    net_price=Decimal("99.99"),
    purchase_price=Decimal("50.00"),
    tax_rate=tax_rate,
    cost_type_1=cost_type,
    item_type="MATERIAL",
    is_discountable=True,
    is_active=True
)
```

### Using an Item in a Document Line

```python
from auftragsverwaltung.models import SalesDocumentLine
from auftragsverwaltung.services.item_snapshot import apply_item_snapshot

# Create line and apply snapshot
line = SalesDocumentLine(
    document=document,
    position_no=1,
    line_type="NORMAL",
    is_selected=True,
    description="Premium Widget",
    quantity=Decimal("5.0000"),
    unit_price_net=Decimal("0.00"),  # Will be set by snapshot
    tax_rate=some_default_tax_rate  # Will be overwritten by snapshot
)

# Set item and apply snapshot
line.item = item
apply_item_snapshot(line, item)

# Save the line
line.save()
```

### Updating Item Master Data

```python
# Updating an item does NOT affect existing document lines
item.net_price = Decimal("109.99")
item.save()

# Existing lines keep their original snapshot values
# New lines will use the updated price
```

## Admin Interface

Items can be managed via Django Admin:

- **List View**: Displays `article_no`, `short_text_1`, `item_type`, `net_price`, `tax_rate`, `is_discountable`, `is_active`
- **Filters**: By `item_type`, `is_active`, `is_discountable`, `tax_rate`
- **Search**: By `article_no`, `short_text_1`, `short_text_2`, `long_text`
- **Deletion**: Prevented if item is referenced by sales document lines (use `is_active=False` instead)

## Out of Scope

The following features are explicitly OUT OF SCOPE for this implementation:

- Inventory/stock management
- Price tiers or volume-based pricing
- Company-specific or customer-specific pricing
- Product variants or bundles
- Price change history/audit trail
- Automatic text composition for document lines

## Database Migrations

- **Migration 0018**: Extends the stub `Item` model with full article master data fields

## Testing

Comprehensive tests are provided in `core.test_item`:

- Model validation (uniqueness, price constraints)
- Snapshot service functionality
- Historical stability verification
- Edge cases (None item, zero prices)

Run tests:
```bash
python manage.py test core.test_item
```

## Project Standards Compliance

This implementation follows project standards:

- **No Logic in `Model.save()`**: Snapshot logic is in a service, not in model save methods
- **Service Pattern**: Uses deterministic service functions (`apply_item_snapshot`)
- **Snapshot Principle**: Existing documents remain stable when master data changes
- **Validation**: Uses Django's `clean()` method for model validation
- **Constraints**: Uses database constraints for data integrity

## Future Enhancements

Planned for future issues:

- Description text handling in document lines
- Behavior when `item` is set to `NULL` on an existing line
- Additional item metadata (units of measure, categories, etc.)

## References

- Issue #276: Global Article Master Data Implementation
- Issue #266: Document Positions (Snapshot Principle)
- Issue #268: Document Calculation Service (Service Pattern)
- Issue #261: Tax Rate Entity

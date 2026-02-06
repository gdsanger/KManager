# TaxRate FK Integration Guide

## Overview
The `core.TaxRate` model is designed to be referenced by other domain models via ForeignKey relationships. This document explains how to integrate TaxRate into your models.

## Status
**As of this implementation:**
- ✅ `core.TaxRate` model exists and is fully functional
- ❌ `Item` model does not exist yet (will be created in a future issue)
- ❌ `SalesDocumentLine` model does not exist yet (will be created in a future issue)

## How to Add TaxRate FK to Your Model

When creating models like `Item` or `SalesDocumentLine` in future issues, add the TaxRate ForeignKey as follows:

### Example: Item Model
```python
from django.db import models
from core.models import TaxRate

class Item(models.Model):
    """Item/Product model"""
    name = models.CharField(max_length=200, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    
    # TaxRate ForeignKey
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,  # Prevent deletion of TaxRate if referenced
        null=True,  # Make optional if needed
        blank=True,
        verbose_name="Steuersatz",
        help_text="Zugeordneter Steuersatz"
    )
    
    class Meta:
        verbose_name = "Artikel"
        verbose_name_plural = "Artikel"
    
    def __str__(self):
        return self.name
```

### Example: SalesDocumentLine Model
```python
from django.db import models
from decimal import Decimal
from core.models import TaxRate

class SalesDocumentLine(models.Model):
    """Sales document line item"""
    description = models.CharField(max_length=200, verbose_name="Beschreibung")
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Menge")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Einzelpreis")
    
    # TaxRate ForeignKey
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.PROTECT,  # Prevent deletion of TaxRate if referenced
        verbose_name="Steuersatz",
        help_text="Steuersatz für diese Position"
    )
    
    class Meta:
        verbose_name = "Verkaufsdokument Position"
        verbose_name_plural = "Verkaufsdokument Positionen"
    
    @property
    def net_amount(self):
        """Calculate net amount (quantity * unit_price)"""
        return Decimal(self.quantity) * Decimal(self.unit_price)
    
    @property
    def tax_amount(self):
        """Calculate tax amount"""
        return self.net_amount * self.tax_rate.rate
    
    @property
    def gross_amount(self):
        """Calculate gross amount (net + tax)"""
        return self.net_amount + self.tax_amount
```

## Important Design Decisions

### Delete Protection (PROTECT)
- **TaxRate instances CANNOT be deleted** if they are referenced by other models
- Use `on_delete=models.PROTECT` in all FK relationships
- To "remove" a TaxRate, set `is_active=False` instead

### Active vs Inactive Tax Rates
- Inactive tax rates (`is_active=False`) remain in the database
- They can still be referenced by existing records
- UI should filter to show only active rates for new selections

### Migration Strategy
When adding the FK field to existing models:
1. Add the field with `null=True` initially
2. Optionally populate existing records with a default TaxRate
3. If required, change to `null=False` in a subsequent migration

## Admin Integration
When registering your model in admin.py, the TaxRate FK will automatically work with Django's admin interface:

```python
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_rate', 'is_active')
    list_filter = ('tax_rate', 'is_active')
    search_fields = ('name', 'description')
    
    # Optional: Filter to show only active tax rates in dropdowns
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "tax_rate":
            kwargs["queryset"] = TaxRate.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

## Testing FK Relationships
When writing tests for models with TaxRate FKs:

```python
from decimal import Decimal
from core.models import TaxRate

class ItemTestCase(TestCase):
    def setUp(self):
        """Create test TaxRate"""
        self.tax_rate = TaxRate.objects.create(
            code="VAT19",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
    
    def test_create_item_with_tax_rate(self):
        """Test creating item with TaxRate FK"""
        item = Item.objects.create(
            name="Test Item",
            tax_rate=self.tax_rate
        )
        
        self.assertEqual(item.tax_rate, self.tax_rate)
        self.assertEqual(item.tax_rate.rate, Decimal("0.19"))
```

## See Also
- `core/models.py` - TaxRate model definition
- `core/admin.py` - TaxRate admin interface
- `core/test_taxrate.py` - TaxRate model tests
- `core/test_taxrate_fk.py` - FK relationship tests

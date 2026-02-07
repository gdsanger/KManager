#!/usr/bin/env python
"""
Manual test script for Kostenart filtering functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
django.setup()

from core.models import Item, Kostenart, TaxRate, ItemGroup
from core.forms import ItemForm
from decimal import Decimal


def test_kostenart_filtering():
    """Test the Kostenart filtering functionality"""
    
    print("=" * 80)
    print("TESTING KOSTENART FILTERING IN ITEM FORM")
    print("=" * 80)
    
    # Get test data
    tax_rate = TaxRate.objects.get(code='VAT19')
    item_group = ItemGroup.objects.get(code='SUB')
    
    # Get Kostenarten
    personal = Kostenart.objects.get(name='Personal')
    material = Kostenart.objects.get(name='Material')
    gehaelter = Kostenart.objects.get(name='Gehälter')
    rohstoffe = Kostenart.objects.get(name='Rohstoffe')
    
    print("\n1. TEST: Cost_type_1 queryset only contains Hauptkostenarten")
    print("-" * 80)
    form = ItemForm()
    cost_type_1_qs = form.fields['cost_type_1'].queryset
    print(f"Cost_type_1 queryset count: {cost_type_1_qs.count()}")
    print("Cost_type_1 options:")
    for kt in cost_type_1_qs:
        print(f"  - {kt.name} (parent: {kt.parent})")
    
    assert all(kt.parent is None for kt in cost_type_1_qs), "ERROR: Cost_type_1 contains Unterkostenarten!"
    print("✓ PASS: Cost_type_1 only contains Hauptkostenarten\n")
    
    print("2. TEST: Cost_type_2 is empty when no cost_type_1 is selected")
    print("-" * 80)
    cost_type_2_qs = form.fields['cost_type_2'].queryset
    print(f"Cost_type_2 queryset count (no cost_type_1): {cost_type_2_qs.count()}")
    assert cost_type_2_qs.count() == 0, "ERROR: Cost_type_2 should be empty!"
    print("✓ PASS: Cost_type_2 is empty\n")
    
    print("3. TEST: Create valid item with Hauptkostenart and Unterkostenart")
    print("-" * 80)
    data = {
        'article_no': 'TEST-001',
        'short_text_1': 'Test Article',
        'net_price': Decimal('100.00'),
        'purchase_price': Decimal('50.00'),
        'tax_rate': tax_rate.pk,
        'cost_type_1': personal.pk,
        'cost_type_2': gehaelter.pk,
        'item_group': item_group.pk,
        'item_type': 'SERVICE',
        'is_active': True,
    }
    
    form = ItemForm(data=data)
    print(f"Form is valid: {form.is_valid()}")
    if not form.is_valid():
        print("ERRORS:", form.errors)
        assert False, "Form should be valid!"
    
    # Check that cost_type_2 queryset was filtered
    cost_type_2_qs = form.fields['cost_type_2'].queryset
    print(f"Cost_type_2 queryset count (cost_type_1=Personal): {cost_type_2_qs.count()}")
    print("Cost_type_2 options:")
    for kt in cost_type_2_qs:
        print(f"  - {kt.name} (parent: {kt.parent.name if kt.parent else None})")
    
    # Save the item
    item = form.save()
    print(f"✓ PASS: Created item '{item.article_no}' with:")
    print(f"  - Cost_type_1: {item.cost_type_1.name}")
    print(f"  - Cost_type_2: {item.cost_type_2.name if item.cost_type_2 else None}\n")
    
    print("4. TEST: Edit mode - cost_type_2 is filtered by saved cost_type_1")
    print("-" * 80)
    edit_form = ItemForm(instance=item)
    cost_type_2_qs = edit_form.fields['cost_type_2'].queryset
    print(f"Cost_type_2 queryset count in edit mode: {cost_type_2_qs.count()}")
    print("Cost_type_2 options in edit mode:")
    for kt in cost_type_2_qs:
        print(f"  - {kt.name} (parent: {kt.parent.name if kt.parent else None})")
    
    assert all(kt.parent == personal for kt in cost_type_2_qs), "ERROR: Cost_type_2 not filtered correctly!"
    print("✓ PASS: Cost_type_2 correctly filtered in edit mode\n")
    
    print("5. TEST: Validation - Unterkostenart cannot be selected as cost_type_1")
    print("-" * 80)
    data['article_no'] = 'TEST-002'
    data['cost_type_1'] = gehaelter.pk  # Unterkostenart - should fail
    form = ItemForm(data=data)
    print(f"Form is valid: {form.is_valid()}")
    if form.is_valid():
        print("ERROR: Form should be invalid!")
        assert False
    print(f"Validation errors: {form.errors.get('cost_type_1', [])}")
    print("✓ PASS: Unterkostenart rejected for cost_type_1\n")
    
    print("6. TEST: Validation - cost_type_2 must be child of cost_type_1")
    print("-" * 80)
    data['article_no'] = 'TEST-003'
    data['cost_type_1'] = personal.pk
    data['cost_type_2'] = rohstoffe.pk  # Child of Material, not Personal - should fail
    form = ItemForm(data=data)
    print(f"Form is valid: {form.is_valid()}")
    if form.is_valid():
        print("ERROR: Form should be invalid!")
        assert False
    print(f"Validation errors: {form.errors.get('cost_type_2', [])}")
    print("✓ PASS: Mismatched cost_type_2 rejected\n")
    
    print("7. TEST: cost_type_2 is optional")
    print("-" * 80)
    data['article_no'] = 'TEST-004'
    data['cost_type_1'] = material.pk
    del data['cost_type_2']  # No cost_type_2
    form = ItemForm(data=data)
    print(f"Form is valid: {form.is_valid()}")
    if not form.is_valid():
        print("ERRORS:", form.errors)
        assert False, "Form should be valid without cost_type_2!"
    
    item2 = form.save()
    print(f"✓ PASS: Created item '{item2.article_no}' with:")
    print(f"  - Cost_type_1: {item2.cost_type_1.name}")
    print(f"  - Cost_type_2: {item2.cost_type_2}\n")
    
    # Cleanup
    item.delete()
    item2.delete()
    
    print("=" * 80)
    print("ALL TESTS PASSED! ✓")
    print("=" * 80)


if __name__ == '__main__':
    test_kostenart_filtering()

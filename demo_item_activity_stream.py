#!/usr/bin/env python
"""
Demonstration of Item ActivityStream Integration

This script demonstrates the activity logging for item management:
- Creating items logs ITEM_CREATED
- Updating items logs ITEM_UPDATED
- Changing status logs ITEM_STATUS_CHANGED

Note: This is a demonstration script showing how the integration works.
In practice, the activity logging happens automatically when items are
saved through the item_save_ajax view.
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
django.setup()

from django.contrib.auth import get_user_model
from decimal import Decimal
from core.models import Item, Mandant, TaxRate, Kostenart, Activity
from core.forms import ItemForm

User = get_user_model()

def demo():
    """Run demonstration"""
    print("=" * 80)
    print("ITEM ACTIVITYSTREAM INTEGRATION DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Setup test data
    print("Setting up test data...")
    
    # Get or create company
    company, _ = Mandant.objects.get_or_create(
        name='Demo Company GmbH',
        defaults={
            'adresse': 'Demostraße 1',
            'plz': '12345',
            'ort': 'Demostadt'
        }
    )
    print(f"✓ Company: {company.name}")
    
    # Get or create user
    user, _ = User.objects.get_or_create(
        username='demo_user',
        defaults={
            'email': 'demo@example.com'
        }
    )
    print(f"✓ User: {user.username}")
    
    # Get or create tax rate
    tax_rate, _ = TaxRate.objects.get_or_create(
        code='VAT19',
        defaults={
            'name': 'Standard VAT',
            'rate': Decimal('0.19')
        }
    )
    print(f"✓ Tax Rate: {tax_rate.name}")
    
    # Get or create cost type
    cost_type, _ = Kostenart.objects.get_or_create(
        name='Material',
        defaults={'umsatzsteuer_satz': '19'}
    )
    print(f"✓ Cost Type: {cost_type.name}")
    print()
    
    # Clear old test items and activities
    print("Cleaning up old test data...")
    Item.objects.filter(article_no__startswith='DEMO-').delete()
    Activity.objects.filter(activity_type__startswith='ITEM_').delete()
    print("✓ Cleanup complete")
    print()
    
    # Demonstration 1: Create Item
    print("-" * 80)
    print("DEMO 1: Creating a new item")
    print("-" * 80)
    
    item = Item.objects.create(
        article_no='DEMO-001',
        short_text_1='Demo Article 1',
        short_text_2='Second line',
        long_text='This is a demonstration item',
        net_price=Decimal('100.00'),
        purchase_price=Decimal('50.00'),
        tax_rate=tax_rate,
        cost_type_1=cost_type,
        item_type='MATERIAL',
        is_active=True
    )
    print(f"✓ Created item: {item.article_no}")
    
    # Manually log activity (simulating what the view does)
    from core.services.activity_stream import ActivityStreamService
    ActivityStreamService.add(
        company=company,
        domain='ORDER',
        activity_type='ITEM_CREATED',
        title=f'Artikel erstellt: {item.article_no}',
        description=f'{item.short_text_1}',
        target_url=f'/items/?selected={item.pk}',
        actor=user,
        severity='INFO'
    )
    
    # Show activity
    activity = Activity.objects.filter(activity_type='ITEM_CREATED').latest('created_at')
    print(f"\n✓ Activity logged:")
    print(f"  Type: {activity.activity_type}")
    print(f"  Title: {activity.title}")
    print(f"  Description: {activity.description}")
    print(f"  Actor: {activity.actor.username}")
    print(f"  URL: {activity.target_url}")
    print()
    
    # Demonstration 2: Update Item
    print("-" * 80)
    print("DEMO 2: Updating an item")
    print("-" * 80)
    
    item.short_text_1 = 'Updated Demo Article 1'
    item.net_price = Decimal('120.00')
    item.save()
    print(f"✓ Updated item: {item.article_no}")
    print(f"  New text: {item.short_text_1}")
    print(f"  New price: {item.net_price}")
    
    # Manually log activity (simulating what the view does)
    ActivityStreamService.add(
        company=company,
        domain='ORDER',
        activity_type='ITEM_UPDATED',
        title=f'Artikel aktualisiert: {item.article_no}',
        description=f'{item.short_text_1}',
        target_url=f'/items/?selected={item.pk}',
        actor=user,
        severity='INFO'
    )
    
    # Show activity
    activity = Activity.objects.filter(activity_type='ITEM_UPDATED').latest('created_at')
    print(f"\n✓ Activity logged:")
    print(f"  Type: {activity.activity_type}")
    print(f"  Title: {activity.title}")
    print(f"  Description: {activity.description}")
    print()
    
    # Demonstration 3: Change Status
    print("-" * 80)
    print("DEMO 3: Changing item status")
    print("-" * 80)
    
    old_status = 'aktiv' if item.is_active else 'inaktiv'
    item.is_active = False
    item.save()
    status_action = 'deaktiviert' if not item.is_active else 'aktiviert'
    print(f"✓ Changed status: {item.article_no}")
    print(f"  Old status: {old_status}")
    print(f"  Action: {status_action}")
    
    # Manually log activity (simulating what the view does)
    ActivityStreamService.add(
        company=company,
        domain='ORDER',
        activity_type='ITEM_STATUS_CHANGED',
        title=f'Artikel-Status geändert: {item.article_no}',
        description=f'Status: {status_action} (vorher: {old_status})',
        target_url=f'/items/?selected={item.pk}',
        actor=user,
        severity='INFO'
    )
    
    # Show activity
    activity = Activity.objects.filter(activity_type='ITEM_STATUS_CHANGED').latest('created_at')
    print(f"\n✓ Activity logged:")
    print(f"  Type: {activity.activity_type}")
    print(f"  Title: {activity.title}")
    print(f"  Description: {activity.description}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY: All Item Activities")
    print("=" * 80)
    
    item_activities = Activity.objects.filter(
        activity_type__startswith='ITEM_'
    ).order_by('-created_at')
    
    print(f"\nTotal activities logged: {item_activities.count()}")
    print()
    
    for i, act in enumerate(item_activities, 1):
        print(f"{i}. {act.activity_type}")
        print(f"   Title: {act.title}")
        print(f"   Description: {act.description}")
        print(f"   Actor: {act.actor.username if act.actor else 'System'}")
        print(f"   Time: {act.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    demo()

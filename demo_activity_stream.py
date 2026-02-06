#!/usr/bin/env python
"""
Demo script for Activity Stream Service

This demonstrates how to use the Activity Stream to log events.
Run with: python demo_activity_stream.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Mandant
from core.services.activity_stream import ActivityStreamService


def main():
    print("=" * 70)
    print("Activity Stream Service Demo")
    print("=" * 70)
    
    # Get or create a test company
    company, created = Mandant.objects.get_or_create(
        name='Demo Company',
        defaults={
            'adresse': 'Teststraße 1',
            'plz': '12345',
            'ort': 'Teststadt'
        }
    )
    print(f"\n✓ Using company: {company.name}")
    
    # Get or create a test user
    user, created = User.objects.get_or_create(
        username='demouser',
        defaults={'email': 'demo@example.com'}
    )
    print(f"✓ Using user: {user.username}")
    
    print("\n" + "-" * 70)
    print("Creating Activity Entries")
    print("-" * 70)
    
    # Example 1: Simple activity (minimal parameters)
    activity1 = ActivityStreamService.add(
        company=company,
        domain='RENTAL',
        activity_type='CONTRACT_CREATED',
        title='Neuer Mietvertrag erstellt',
        target_url='/vermietung/vertraege/123'
    )
    print(f"\n1. Created: {activity1.title}")
    print(f"   - Domain: {activity1.get_domain_display()}")
    print(f"   - Severity: {activity1.get_severity_display()}")
    print(f"   - Target: {activity1.target_url}")
    
    # Example 2: Activity with all parameters
    activity2 = ActivityStreamService.add(
        company=company,
        domain='ORDER',
        activity_type='INVOICE_CREATED',
        title='Rechnung Nr. 2024-001 erstellt',
        description='Rechnung für Projekt ABC wurde erfolgreich erstellt und versendet',
        target_url='/auftragsverwaltung/documents/456',
        actor=user,
        severity='INFO'
    )
    print(f"\n2. Created: {activity2.title}")
    print(f"   - Description: {activity2.description}")
    print(f"   - Actor: {activity2.actor.username if activity2.actor else 'N/A'}")
    
    # Example 3: Warning activity
    activity3 = ActivityStreamService.add(
        company=company,
        domain='FINANCE',
        activity_type='PAYMENT_DELAYED',
        title='Zahlung überfällig',
        description='Zahlungseingang für Rechnung 2024-001 ist überfällig',
        target_url='/finanzen/zahlungen/789',
        actor=user,
        severity='WARNING'
    )
    print(f"\n3. Created: {activity3.title}")
    print(f"   - Severity: {activity3.get_severity_display()}")
    
    # Example 4: Error activity
    activity4 = ActivityStreamService.add(
        company=company,
        domain='ORDER',
        activity_type='CONTRACT_RUN_FAILED',
        title='Vertragsabrechnung fehlgeschlagen',
        description='Automatische Abrechnung konnte nicht durchgeführt werden',
        target_url='/auftragsverwaltung/contracts/101',
        severity='ERROR'
    )
    print(f"\n4. Created: {activity4.title}")
    print(f"   - Severity: {activity4.get_severity_display()}")
    
    print("\n" + "-" * 70)
    print("Retrieving Activity Entries")
    print("-" * 70)
    
    # Get latest activities (default: 20)
    print("\n▸ Latest activities (all):")
    latest_all = ActivityStreamService.latest(n=10)
    for i, activity in enumerate(latest_all, 1):
        print(f"   {i}. [{activity.get_severity_display()}] {activity.title}")
    
    # Filter by domain
    print("\n▸ Latest ORDER activities:")
    order_activities = ActivityStreamService.latest(domain='ORDER', n=10)
    for i, activity in enumerate(order_activities, 1):
        print(f"   {i}. {activity.title}")
    
    # Filter by company and domain
    print("\n▸ Latest RENTAL activities for Demo Company:")
    rental_activities = ActivityStreamService.latest(
        company=company,
        domain='RENTAL',
        n=10
    )
    for i, activity in enumerate(rental_activities, 1):
        print(f"   {i}. {activity.title}")
    
    print("\n" + "=" * 70)
    print("Demo completed successfully!")
    print("=" * 70)
    print("\nNotes:")
    print("- Activities are stored in the database")
    print("- They can be viewed in Django Admin at /admin/core/activity/")
    print("- Activities are read-only (cannot be edited or deleted)")
    print("- Use ActivityStreamService.add() to log new activities")
    print("- Use ActivityStreamService.latest() to retrieve activities")
    print()


if __name__ == '__main__':
    main()

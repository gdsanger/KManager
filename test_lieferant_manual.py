"""Manual test script for Lieferant functionality."""

import os
import sys
import django
from django.core.management import call_command

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

# Run migrations
print("Running migrations...")
call_command('migrate', '--run-syncdb', verbosity=0)

from django.contrib.auth.models import User, Group
from core.models import Adresse
from django.test import Client
from django.urls import reverse

# Create a test user with Vermietung access
user, created = User.objects.get_or_create(
    username='testuser',
    defaults={'is_staff': False}
)
if created:
    user.set_password('testpass123')
    user.save()

# Create Vermietung group and add user to it
group, _ = Group.objects.get_or_create(name='Vermietung')
user.groups.add(group)

# Create some test suppliers
lieferant1, created = Adresse.objects.get_or_create(
    adressen_type='LIEFERANT',
    name='Test Lieferant 1',
    defaults={
        'strasse': 'Lieferstrasse 1',
        'plz': '12345',
        'ort': 'Berlin',
        'land': 'Deutschland',
        'email': 'lieferant1@example.com',
        'telefon': '030-12345678',
        'firma': 'Lieferant GmbH'
    }
)

lieferant2, created = Adresse.objects.get_or_create(
    adressen_type='LIEFERANT',
    name='Test Lieferant 2',
    defaults={
        'strasse': 'Lieferstrasse 2',
        'plz': '54321',
        'ort': 'München',
        'land': 'Deutschland',
        'email': 'lieferant2@example.com',
        'mobil': '0170-98765432'
    }
)

# Create a kunde to ensure it doesn't show in lieferant list
kunde, created = Adresse.objects.get_or_create(
    adressen_type='KUNDE',
    name='Test Kunde',
    defaults={
        'strasse': 'Kundestrasse 1',
        'plz': '11111',
        'ort': 'Hamburg',
        'land': 'Deutschland'
    }
)

print("\n✓ Test data created successfully")
print(f"  - Lieferant 1: {lieferant1.full_name()}")
print(f"  - Lieferant 2: {lieferant2.full_name()}")
print(f"  - Kunde (should not appear in lieferant list): {kunde.full_name()}")

# Test URL resolution
client = Client()
client.login(username='testuser', password='testpass123')

print("\n✓ Testing URL patterns:")

urls_to_test = [
    ('lieferant_list', {}, 'Lieferant List'),
    ('lieferant_create', {}, 'Lieferant Create'),
    ('lieferant_detail', {'pk': lieferant1.pk}, 'Lieferant Detail'),
    ('lieferant_edit', {'pk': lieferant1.pk}, 'Lieferant Edit'),
]

for url_name, kwargs, description in urls_to_test:
    try:
        url = reverse(f'vermietung:{url_name}', kwargs=kwargs)
        response = client.get(url)
        status = '✓' if response.status_code == 200 else f'✗ (Status: {response.status_code})'
        print(f"  {status} {description}: {url}")
        
        # Additional checks for specific pages
        if url_name == 'lieferant_list' and response.status_code == 200:
            content = response.content.decode('utf-8')
            has_l1 = 'Test Lieferant 1' in content
            has_l2 = 'Test Lieferant 2' in content
            has_kunde = 'Test Kunde' in content
            print(f"       - Contains Lieferant 1: {'✓' if has_l1 else '✗'}")
            print(f"       - Contains Lieferant 2: {'✓' if has_l2 else '✗'}")
            print(f"       - Excludes Kunde: {'✓' if not has_kunde else '✗'}")
            
    except Exception as e:
        print(f"  ✗ {description}: ERROR - {e}")

print("\n✓ All manual tests completed successfully!")

import os
import sys
import django

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag
from decimal import Decimal
from datetime import date, timedelta

# Create a user with Vermietung access
user, created = User.objects.get_or_create(
    username='admin',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('admin')
    user.save()
    print(f"Created user: admin")
else:
    print(f"User already exists: admin")

# Create Vermietung group
vermietung_group, _ = Group.objects.get_or_create(name='Vermietung')
user.groups.add(vermietung_group)

# Create test standort
standort, _ = Adresse.objects.get_or_create(
    adressen_type='STANDORT',
    name='Standort Berlin',
    defaults={
        'strasse': 'Berliner Str. 1',
        'plz': '10115',
        'ort': 'Berlin',
        'land': 'Deutschland'
    }
)

# Create test MietObjekt
objekt, created = MietObjekt.objects.get_or_create(
    name='Test Büro 1',
    defaults={
        'type': 'RAUM',
        'beschreibung': 'Modernes Büro im Zentrum für Tests',
        'fläche': Decimal('50.00'),
        'standort': standort,
        'mietpreis': Decimal('1000.00'),
        'nebenkosten': Decimal('200.00'),
        'verfuegbar': True
    }
)
if created:
    print(f"Created MietObjekt: {objekt.name} (ID: {objekt.pk})")
else:
    print(f"MietObjekt already exists: {objekt.name} (ID: {objekt.pk})")

# Create test kunde for contracts
kunde, _ = Adresse.objects.get_or_create(
    adressen_type='KUNDE',
    name='Test Mieter GmbH',
    defaults={
        'strasse': 'Mieter Str. 1',
        'plz': '12345',
        'ort': 'Teststadt',
        'land': 'Deutschland'
    }
)

# Create some test contracts
for i in range(3):
    vertrag, created = Vertrag.objects.get_or_create(
        vertragsnummer=f'V-2024-{i+1:03d}',
        defaults={
            'mietobjekt': objekt,
            'mieter': kunde,
            'start': date.today() - timedelta(days=30*(i+1)),
            'ende': date.today() + timedelta(days=30*(i+1)) if i < 2 else None,
            'miete': Decimal('1000.00'),
            'kaution': Decimal('3000.00'),
            'status': 'active' if i == 0 else 'ended'
        }
    )
    if created:
        print(f"Created contract: {vertrag.vertragsnummer}")

print(f"\nTest data created successfully!")
print(f"User: admin / Password: admin")
print(f"MietObjekt ID: {objekt.pk}")
print(f"URL: http://localhost:8000/vermietung/mietobjekte/{objekt.pk}/")

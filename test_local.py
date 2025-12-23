import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')

import django
django.setup()

from django.contrib.auth.models import User, Group
from core.models import Adresse
from vermietung.models import MietObjekt
from decimal import Decimal

# Create admin user
try:
    admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print(f"Created admin user: {admin.username}")
except Exception as e:
    print(f"Admin user already exists or error: {e}")

# Create Vermietung group and user
try:
    group = Group.objects.create(name='Vermietung')
    print(f"Created group: {group.name}")
except Exception as e:
    print(f"Group already exists or error: {e}")
    group = Group.objects.get(name='Vermietung')

try:
    user = User.objects.create_user('vermietung', 'vermietung@example.com', 'test123')
    user.groups.add(group)
    print(f"Created user: {user.username}")
except Exception as e:
    print(f"User already exists or error: {e}")

# Create standorte
try:
    standort1 = Adresse.objects.create(
        adressen_type='STANDORT',
        name='Standort Berlin',
        strasse='Berliner Str. 123',
        plz='10115',
        ort='Berlin',
        land='Deutschland'
    )
    print(f"Created standort: {standort1.ort}")
    
    standort2 = Adresse.objects.create(
        adressen_type='STANDORT',
        name='Standort Hamburg',
        strasse='Hamburger Weg 45',
        plz='20095',
        ort='Hamburg',
        land='Deutschland'
    )
    print(f"Created standort: {standort2.ort}")
except Exception as e:
    print(f"Standorte already exist or error: {e}")
    standort1 = Adresse.objects.filter(adressen_type='STANDORT').first()
    standort2 = Adresse.objects.filter(adressen_type='STANDORT').last()

# Create MietObjekte
try:
    objekt1 = MietObjekt.objects.create(
        name='Büro 101',
        type='RAUM',
        beschreibung='Modernes Büro im Stadtzentrum mit großen Fenstern',
        fläche=Decimal('50.00'),
        höhe=Decimal('2.80'),
        standort=standort1,
        mietpreis=Decimal('1200.00'),
        nebenkosten=Decimal('250.00'),
        verfuegbar=True
    )
    print(f"Created Mietobjekt: {objekt1.name}")
    
    objekt2 = MietObjekt.objects.create(
        name='Lager A1',
        type='CONTAINER',
        beschreibung='Großes Lager mit 24/7 Zugang',
        fläche=Decimal('200.00'),
        höhe=Decimal('4.50'),
        standort=standort2,
        mietpreis=Decimal('800.00'),
        nebenkosten=Decimal('150.00'),
        verfuegbar=True
    )
    print(f"Created Mietobjekt: {objekt2.name}")
    
    objekt3 = MietObjekt.objects.create(
        name='Stellplatz 5',
        type='STELLPLATZ',
        beschreibung='Überdachter Stellplatz',
        fläche=Decimal('15.00'),
        standort=standort1,
        mietpreis=Decimal('100.00'),
        verfuegbar=False
    )
    print(f"Created Mietobjekt: {objekt3.name}")
    
    print(f"\nTotal MietObjekte: {MietObjekt.objects.count()}")
except Exception as e:
    print(f"Error creating MietObjekte: {e}")
    import traceback
    traceback.print_exc()

print("\nSetup completed!")
print("You can login with:")
print("  - admin/admin123 (superuser)")
print("  - vermietung/test123 (Vermietung user)")

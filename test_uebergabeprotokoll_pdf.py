"""
Manual test script for Uebergabeprotokoll PDF generation.

This script creates test data and generates a sample PDF to verify the implementation.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

# Run migrations to create database tables
from django.core.management import call_command
call_command('migrate', '--run-syncdb', verbosity=0)

from decimal import Decimal
from datetime import date
from core.models import Mandant, Adresse
from vermietung.models import MietObjekt, Vertrag, Uebergabeprotokoll, UEBERGABE_TYP
from vermietung.printing.context import UebergabeprotokollContextBuilder
from core.printing import PdfRenderService, get_static_base_url


def create_test_data():
    """Create test data for Uebergabeprotokoll PDF testing."""
    print("Creating test data...")
    
    # 1. Create or get Mandant (Company)
    mandant, created = Mandant.objects.get_or_create(
        name='Test Immobilienverwaltung GmbH',
        defaults={
            'adresse': 'Hauptstraße 123',
            'plz': '10115',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'telefon': '+49 30 123456',
            'email': 'info@test-immo.de',
            'steuernummer': 'DE123456789',
            'ust_id_nr': 'DE987654321',
        }
    )
    print(f"  Mandant: {mandant.name} ({'created' if created else 'exists'})")
    
    # 2. Create Standort (Location)
    standort, created = Adresse.objects.get_or_create(
        strasse='Musterstraße 1',
        plz='10115',
        ort='Berlin',
        defaults={
            'adressen_type': 'STANDORT',
            'name': 'Standort Berlin Mitte',
            'land': 'Deutschland',
        }
    )
    print(f"  Standort: {standort.strasse} ({'created' if created else 'exists'})")
    
    # 3. Create MietObjekt (Rental Object)
    mietobjekt, created = MietObjekt.objects.get_or_create(
        name='Wohnung 3B',
        standort=standort,
        defaults={
            'type': 'WOHNUNG',
            'fläche': Decimal('85.50'),
            'beschreibung': 'Schöne 3-Zimmer-Wohnung',
            'mandant': mandant,
        }
    )
    print(f"  MietObjekt: {mietobjekt.name} ({'created' if created else 'exists'})")
    
    # 4. Create Mieter (Tenant/Customer)
    mieter, created = Adresse.objects.get_or_create(
        name='Mustermann',
        strasse='Mietergasse 42',
        defaults={
            'adressen_type': 'KUNDE',
            'firma': '',
            'anrede': 'HERR',
            'plz': '10115',
            'ort': 'Berlin',
            'land': 'Deutschland',
            'email': 'max.mustermann@example.com',
            'telefon': '+49 170 1234567',
        }
    )
    print(f"  Mieter: {mieter.name} ({'created' if created else 'exists'})")
    
    # 5. Create Vertrag (Contract)
    vertrag, created = Vertrag.objects.get_or_create(
        vertragsnummer='VM2024001',
        defaults={
            'mieter': mieter,
            'mandant': mandant,
            'start': date(2024, 1, 1),
            'ende': None,
            'miete': Decimal('750.00'),
            'kaution': Decimal('2250.00'),
            'status': 'active',
        }
    )
    print(f"  Vertrag: {vertrag.vertragsnummer} ({'created' if created else 'exists'})")
    
    # Create VertragsObjekt to link Vertrag with MietObjekt
    from vermietung.models import VertragsObjekt
    vo, vo_created = VertragsObjekt.objects.get_or_create(
        vertrag=vertrag,
        mietobjekt=mietobjekt,
        defaults={
            'preis': Decimal('750.00'),
            'anzahl': 1,
            'status': 'AKTIV',
        }
    )
    
    # 6. Create Uebergabeprotokoll (Handover Protocol) - EINZUG
    protokoll, created = Uebergabeprotokoll.objects.get_or_create(
        vertrag=vertrag,
        mietobjekt=mietobjekt,
        typ='EINZUG',
        defaults={
            'uebergabetag': date(2024, 1, 1),
            'zaehlerstand_strom': Decimal('12345.50'),
            'zaehlerstand_gas': Decimal('6789.00'),
            'zaehlerstand_wasser': Decimal('3456.75'),
            'anzahl_schluessel': 3,
            'bemerkungen': (
                'Die Wohnung wurde in sauberem Zustand übergeben.\n'
                'Alle Räume wurden gemeinsam besichtigt.\n'
                'Der Mieter hat die Hausordnung erhalten.'
            ),
            'maengel': (
                '1. Kleine Kratzer am Türrahmen im Wohnzimmer\n'
                '2. Wasserfleck an der Decke im Badezimmer (ca. 10x10 cm)\n'
                '3. Fenstergriff im Schlafzimmer locker'
            ),
            'person_vermieter': 'Hans Verwalter',
            'person_mieter': 'Max Mustermann',
        }
    )
    print(f"  Übergabeprotokoll: {protokoll} ({'created' if created else 'exists'})")
    
    return protokoll


def test_pdf_generation(protokoll):
    """Test PDF generation for the given protokoll."""
    print(f"\nTesting PDF generation for Übergabeprotokoll {protokoll.pk}...")
    
    # Build context
    context_builder = UebergabeprotokollContextBuilder()
    context = context_builder.build_context(protokoll)
    template_name = context_builder.get_template_name(protokoll)
    
    print(f"  Template: {template_name}")
    print(f"  Context keys: {list(context.keys())}")
    
    # Check context content
    print(f"\n  Company: {context.get('company', {}).get('name', 'N/A')}")
    print(f"  Protokoll Typ: {context.get('protokoll', {}).get('typ_display', 'N/A')}")
    print(f"  Vertrag: {context.get('vertrag', {}).get('vertragsnummer', 'N/A')}")
    print(f"  MietObjekt: {context.get('mietobjekt', {}).get('name', 'N/A')}")
    print(f"  Mieter: {context.get('mieter', {}).get('name', 'N/A')}")
    
    # Generate PDF
    base_url = get_static_base_url()
    pdf_service = PdfRenderService()
    
    try:
        result = pdf_service.render(
            template_name=template_name,
            context=context,
            base_url=base_url,
            filename='test_uebergabeprotokoll.pdf'
        )
        
        # Save to file
        output_path = '/tmp/test_uebergabeprotokoll.pdf'
        with open(output_path, 'wb') as f:
            f.write(result.pdf_bytes)
        
        print(f"\n✓ PDF generated successfully!")
        print(f"  Size: {len(result.pdf_bytes)} bytes")
        print(f"  Filename: {result.filename}")
        print(f"  Saved to: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ PDF generation failed!")
        print(f"  Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("Uebergabeprotokoll PDF Generation Test")
    print("=" * 60)
    
    # Create test data
    protokoll = create_test_data()
    
    # Test PDF generation
    success = test_pdf_generation(protokoll)
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
        print("\nYou can view the PDF at: /tmp/test_uebergabeprotokoll.pdf")
    else:
        print("✗ Tests failed - see errors above")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

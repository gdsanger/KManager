"""
Tests for VAT (Umsatzsteuer) functionality in Vertrag model.
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class VertragVATTestCase(TestCase):
    """Test case for VAT calculations in Vertrag."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=False
        )
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create test standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        # Create test customer
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create test mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            verfuegbar=True
        )
    
    def test_vat_calculation_19_percent(self):
        """Test VAT calculation with 19% rate."""
        # Create contract with 19% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Test calculations
        nettobetrag = vertrag.berechne_gesamtmiete()
        self.assertEqual(nettobetrag, Decimal('1000.00'))
        
        umsatzsteuer = vertrag.berechne_umsatzsteuer()
        self.assertEqual(umsatzsteuer, Decimal('190.00'))  # 19% of 1000
        
        bruttobetrag = vertrag.berechne_bruttobetrag()
        self.assertEqual(bruttobetrag, Decimal('1190.00'))  # 1000 + 190
    
    def test_vat_calculation_7_percent(self):
        """Test VAT calculation with 7% rate."""
        # Create contract with 7% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            umsatzsteuer_satz='7',
            status='active'
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Test calculations
        nettobetrag = vertrag.berechne_gesamtmiete()
        self.assertEqual(nettobetrag, Decimal('1000.00'))
        
        umsatzsteuer = vertrag.berechne_umsatzsteuer()
        self.assertEqual(umsatzsteuer, Decimal('70.00'))  # 7% of 1000
        
        bruttobetrag = vertrag.berechne_bruttobetrag()
        self.assertEqual(bruttobetrag, Decimal('1070.00'))  # 1000 + 70
    
    def test_vat_calculation_0_percent(self):
        """Test VAT calculation with 0% rate (tax-free)."""
        # Create contract with 0% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            umsatzsteuer_satz='0',
            status='active'
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Test calculations
        nettobetrag = vertrag.berechne_gesamtmiete()
        self.assertEqual(nettobetrag, Decimal('1000.00'))
        
        umsatzsteuer = vertrag.berechne_umsatzsteuer()
        self.assertEqual(umsatzsteuer, Decimal('0.00'))  # 0% of 1000
        
        bruttobetrag = vertrag.berechne_bruttobetrag()
        self.assertEqual(bruttobetrag, Decimal('1000.00'))  # 1000 + 0
    
    def test_vat_calculation_multiple_objects(self):
        """Test VAT calculation with multiple rental objects."""
        # Create another mietobjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Büro 2',
            type='RAUM',
            beschreibung='Großes Büro',
            standort=self.standort,
            mietpreis=Decimal('1500.00'),
            kaution=Decimal('4500.00'),
            verfuegbar=True
        )
        
        # Create contract with 19% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('2500.00'),  # Will be updated
            kaution=Decimal('7500.00'),
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create VertragsObjekt for first object
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Create VertragsObjekt for second object
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt2,
            preis=Decimal('1500.00'),
            anzahl=1
        )
        
        # Test calculations
        nettobetrag = vertrag.berechne_gesamtmiete()
        self.assertEqual(nettobetrag, Decimal('2500.00'))  # 1000 + 1500
        
        umsatzsteuer = vertrag.berechne_umsatzsteuer()
        self.assertEqual(umsatzsteuer, Decimal('475.00'))  # 19% of 2500
        
        bruttobetrag = vertrag.berechne_bruttobetrag()
        self.assertEqual(bruttobetrag, Decimal('2975.00'))  # 2500 + 475
    
    def test_vat_calculation_with_quantities(self):
        """Test VAT calculation with multiple quantities."""
        # Create mietobjekt with 3 available units
        mietobjekt_multi = MietObjekt.objects.create(
            name='Container Lager',
            type='CONTAINER',
            beschreibung='Mehrfach vermietbar',
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            verfuegbare_einheiten=3,
            verfuegbar=True
        )
        
        # Create contract with 19% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('3000.00'),  # Will be updated
            kaution=Decimal('9000.00'),
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create VertragsObjekt with quantity 3
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt_multi,
            preis=Decimal('1000.00'),
            anzahl=3
        )
        
        # Test calculations
        nettobetrag = vertrag.berechne_gesamtmiete()
        self.assertEqual(nettobetrag, Decimal('3000.00'))  # 1000 * 3
        
        umsatzsteuer = vertrag.berechne_umsatzsteuer()
        self.assertEqual(umsatzsteuer, Decimal('570.00'))  # 19% of 3000
        
        bruttobetrag = vertrag.berechne_bruttobetrag()
        self.assertEqual(bruttobetrag, Decimal('3570.00'))  # 3000 + 570
    
    def test_default_vat_rate(self):
        """Test that default VAT rate is 19%."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        # Check default value
        self.assertEqual(vertrag.umsatzsteuer_satz, '19')

"""
Tests for stellplatzbetrag (parking space amount) functionality in Vertrag model.
Tests that the stellplatzbetrag field is correctly added to the effective_net_total.
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class VertragStellplatzbetragTestCase(TestCase):
    """Test case for stellplatzbetrag in Vertrag."""
    
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
    
    def test_stellplatzbetrag_default_none(self):
        """Test that stellplatzbetrag defaults to None."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        self.assertIsNone(vertrag.stellplatzbetrag)
    
    def test_stellplatzbetrag_with_auto_total(self):
        """Test that stellplatzbetrag is added to auto-calculated total."""
        # Create contract in auto mode (default)
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            stellplatzbetrag=Decimal('100.00')
        )
        
        # Add a contract object
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Effective total should be sum of positions + stellplatzbetrag
        # 1 * 1000.00 + 100.00 = 1100.00
        self.assertEqual(vertrag.effective_net_total, Decimal('1100.00'))
    
    def test_stellplatzbetrag_with_manual_total(self):
        """Test that stellplatzbetrag is added to manual total."""
        # Create contract with manual total
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            auto_total=False,
            manual_net_total=Decimal('1500.00'),
            stellplatzbetrag=Decimal('150.00')
        )
        
        # Add a contract object (should be ignored due to manual mode)
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Effective total should be manual total + stellplatzbetrag
        # 1500.00 + 150.00 = 1650.00
        self.assertEqual(vertrag.effective_net_total, Decimal('1650.00'))
    
    def test_stellplatzbetrag_none_treated_as_zero(self):
        """Test that None stellplatzbetrag is treated as 0."""
        # Create contract without stellplatzbetrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        # Add a contract object with anzahl=1 (within available units)
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('500.00'),
            anzahl=1
        )
        
        # Effective total should be just the sum of positions
        # 1 * 500.00 = 500.00
        self.assertEqual(vertrag.effective_net_total, Decimal('500.00'))
    
    def test_stellplatzbetrag_zero(self):
        """Test that zero stellplatzbetrag works correctly."""
        # Create contract with zero stellplatzbetrag
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            stellplatzbetrag=Decimal('0.00')
        )
        
        # Add a contract object
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('800.00'),
            anzahl=1
        )
        
        # Effective total should be just the sum of positions
        # 1 * 800.00 + 0.00 = 800.00
        self.assertEqual(vertrag.effective_net_total, Decimal('800.00'))
    
    def test_stellplatzbetrag_multiple_positions(self):
        """Test stellplatzbetrag with multiple contract positions."""
        # Create contract
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            stellplatzbetrag=Decimal('75.50')
        )
        
        # Add contract object with anzahl=1 (within available units)
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('500.00'),
            anzahl=1
        )
        
        # Create another mietobjekt
        mietobjekt2 = MietObjekt.objects.create(
            name='Lager 1',
            type='LAGER',
            beschreibung='Kleines Lager',
            standort=self.standort,
            mietpreis=Decimal('300.00'),
            kaution=Decimal('900.00'),
            verfuegbar=True
        )
        
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt2,
            preis=Decimal('300.00'),
            anzahl=1
        )
        
        # Effective total should be sum of all positions + stellplatzbetrag
        # (1 * 500.00) + (1 * 300.00) + 75.50 = 500.00 + 300.00 + 75.50 = 875.50
        self.assertEqual(vertrag.effective_net_total, Decimal('875.50'))
    
    def test_stellplatzbetrag_affects_vat_calculation(self):
        """Test that stellplatzbetrag is included in VAT calculation."""
        # Create contract with stellplatzbetrag and 19% VAT
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            umsatzsteuer_satz='19',
            stellplatzbetrag=Decimal('100.00')
        )
        
        # Add a contract object
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Net total: 1000.00 + 100.00 = 1100.00
        # VAT (19%): 1100.00 * 0.19 = 209.00
        # Gross: 1100.00 + 209.00 = 1309.00
        self.assertEqual(vertrag.effective_net_total, Decimal('1100.00'))
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('209.00'))
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('1309.00'))
    
    def test_stellplatzbetrag_persistence(self):
        """Test that stellplatzbetrag is correctly saved and retrieved."""
        # Create and save contract
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            stellplatzbetrag=Decimal('125.75')
        )
        
        # Retrieve from database
        vertrag_from_db = Vertrag.objects.get(pk=vertrag.pk)
        
        # Check that stellplatzbetrag was saved correctly
        self.assertEqual(vertrag_from_db.stellplatzbetrag, Decimal('125.75'))
    
    def test_stellplatzbetrag_negative_validation(self):
        """Test that negative stellplatzbetrag is rejected by validation."""
        # Create contract with negative stellplatzbetrag
        vertrag = Vertrag(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active',
            stellplatzbetrag=Decimal('-50.00')
        )
        
        # Validation should raise error
        with self.assertRaises(ValidationError) as context:
            vertrag.clean()
        
        # Check that the error is for stellplatzbetrag field
        self.assertIn('stellplatzbetrag', context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict['stellplatzbetrag'][0],
            'Der Stellplatzbetrag darf nicht negativ sein.'
        )

"""
Tests for flat-rate pricing functionality in Vertrag model.
Tests the auto_total and manual_net_total fields that allow
contracts to override the calculated total with a manual flat rate.
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class VertragFlatRateTestCase(TestCase):
    """Test case for flat-rate pricing in Vertrag."""
    
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
    
    def test_auto_total_default_true(self):
        """Test that auto_total defaults to True."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            status='active'
        )
        
        self.assertTrue(vertrag.auto_total)
        self.assertIsNone(vertrag.manual_net_total)
    
    def test_auto_mode_calculation(self):
        """Test that auto mode calculates total from line items."""
        # Create contract in auto mode (default)
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=True,
            status='active'
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # In auto mode, effective_net_total should equal sum of lines
        calculated_total = vertrag.berechne_gesamtmiete()
        self.assertEqual(calculated_total, Decimal('1000.00'))
        self.assertEqual(vertrag.effective_net_total, Decimal('1000.00'))
        self.assertEqual(vertrag.effective_net_total, calculated_total)
    
    def test_manual_mode_with_flat_rate(self):
        """Test that manual mode uses manual_net_total instead of line items."""
        # Create contract in manual mode with flat rate
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('1500.00'),  # Flat rate override
            status='active'
        )
        
        # Create VertragsObjekt (line items)
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # In manual mode, effective_net_total should equal manual_net_total
        calculated_total = vertrag.berechne_gesamtmiete()
        self.assertEqual(calculated_total, Decimal('1000.00'))  # Line items sum
        self.assertEqual(vertrag.effective_net_total, Decimal('1500.00'))  # Manual override
        self.assertNotEqual(vertrag.effective_net_total, calculated_total)
    
    def test_manual_mode_with_null_flat_rate(self):
        """Test that manual mode with null manual_net_total falls back to calculated total."""
        # Create contract in manual mode but without manual_net_total set
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=None,  # Not set during negotiation
            status='active'
        )
        
        # Create VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Should fall back to calculated total
        calculated_total = vertrag.berechne_gesamtmiete()
        self.assertEqual(calculated_total, Decimal('1000.00'))
        self.assertEqual(vertrag.effective_net_total, Decimal('1000.00'))
    
    def test_vat_calculation_auto_mode(self):
        """Test VAT calculation in auto mode uses sum of line items."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=True,
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
        
        # VAT should be calculated on line items sum
        self.assertEqual(vertrag.effective_net_total, Decimal('1000.00'))
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('190.00'))  # 19% of 1000
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('1190.00'))  # 1000 + 190
    
    def test_vat_calculation_manual_mode(self):
        """Test VAT calculation in manual mode uses manual_net_total."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('1500.00'),  # Override
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create VertragsObjekt with different total
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # VAT should be calculated on manual_net_total, not line items
        self.assertEqual(vertrag.berechne_gesamtmiete(), Decimal('1000.00'))  # Line items
        self.assertEqual(vertrag.effective_net_total, Decimal('1500.00'))  # Manual override
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('285.00'))  # 19% of 1500
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('1785.00'))  # 1500 + 285
    
    def test_multiple_objects_auto_mode(self):
        """Test auto mode with multiple rental objects."""
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
        
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('2500.00'),
            kaution=Decimal('7500.00'),
            auto_total=True,
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create two VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt2,
            preis=Decimal('1500.00'),
            anzahl=1
        )
        
        # Should sum both objects
        self.assertEqual(vertrag.effective_net_total, Decimal('2500.00'))
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('475.00'))
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('2975.00'))
    
    def test_multiple_objects_manual_mode(self):
        """Test manual mode with multiple rental objects - flat rate overrides sum."""
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
        
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('2500.00'),
            kaution=Decimal('7500.00'),
            auto_total=False,
            manual_net_total=Decimal('2000.00'),  # Flat rate lower than sum
            umsatzsteuer_satz='19',
            status='active'
        )
        
        # Create two VertragsObjekt
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=mietobjekt2,
            preis=Decimal('1500.00'),
            anzahl=1
        )
        
        # Line items sum to 2500, but manual override is 2000
        self.assertEqual(vertrag.berechne_gesamtmiete(), Decimal('2500.00'))  # Line items
        self.assertEqual(vertrag.effective_net_total, Decimal('2000.00'))  # Manual override
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('380.00'))  # 19% of 2000
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('2380.00'))  # 2000 + 380
    
    def test_validation_negative_manual_net_total(self):
        """Test that negative manual_net_total is rejected."""
        vertrag = Vertrag(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('-100.00'),  # Invalid
            status='active'
        )
        
        with self.assertRaises(ValidationError) as cm:
            vertrag.full_clean()
        
        self.assertIn('manual_net_total', cm.exception.message_dict)
    
    def test_validation_zero_manual_net_total_allowed(self):
        """Test that zero manual_net_total is allowed."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('0.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('0.00'),  # Valid (e.g., free rental)
            status='active'
        )
        
        # Should not raise any validation error
        vertrag.full_clean()
        self.assertEqual(vertrag.effective_net_total, Decimal('0.00'))
    
    def test_switching_auto_to_manual(self):
        """Test switching from auto to manual mode."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=True,
            status='active'
        )
        
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Initially in auto mode
        self.assertEqual(vertrag.effective_net_total, Decimal('1000.00'))
        
        # Switch to manual mode
        vertrag.auto_total = False
        vertrag.manual_net_total = Decimal('1200.00')
        vertrag.save()
        
        # Should now use manual value
        vertrag.refresh_from_db()
        self.assertFalse(vertrag.auto_total)
        self.assertEqual(vertrag.effective_net_total, Decimal('1200.00'))
    
    def test_switching_manual_to_auto(self):
        """Test switching from manual to auto mode."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('1200.00'),
            status='active'
        )
        
        VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Initially in manual mode
        self.assertEqual(vertrag.effective_net_total, Decimal('1200.00'))
        
        # Switch to auto mode
        vertrag.auto_total = True
        vertrag.save()
        
        # Should now use calculated value
        vertrag.refresh_from_db()
        self.assertTrue(vertrag.auto_total)
        self.assertEqual(vertrag.effective_net_total, Decimal('1000.00'))
    
    def test_quantities_in_auto_mode(self):
        """Test auto mode with quantity > 1."""
        # Create a multi-unit mietobjekt
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
        
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('3000.00'),
            kaution=Decimal('9000.00'),
            auto_total=True,
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
        
        # Should calculate 3 * 1000
        self.assertEqual(vertrag.effective_net_total, Decimal('3000.00'))
        self.assertEqual(vertrag.berechne_umsatzsteuer(), Decimal('570.00'))
        self.assertEqual(vertrag.berechne_bruttobetrag(), Decimal('3570.00'))
    
    def test_line_items_preserved_in_manual_mode(self):
        """Test that line items are preserved but not used in manual mode."""
        vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('1000.00'),
            kaution=Decimal('3000.00'),
            auto_total=False,
            manual_net_total=Decimal('1500.00'),
            status='active'
        )
        
        # Create VertragsObjekt
        vo = VertragsObjekt.objects.create(
            vertrag=vertrag,
            mietobjekt=self.mietobjekt,
            preis=Decimal('1000.00'),
            anzahl=1
        )
        
        # Line items are stored and accessible
        self.assertEqual(vertrag.vertragsobjekte.count(), 1)
        self.assertEqual(vo.preis, Decimal('1000.00'))
        self.assertEqual(vertrag.berechne_gesamtmiete(), Decimal('1000.00'))
        
        # But effective total uses manual value
        self.assertEqual(vertrag.effective_net_total, Decimal('1500.00'))

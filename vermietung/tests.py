from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, Uebergabeprotokoll


class VertragModelTest(TestCase):
    """Tests for the Vertrag (Contract) model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a customer address
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create a non-customer address
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferstrasse 2',
            plz='54321',
            ort='Lieferstadt',
            land='Deutschland'
        )
        
        # Create a location address
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create a rental object
        self.mietobjekt = MietObjekt.objects.create(
            name='Garage 1',
            type='GEBAEUDE',
            beschreibung='Eine schöne Garage',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00,
            verfuegbar=True
        )
        
        # Create another rental object
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Garage 2',
            type='GEBAEUDE',
            beschreibung='Noch eine Garage',
            fläche=25.00,
            standort=self.standort,
            mietpreis=200.00,
            verfuegbar=True
        )
    
    def test_vertragsnummer_auto_generation(self):
        """Test that contract numbers are auto-generated in the correct format."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.vertragsnummer, 'V-00001')
    
    def test_vertragsnummer_sequential(self):
        """Test that contract numbers are generated sequentially."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2025, 1, 1),
            ende=date(2025, 12, 31),
            miete=200.00,
            kaution=600.00
        )
        self.assertEqual(vertrag1.vertragsnummer, 'V-00001')
        self.assertEqual(vertrag2.vertragsnummer, 'V-00002')
    
    def test_vertragsnummer_unique(self):
        """Test that contract numbers are unique."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        # Try to create a second contract - should get a different number
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2025, 1, 1),
            miete=200.00,
            kaution=600.00
        )
        self.assertNotEqual(vertrag1.vertragsnummer, vertrag2.vertragsnummer)
    
    def test_start_is_required(self):
        """Test that start date is required."""
        with self.assertRaises(ValidationError):
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                # start is missing
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
    
    def test_ende_is_optional(self):
        """Test that ende (end date) is optional (NULL allowed)."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            # ende is None (optional)
            miete=150.00,
            kaution=450.00
        )
        self.assertIsNone(vertrag.ende)
        self.assertEqual(vertrag.vertragsnummer, 'V-00001')
    
    def test_ende_must_be_after_start(self):
        """Test that ende must be greater than start if set."""
        with self.assertRaises(ValidationError) as context:
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 12, 31),
                ende=date(2024, 1, 1),  # ende before start
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
        
        self.assertIn('ende', context.exception.error_dict)
    
    def test_ende_equal_to_start_invalid(self):
        """Test that ende equal to start is invalid."""
        with self.assertRaises(ValidationError) as context:
            vertrag = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 1, 1),
                ende=date(2024, 1, 1),  # same as start
                miete=150.00,
                kaution=450.00
            )
            vertrag.full_clean()
        
        self.assertIn('ende', context.exception.error_dict)
    
    def test_mieter_relationship(self):
        """Test the relationship between Vertrag and Adresse (Mieter)."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.mieter, self.kunde)
        self.assertEqual(vertrag.mieter.adressen_type, 'KUNDE')
    
    def test_mietobjekt_relationship(self):
        """Test the relationship between Vertrag and MietObjekt."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag.mietobjekt, self.mietobjekt)
        # Test reverse relationship
        self.assertIn(vertrag, self.mietobjekt.vertraege.all())
    
    def test_multiple_contracts_for_same_mietobjekt(self):
        """Test that a MietObjekt can have multiple contracts (history)."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=160.00,
            kaution=480.00
        )
        contracts = self.mietobjekt.vertraege.all()
        self.assertEqual(contracts.count(), 2)
        self.assertIn(vertrag1, contracts)
        self.assertIn(vertrag2, contracts)
    
    def test_overlapping_contracts_with_end_dates(self):
        """Test that overlapping contracts are prevented."""
        # Create first contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Try to create overlapping contract
        with self.assertRaises(ValidationError):
            vertrag2 = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2024, 6, 1),  # overlaps with vertrag1
                ende=date(2025, 6, 1),
                miete=150.00,
                kaution=450.00
            )
            vertrag2.save()
    
    def test_open_ended_contract_blocks_future_contracts(self):
        """Test that an open-ended contract (ende=NULL) blocks future contracts."""
        # Create open-ended contract
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            # ende is None (open-ended)
            miete=150.00,
            kaution=450.00
        )
        
        # Try to create a contract starting after the open-ended one
        with self.assertRaises(ValidationError):
            vertrag2 = Vertrag(
                mietobjekt=self.mietobjekt,
                mieter=self.kunde,
                start=date(2025, 1, 1),
                ende=date(2025, 12, 31),
                miete=150.00,
                kaution=450.00
            )
            vertrag2.save()
    
    def test_non_overlapping_contracts_allowed(self):
        """Test that non-overlapping (adjacent) contracts are allowed."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Create adjacent/non-overlapping contract (starts day after first ends)
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=160.00,
            kaution=480.00
        )
        
        self.assertEqual(Vertrag.objects.filter(mietobjekt=self.mietobjekt).count(), 2)
    
    def test_different_mietobjekt_no_conflict(self):
        """Test that contracts for different MietObjekt don't conflict."""
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Same dates but different MietObjekt - should be allowed
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=200.00,
            kaution=600.00
        )
        
        self.assertEqual(Vertrag.objects.count(), 2)
    
    def test_decimal_fields_miete_kaution(self):
        """Test that miete and kaution are decimal fields."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.50,
            kaution=451.50
        )
        self.assertEqual(float(vertrag.miete), 150.50)
        self.assertEqual(float(vertrag.kaution), 451.50)
    
    def test_str_representation(self):
        """Test the string representation of Vertrag."""
        vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        expected = f"V-00001 - Garage 1 (Max Mustermann)"
        self.assertEqual(str(vertrag), expected)
    
    def test_open_ended_after_finished_contract(self):
        """Test that an open-ended contract can be created after a finished contract."""
        # Create a contract that has ended
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2023, 1, 1),
            ende=date(2023, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        
        # Create an open-ended contract starting after the first one ends
        # This should be allowed
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),  # Starts after vertrag1 ends
            ende=None,  # Open-ended
            miete=160.00,
            kaution=480.00
        )
        
        self.assertEqual(Vertrag.objects.filter(mietobjekt=self.mietobjekt).count(), 2)
        self.assertIsNone(vertrag2.ende)
    
    def test_contract_number_generation_with_malformed_data(self):
        """Test that contract number generation handles malformed data gracefully."""
        # Create first contract normally
        vertrag1 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
        self.assertEqual(vertrag1.vertragsnummer, 'V-00001')
        
        # Manually corrupt the contract number in the database
        Vertrag.objects.filter(pk=vertrag1.pk).update(vertragsnummer='INVALID')
        
        # Create a new contract - should handle the malformed number gracefully
        vertrag2 = Vertrag.objects.create(
            mietobjekt=self.mietobjekt2,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            miete=200.00,
            kaution=600.00
        )
        
        # Should still generate a valid contract number
        self.assertTrue(vertrag2.vertragsnummer.startswith('V-'))
        self.assertEqual(len(vertrag2.vertragsnummer), 7)  # V-XXXXX format


class UebergabeprotokollModelTest(TestCase):
    """Tests for the Uebergabeprotokoll (Handover Protocol) model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a customer address
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        # Create a location address
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 3',
            plz='11111',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create rental objects
        self.mietobjekt = MietObjekt.objects.create(
            name='Garage 1',
            type='GEBAEUDE',
            beschreibung='Eine schöne Garage',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00,
            verfuegbar=True
        )
        
        self.mietobjekt2 = MietObjekt.objects.create(
            name='Garage 2',
            type='GEBAEUDE',
            beschreibung='Noch eine Garage',
            fläche=25.00,
            standort=self.standort,
            mietpreis=200.00,
            verfuegbar=True
        )
        
        # Create a contract
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=150.00,
            kaution=450.00
        )
    
    def test_create_uebergabeprotokoll_basic(self):
        """Test creating a basic handover protocol."""
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2,
            person_vermieter='Hans Schmidt',
            person_mieter='Max Mustermann'
        )
        
        self.assertEqual(protokoll.vertrag, self.vertrag)
        self.assertEqual(protokoll.mietobjekt, self.mietobjekt)
        self.assertEqual(protokoll.typ, 'EINZUG')
        self.assertEqual(protokoll.anzahl_schluessel, 2)
    
    def test_uebergabeprotokoll_with_meter_readings(self):
        """Test creating a protocol with meter readings."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            zaehlerstand_strom=1234.50,
            zaehlerstand_gas=567.00,
            zaehlerstand_wasser=890.00,
            anzahl_schluessel=2
        )
        
        self.assertEqual(float(protokoll.zaehlerstand_strom), 1234.50)
        self.assertEqual(float(protokoll.zaehlerstand_gas), 567.00)
        self.assertEqual(float(protokoll.zaehlerstand_wasser), 890.00)
    
    def test_uebergabeprotokoll_with_remarks_and_defects(self):
        """Test creating a protocol with remarks and defects."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='AUSZUG',
            uebergabetag=date(2024, 12, 31),
            anzahl_schluessel=2,
            bemerkungen='Übergabe verlief reibungslos',
            maengel='Kleine Kratzer an der Tür'
        )
        
        self.assertEqual(protokoll.bemerkungen, 'Übergabe verlief reibungslos')
        self.assertEqual(protokoll.maengel, 'Kleine Kratzer an der Tür')
    
    def test_mietobjekt_must_match_vertrag(self):
        """Test that MietObjekt must match the Vertrag's MietObjekt."""
        
        # Try to create a protocol with mismatched MietObjekt
        with self.assertRaises(ValidationError) as context:
            protokoll = Uebergabeprotokoll(
                vertrag=self.vertrag,  # Contract is for mietobjekt
                mietobjekt=self.mietobjekt2,  # But we're using mietobjekt2
                typ='EINZUG',
                uebergabetag=date(2024, 1, 1),
                anzahl_schluessel=2
            )
            protokoll.save()
        
        self.assertIn('mietobjekt', context.exception.error_dict)
    
    def test_multiple_protocols_per_contract(self):
        """Test that multiple protocols can exist for the same contract."""
        
        # Create move-in protocol
        einzug = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2,
            zaehlerstand_strom=1000.00
        )
        
        # Create move-out protocol
        auszug = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='AUSZUG',
            uebergabetag=date(2024, 12, 31),
            anzahl_schluessel=2,
            zaehlerstand_strom=1500.00
        )
        
        protocols = self.vertrag.uebergabeprotokolle.all()
        self.assertEqual(protocols.count(), 2)
        self.assertIn(einzug, protocols)
        self.assertIn(auszug, protocols)
    
    def test_einzug_before_contract_start_invalid(self):
        """Test that move-in date before contract start is invalid."""
        
        with self.assertRaises(ValidationError) as context:
            protokoll = Uebergabeprotokoll(
                vertrag=self.vertrag,  # Starts 2024-01-01
                mietobjekt=self.mietobjekt,
                typ='EINZUG',
                uebergabetag=date(2023, 12, 31),  # Before contract start
                anzahl_schluessel=2
            )
            protokoll.save()
        
        self.assertIn('uebergabetag', context.exception.error_dict)
    
    def test_auszug_after_contract_end_invalid(self):
        """Test that move-out date after contract end is invalid."""
        
        with self.assertRaises(ValidationError) as context:
            protokoll = Uebergabeprotokoll(
                vertrag=self.vertrag,  # Ends 2024-12-31
                mietobjekt=self.mietobjekt,
                typ='AUSZUG',
                uebergabetag=date(2025, 1, 1),  # After contract end
                anzahl_schluessel=2
            )
            protokoll.save()
        
        self.assertIn('uebergabetag', context.exception.error_dict)
    
    def test_str_representation(self):
        """Test the string representation of Uebergabeprotokoll."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
        
        expected = f"Einzug - {self.vertrag.vertragsnummer} - 2024-01-01"
        self.assertEqual(str(protokoll), expected)
    
    def test_optional_fields(self):
        """Test that meter readings and text fields are optional."""
        
        # Create protocol with only required fields
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
        
        self.assertIsNone(protokoll.zaehlerstand_strom)
        self.assertIsNone(protokoll.zaehlerstand_gas)
        self.assertIsNone(protokoll.zaehlerstand_wasser)
        self.assertEqual(protokoll.bemerkungen, '')
        self.assertEqual(protokoll.maengel, '')
        self.assertEqual(protokoll.person_vermieter, '')
        self.assertEqual(protokoll.person_mieter, '')
    
    def test_default_anzahl_schluessel(self):
        """Test that anzahl_schluessel has a default value of 0."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1)
            # anzahl_schluessel not provided
        )
        
        self.assertEqual(protokoll.anzahl_schluessel, 0)
    
    def test_relationship_to_vertrag(self):
        """Test the relationship between Uebergabeprotokoll and Vertrag."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
        
        # Test forward relationship
        self.assertEqual(protokoll.vertrag, self.vertrag)
        
        # Test reverse relationship
        self.assertIn(protokoll, self.vertrag.uebergabeprotokolle.all())
    
    def test_relationship_to_mietobjekt(self):
        """Test the relationship between Uebergabeprotokoll and MietObjekt."""
        
        protokoll = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
        
        # Test forward relationship
        self.assertEqual(protokoll.mietobjekt, self.mietobjekt)
        
        # Test reverse relationship
        self.assertIn(protokoll, self.mietobjekt.uebergabeprotokolle.all())
    
    def test_ordering_by_uebergabetag(self):
        """Test that protocols are ordered by uebergabetag (descending)."""
        
        protokoll1 = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='EINZUG',
            uebergabetag=date(2024, 1, 1),
            anzahl_schluessel=2
        )
        
        protokoll2 = Uebergabeprotokoll.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            typ='AUSZUG',
            uebergabetag=date(2024, 12, 31),
            anzahl_schluessel=2
        )
        
        protocols = Uebergabeprotokoll.objects.all()
        # Should be ordered by uebergabetag descending
        self.assertEqual(list(protocols), [protokoll2, protokoll1])


class MietObjektModelTest(TestCase):
    """Tests for the MietObjekt model extensions (kaution and qm_mietpreis)."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a location address
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Standortstrasse 1',
            plz='12345',
            ort='Standortstadt',
            land='Deutschland'
        )
    
    def test_kaution_default_value_on_creation(self):
        """Test that kaution is automatically set to 3 × mietpreis for new objects."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00
        )
        
        # kaution should be 3 × mietpreis = 3 × 150 = 450
        self.assertEqual(mietobjekt.kaution, 450.00)
    
    def test_kaution_can_be_set_explicitly(self):
        """Test that kaution can be set explicitly and won't be overridden."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00,
            kaution=500.00  # Set explicitly
        )
        
        # kaution should be the explicitly set value, not 3 × mietpreis
        self.assertEqual(mietobjekt.kaution, 500.00)
    
    def test_kaution_not_updated_on_mietpreis_change(self):
        """Test that kaution is not automatically updated when mietpreis changes."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00
        )
        
        # Initial kaution should be 450
        self.assertEqual(mietobjekt.kaution, 450.00)
        
        # Update mietpreis
        mietobjekt.mietpreis = 200.00
        mietobjekt.save()
        
        # kaution should remain unchanged
        mietobjekt.refresh_from_db()
        self.assertEqual(mietobjekt.kaution, 450.00)
    
    def test_qm_mietpreis_calculation(self):
        """Test that qm_mietpreis is calculated correctly."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=20.00,
            standort=self.standort,
            mietpreis=150.00
        )
        
        # qm_mietpreis should be 150 / 20 = 7.50
        from decimal import Decimal
        self.assertEqual(mietobjekt.qm_mietpreis, Decimal('7.50'))
    
    def test_qm_mietpreis_rounding(self):
        """Test that qm_mietpreis is rounded to 2 decimal places."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=30.00,
            standort=self.standort,
            mietpreis=100.00
        )
        
        # qm_mietpreis should be 100 / 30 = 3.333... rounded to 3.33
        from decimal import Decimal
        self.assertEqual(mietobjekt.qm_mietpreis, Decimal('3.33'))
    
    def test_qm_mietpreis_with_zero_flaeche(self):
        """Test that qm_mietpreis returns None when fläche is 0."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=0,
            standort=self.standort,
            mietpreis=150.00
        )
        
        # Should return None without raising an error
        self.assertIsNone(mietobjekt.qm_mietpreis)
    
    def test_qm_mietpreis_with_none_flaeche(self):
        """Test that qm_mietpreis returns None when fläche is None."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=None,
            standort=self.standort,
            mietpreis=150.00
        )
        
        # Should return None without raising an error
        self.assertIsNone(mietobjekt.qm_mietpreis)
    
    def test_qm_mietpreis_precision(self):
        """Test qm_mietpreis calculation with various values for precision."""
        mietobjekt = MietObjekt.objects.create(
            name='Test Garage',
            type='GEBAEUDE',
            beschreibung='Test',
            fläche=7.00,
            standort=self.standort,
            mietpreis=50.00
        )
        
        # qm_mietpreis should be 50 / 7 = 7.142857... rounded to 7.14
        from decimal import Decimal
        self.assertEqual(mietobjekt.qm_mietpreis, Decimal('7.14'))
    

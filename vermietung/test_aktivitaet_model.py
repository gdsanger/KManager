"""
Tests for Aktivitaet (Activity/Task) model.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, Aktivitaet, AktivitaetsBereich

User = get_user_model()


class AktivitaetModelTest(TestCase):
    """Tests for the Aktivitaet (Activity) model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a user for assignment tests
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create addresses
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferstrasse 2',
            plz='54321',
            ort='Lieferstadt',
            land='Deutschland'
        )
        
        self.other_adresse = Adresse.objects.create(
            adressen_type='SONSTIGES',
            name='Sonstige Adresse',
            strasse='Sonstige Straße 3',
            plz='11111',
            ort='Sonstige Stadt',
            land='Deutschland'
        )
        
        # Create a MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True
        )
        
        # Create a Vertrag
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
    
    def test_create_aktivitaet_with_vertrag_context(self):
        """Test creating an activity with Vertrag as the only context is valid."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Vertrag prüfen',
            beschreibung='Vertrag auf Vollständigkeit prüfen',
            status='OFFEN',
            prioritaet='HOCH',
            vertrag=self.vertrag
        )
        
        self.assertEqual(aktivitaet.titel, 'Vertrag prüfen')
        self.assertEqual(aktivitaet.vertrag, self.vertrag)
        self.assertIsNone(aktivitaet.mietobjekt)
        self.assertIsNone(aktivitaet.kunde)
        self.assertEqual(aktivitaet.status, 'OFFEN')
        self.assertEqual(aktivitaet.prioritaet, 'HOCH')
    
    def test_create_aktivitaet_with_mietobjekt_context(self):
        """Test creating an activity with MietObjekt as the only context is valid."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Wartung durchführen',
            mietobjekt=self.mietobjekt
        )
        
        self.assertEqual(aktivitaet.mietobjekt, self.mietobjekt)
        self.assertIsNone(aktivitaet.vertrag)
        self.assertIsNone(aktivitaet.kunde)
    
    def test_create_aktivitaet_with_kunde_context(self):
        """Test creating an activity with Kunde as the only context is valid."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Kunde kontaktieren',
            kunde=self.kunde
        )
        
        self.assertEqual(aktivitaet.kunde, self.kunde)
        self.assertIsNone(aktivitaet.vertrag)
        self.assertIsNone(aktivitaet.mietobjekt)
    
    def test_aktivitaet_without_context_is_allowed(self):
        """Test that creating an activity without any context is now allowed (for private/personal tasks)."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Persönliche Aufgabe ohne Kontext',
            beschreibung='Diese Aufgabe hat keinen Vermietungskontext',
            ersteller=self.user
        )
        
        self.assertEqual(aktivitaet.titel, 'Persönliche Aufgabe ohne Kontext')
        self.assertIsNone(aktivitaet.mietobjekt)
        self.assertIsNone(aktivitaet.vertrag)
        self.assertIsNone(aktivitaet.kunde)
        self.assertEqual(aktivitaet.status, 'OFFEN')
    
    def test_aktivitaet_with_multiple_contexts_is_allowed(self):
        """Test that creating an activity with multiple contexts is now allowed."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe mit mehreren Kontexten',
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            ersteller=self.user
        )
        
        self.assertEqual(aktivitaet.vertrag, self.vertrag)
        self.assertEqual(aktivitaet.mietobjekt, self.mietobjekt)
        self.assertIsNone(aktivitaet.kunde)
    
    def test_aktivitaet_with_all_three_contexts_is_allowed(self):
        """Test that creating an activity with all three contexts is now allowed."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe mit allen Kontexten',
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt,
            kunde=self.kunde,
            ersteller=self.user
        )
        
        self.assertEqual(aktivitaet.vertrag, self.vertrag)
        self.assertEqual(aktivitaet.mietobjekt, self.mietobjekt)
        self.assertEqual(aktivitaet.kunde, self.kunde)
    
    def test_aktivitaet_with_only_assigned_user(self):
        """Test creating an activity with only assigned_user (internal assignment)."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Interne Aufgabe',
            vertrag=self.vertrag,
            assigned_user=self.user
        )
        
        self.assertEqual(aktivitaet.assigned_user, self.user)
        self.assertIsNone(aktivitaet.assigned_supplier)
    
    def test_aktivitaet_with_only_assigned_supplier(self):
        """Test creating an activity with only assigned_supplier (external assignment)."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Externe Aufgabe',
            vertrag=self.vertrag,
            assigned_supplier=self.lieferant
        )
        
        self.assertEqual(aktivitaet.assigned_supplier, self.lieferant)
        self.assertIsNone(aktivitaet.assigned_user)
    
    def test_aktivitaet_with_both_assignments(self):
        """Test creating an activity with both internal and external assignment."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Gemeinsame Aufgabe',
            vertrag=self.vertrag,
            assigned_user=self.user,
            assigned_supplier=self.lieferant
        )
        
        self.assertEqual(aktivitaet.assigned_user, self.user)
        self.assertEqual(aktivitaet.assigned_supplier, self.lieferant)
    
    def test_aktivitaet_without_assignments(self):
        """Test creating an activity without any assignment is valid."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Nicht zugewiesene Aufgabe',
            vertrag=self.vertrag
        )
        
        self.assertIsNone(aktivitaet.assigned_user)
        self.assertIsNone(aktivitaet.assigned_supplier)
    
    def test_assigned_supplier_must_be_lieferant_type(self):
        """Test that assigned_supplier must be of type LIEFERANT."""
        with self.assertRaises(ValidationError) as context:
            aktivitaet = Aktivitaet(
                titel='Aufgabe mit falscher Lieferant-Adresse',
                vertrag=self.vertrag,
                assigned_supplier=self.kunde  # Kunde, not LIEFERANT
            )
            aktivitaet.save()
        
        self.assertIn('assigned_supplier', context.exception.error_dict)
        self.assertIn('Lieferant', str(context.exception))
    
    def test_assigned_supplier_with_sonstiges_type_raises_error(self):
        """Test that assigned_supplier with SONSTIGES type raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            aktivitaet = Aktivitaet(
                titel='Aufgabe mit sonstiger Adresse',
                vertrag=self.vertrag,
                assigned_supplier=self.other_adresse
            )
            aktivitaet.save()
        
        self.assertIn('assigned_supplier', context.exception.error_dict)
        self.assertIn('Lieferant', str(context.exception))
    
    def test_default_status_is_offen(self):
        """Test that default status is OFFEN."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Neue Aufgabe',
            vertrag=self.vertrag
        )
        
        self.assertEqual(aktivitaet.status, 'OFFEN')
    
    def test_default_prioritaet_is_normal(self):
        """Test that default priority is NORMAL."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Neue Aufgabe',
            vertrag=self.vertrag
        )
        
        self.assertEqual(aktivitaet.prioritaet, 'NORMAL')
    
    def test_status_choices(self):
        """Test that all status choices work correctly."""
        statuses = ['OFFEN', 'IN_BEARBEITUNG', 'ERLEDIGT', 'ABGEBROCHEN']
        
        for status in statuses:
            aktivitaet = Aktivitaet.objects.create(
                titel=f'Aufgabe mit Status {status}',
                vertrag=self.vertrag,
                status=status
            )
            self.assertEqual(aktivitaet.status, status)
    
    def test_prioritaet_choices(self):
        """Test that all priority choices work correctly."""
        priorities = ['NIEDRIG', 'NORMAL', 'HOCH']
        
        for priority in priorities:
            aktivitaet = Aktivitaet.objects.create(
                titel=f'Aufgabe mit Priorität {priority}',
                mietobjekt=self.mietobjekt,
                prioritaet=priority
            )
            self.assertEqual(aktivitaet.prioritaet, priority)
    
    def test_faellig_am_is_optional(self):
        """Test that faellig_am field is optional."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe ohne Fälligkeit',
            vertrag=self.vertrag
        )
        
        self.assertIsNone(aktivitaet.faellig_am)
    
    def test_faellig_am_can_be_set(self):
        """Test that faellig_am can be set to a date."""
        due_date = date(2024, 12, 31)
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe mit Fälligkeit',
            vertrag=self.vertrag,
            faellig_am=due_date
        )
        
        self.assertEqual(aktivitaet.faellig_am, due_date)
    
    def test_beschreibung_is_optional(self):
        """Test that beschreibung field is optional."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe ohne Beschreibung',
            vertrag=self.vertrag
        )
        
        self.assertEqual(aktivitaet.beschreibung, '')
    
    def test_created_at_auto_set(self):
        """Test that created_at is automatically set."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Neue Aufgabe',
            vertrag=self.vertrag
        )
        
        self.assertIsNotNone(aktivitaet.created_at)
    
    def test_updated_at_auto_set(self):
        """Test that updated_at is automatically set and updated."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe zum Aktualisieren',
            vertrag=self.vertrag
        )
        
        original_updated_at = aktivitaet.updated_at
        self.assertIsNotNone(original_updated_at)
        
        # Update the activity
        aktivitaet.status = 'IN_BEARBEITUNG'
        aktivitaet.save()
        
        # updated_at should have changed
        aktivitaet.refresh_from_db()
        self.assertGreaterEqual(aktivitaet.updated_at, original_updated_at)
    
    def test_str_representation(self):
        """Test the string representation of Aktivitaet."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Aufgabe',
            vertrag=self.vertrag,
            status='IN_BEARBEITUNG'
        )
        
        self.assertIn('Test Aufgabe', str(aktivitaet))
        self.assertIn('In Bearbeitung', str(aktivitaet))
    
    def test_get_context_display_with_vertrag(self):
        """Test get_context_display method with Vertrag."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Vertrag Aufgabe',
            vertrag=self.vertrag
        )
        
        context_display = aktivitaet.get_context_display()
        self.assertIn('Vertrag', context_display)
        self.assertIn(self.vertrag.vertragsnummer, context_display)
    
    def test_get_context_display_with_mietobjekt(self):
        """Test get_context_display method with MietObjekt."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Mietobjekt Aufgabe',
            mietobjekt=self.mietobjekt
        )
        
        context_display = aktivitaet.get_context_display()
        self.assertIn('Mietobjekt', context_display)
        self.assertIn(self.mietobjekt.name, context_display)
    
    def test_get_context_display_with_kunde(self):
        """Test get_context_display method with Kunde."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Kunden Aufgabe',
            kunde=self.kunde
        )
        
        context_display = aktivitaet.get_context_display()
        self.assertIn('Kunde', context_display)
    
    def test_relationship_to_vertrag(self):
        """Test the relationship between Aktivitaet and Vertrag."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Vertrag Aufgabe',
            vertrag=self.vertrag
        )
        
        # Test forward relationship
        self.assertEqual(aktivitaet.vertrag, self.vertrag)
        
        # Test reverse relationship
        self.assertIn(aktivitaet, self.vertrag.aktivitaeten.all())
    
    def test_relationship_to_mietobjekt(self):
        """Test the relationship between Aktivitaet and MietObjekt."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Mietobjekt Aufgabe',
            mietobjekt=self.mietobjekt
        )
        
        # Test forward relationship
        self.assertEqual(aktivitaet.mietobjekt, self.mietobjekt)
        
        # Test reverse relationship
        self.assertIn(aktivitaet, self.mietobjekt.aktivitaeten.all())
    
    def test_relationship_to_kunde(self):
        """Test the relationship between Aktivitaet and Kunde (Adresse)."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Kunden Aufgabe',
            kunde=self.kunde
        )
        
        # Test forward relationship
        self.assertEqual(aktivitaet.kunde, self.kunde)
        
        # Test reverse relationship
        self.assertIn(aktivitaet, self.kunde.aktivitaeten.all())
    
    def test_relationship_to_assigned_user(self):
        """Test the relationship between Aktivitaet and User."""
        aktivitaet = Aktivitaet.objects.create(
            titel='User Aufgabe',
            vertrag=self.vertrag,
            assigned_user=self.user
        )
        
        # Test forward relationship
        self.assertEqual(aktivitaet.assigned_user, self.user)
        
        # Test reverse relationship
        self.assertIn(aktivitaet, self.user.aktivitaeten.all())
    
    def test_relationship_to_assigned_supplier(self):
        """Test the relationship between Aktivitaet and supplier (Adresse)."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Lieferanten Aufgabe',
            vertrag=self.vertrag,
            assigned_supplier=self.lieferant
        )
        
        # Test forward relationship
        self.assertEqual(aktivitaet.assigned_supplier, self.lieferant)
        
        # Test reverse relationship
        self.assertIn(aktivitaet, self.lieferant.aktivitaeten_als_lieferant.all())
    
    def test_ordering_by_created_at_descending(self):
        """Test that activities are ordered by created_at descending."""
        aktivitaet1 = Aktivitaet.objects.create(
            titel='Erste Aufgabe',
            vertrag=self.vertrag
        )
        
        aktivitaet2 = Aktivitaet.objects.create(
            titel='Zweite Aufgabe',
            vertrag=self.vertrag
        )
        
        activities = Aktivitaet.objects.all()
        # Should be ordered by created_at descending (newest first)
        self.assertEqual(list(activities), [aktivitaet2, aktivitaet1])
    
    def test_multiple_aktivitaeten_for_same_vertrag(self):
        """Test that multiple activities can be created for the same Vertrag."""
        aktivitaet1 = Aktivitaet.objects.create(
            titel='Aufgabe 1',
            vertrag=self.vertrag
        )
        
        aktivitaet2 = Aktivitaet.objects.create(
            titel='Aufgabe 2',
            vertrag=self.vertrag
        )
        
        activities = self.vertrag.aktivitaeten.all()
        self.assertEqual(activities.count(), 2)
        self.assertIn(aktivitaet1, activities)
        self.assertIn(aktivitaet2, activities)


class AktivitaetsBereichTest(TestCase):
    """Tests for the AktivitaetsBereich (Activity Category) model."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create some activity categories
        self.bereich_privat = AktivitaetsBereich.objects.create(
            name='Privat',
            beschreibung='Private und persönliche Aufgaben'
        )
        
        self.bereich_sport = AktivitaetsBereich.objects.create(
            name='Sport',
            beschreibung='Sport und Fitness'
        )
    
    def test_create_bereich(self):
        """Test creating a new activity category."""
        bereich = AktivitaetsBereich.objects.create(
            name='Finanzen',
            beschreibung='Finanzielle Aufgaben'
        )
        
        self.assertEqual(bereich.name, 'Finanzen')
        self.assertEqual(bereich.beschreibung, 'Finanzielle Aufgaben')
        self.assertIsNotNone(bereich.created_at)
    
    def test_bereich_str_representation(self):
        """Test the string representation of AktivitaetsBereich."""
        self.assertEqual(str(self.bereich_privat), 'Privat')
        self.assertEqual(str(self.bereich_sport), 'Sport')
    
    def test_bereich_unique_name(self):
        """Test that bereich names must be unique."""
        with self.assertRaises(Exception):  # IntegrityError
            AktivitaetsBereich.objects.create(
                name='Privat',  # Duplicate name
                beschreibung='Another private category'
            )
    
    def test_aktivitaet_with_bereich(self):
        """Test creating an activity with a category."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Joggen gehen',
            bereich=self.bereich_sport,
            ersteller=self.user
        )
        
        self.assertEqual(aktivitaet.bereich, self.bereich_sport)
        self.assertEqual(aktivitaet.titel, 'Joggen gehen')
    
    def test_aktivitaet_without_bereich(self):
        """Test creating an activity without a category."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Aufgabe ohne Bereich',
            ersteller=self.user
        )
        
        self.assertIsNone(aktivitaet.bereich)
    
    def test_bereich_delete_sets_null(self):
        """Test that deleting a bereich sets aktivitaet.bereich to NULL."""
        aktivitaet = Aktivitaet.objects.create(
            titel='Sport-Aufgabe',
            bereich=self.bereich_sport,
            ersteller=self.user
        )
        
        # Delete the bereich
        self.bereich_sport.delete()
        
        # Refresh the aktivitaet from DB
        aktivitaet.refresh_from_db()
        
        # bereich should now be NULL
        self.assertIsNone(aktivitaet.bereich)
    
    def test_bereich_relationship(self):
        """Test the reverse relationship from bereich to aktivitaeten."""
        aktivitaet1 = Aktivitaet.objects.create(
            titel='Private Aufgabe 1',
            bereich=self.bereich_privat,
            ersteller=self.user
        )
        
        aktivitaet2 = Aktivitaet.objects.create(
            titel='Private Aufgabe 2',
            bereich=self.bereich_privat,
            ersteller=self.user
        )
        
        # Test reverse relationship
        self.assertEqual(self.bereich_privat.aktivitaeten.count(), 2)
        self.assertIn(aktivitaet1, self.bereich_privat.aktivitaeten.all())
        self.assertIn(aktivitaet2, self.bereich_privat.aktivitaeten.all())
    
    def test_bereich_ordering(self):
        """Test that bereiche are ordered by name."""
        bereich_a = AktivitaetsBereich.objects.create(name='A-Bereich')
        bereich_z = AktivitaetsBereich.objects.create(name='Z-Bereich')
        
        bereiche = list(AktivitaetsBereich.objects.all())
        
        # Should be ordered alphabetically
        self.assertEqual(bereiche[0].name, 'A-Bereich')
        self.assertTrue(bereiche[-1].name == 'Z-Bereich')



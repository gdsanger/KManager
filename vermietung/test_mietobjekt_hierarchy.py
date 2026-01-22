"""
Tests for MietObjekt hierarchical parent-child relationship functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from core.models import Adresse
from vermietung.models import MietObjekt
from vermietung.forms import MietObjektForm
from decimal import Decimal


class MietObjektHierarchyTestCase(TestCase):
    """Test case for MietObjekt parent-child hierarchy functionality."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a user with Vermietung access
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=False
        )
        # Create Vermietung group and add user to it
        self.vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(self.vermietung_group)
        
        # Create test standort (location)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Berlin',
            strasse='Berliner Str. 1',
            plz='10115',
            ort='Berlin',
            land='Deutschland'
        )
        
        # Create test MietObjekte in a hierarchy
        self.building = MietObjekt.objects.create(
            name='Gebäude A',
            type='GEBAEUDE',
            beschreibung='Hauptgebäude',
            fläche=Decimal('1000.00'),
            standort=self.standort,
            mietpreis=Decimal('10000.00'),
            verfuegbar=True
        )
        
        self.apartment1 = MietObjekt.objects.create(
            name='Wohnung 1',
            type='RAUM',
            beschreibung='Erdgeschoss',
            fläche=Decimal('50.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            parent=self.building,
            verfuegbar=True
        )
        
        self.apartment2 = MietObjekt.objects.create(
            name='Wohnung 2',
            type='RAUM',
            beschreibung='Erster Stock',
            fläche=Decimal('60.00'),
            standort=self.standort,
            mietpreis=Decimal('1200.00'),
            parent=self.building,
            verfuegbar=True
        )
        
        self.client = Client()
    
    def test_parent_child_relationship(self):
        """Test that parent-child relationships are correctly set up."""
        # Check parent relationship
        self.assertEqual(self.apartment1.parent, self.building)
        self.assertEqual(self.apartment2.parent, self.building)
        
        # Check children relationship
        children = list(self.building.children.all())
        self.assertEqual(len(children), 2)
        self.assertIn(self.apartment1, children)
        self.assertIn(self.apartment2, children)
    
    def test_hierarchy_level(self):
        """Test that hierarchy levels are correctly calculated."""
        # Building is at root level
        self.assertEqual(self.building.get_hierarchy_level(), 0)
        
        # Apartments are at level 1
        self.assertEqual(self.apartment1.get_hierarchy_level(), 1)
        self.assertEqual(self.apartment2.get_hierarchy_level(), 1)
        
        # Create a deeper level
        room = MietObjekt.objects.create(
            name='Raum 1.1',
            type='RAUM',
            beschreibung='Zimmer in Wohnung 1',
            fläche=Decimal('20.00'),
            standort=self.standort,
            mietpreis=Decimal('400.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        self.assertEqual(room.get_hierarchy_level(), 2)
    
    def test_get_root_parent(self):
        """Test that root parent is correctly identified."""
        # Building is its own root
        self.assertEqual(self.building.get_root_parent(), self.building)
        
        # Apartments have building as root
        self.assertEqual(self.apartment1.get_root_parent(), self.building)
        self.assertEqual(self.apartment2.get_root_parent(), self.building)
        
        # Deeper level also has building as root
        room = MietObjekt.objects.create(
            name='Raum 1.1',
            type='RAUM',
            beschreibung='Zimmer in Wohnung 1',
            fläche=Decimal('20.00'),
            standort=self.standort,
            mietpreis=Decimal('400.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        self.assertEqual(room.get_root_parent(), self.building)
    
    def test_get_all_children(self):
        """Test that all children are correctly retrieved recursively."""
        # Create deeper hierarchy
        room1 = MietObjekt.objects.create(
            name='Raum 1.1',
            type='RAUM',
            beschreibung='Zimmer in Wohnung 1',
            fläche=Decimal('20.00'),
            standort=self.standort,
            mietpreis=Decimal('400.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        
        room2 = MietObjekt.objects.create(
            name='Raum 1.2',
            type='RAUM',
            beschreibung='Zweites Zimmer in Wohnung 1',
            fläche=Decimal('15.00'),
            standort=self.standort,
            mietpreis=Decimal('300.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        
        # Building should have 4 descendants (2 apartments + 2 rooms)
        descendants = self.building.get_all_children()
        self.assertEqual(descendants.count(), 4)
        self.assertIn(self.apartment1, descendants)
        self.assertIn(self.apartment2, descendants)
        self.assertIn(room1, descendants)
        self.assertIn(room2, descendants)
        
        # Apartment1 should have 2 descendants (2 rooms)
        descendants = self.apartment1.get_all_children()
        self.assertEqual(descendants.count(), 2)
        self.assertIn(room1, descendants)
        self.assertIn(room2, descendants)
    
    def test_circular_reference_self(self):
        """Test that an object cannot be its own parent."""
        self.building.parent = self.building
        with self.assertRaises(ValidationError) as context:
            self.building.full_clean()
        self.assertIn('parent', context.exception.message_dict)
    
    def test_circular_reference_direct_child(self):
        """Test that a direct child cannot be set as parent."""
        # Try to set apartment1 (child) as parent of building
        self.building.parent = self.apartment1
        with self.assertRaises(ValidationError) as context:
            self.building.full_clean()
        self.assertIn('parent', context.exception.message_dict)
    
    def test_circular_reference_indirect_child(self):
        """Test that an indirect child (grandchild) cannot be set as parent."""
        # Create a grandchild
        room = MietObjekt.objects.create(
            name='Raum 1.1',
            type='RAUM',
            beschreibung='Zimmer in Wohnung 1',
            fläche=Decimal('20.00'),
            standort=self.standort,
            mietpreis=Decimal('400.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        
        # Try to set grandchild as parent of building
        self.building.parent = room
        with self.assertRaises(ValidationError) as context:
            self.building.full_clean()
        self.assertIn('parent', context.exception.message_dict)
    
    def test_form_excludes_self_and_descendants(self):
        """Test that the form excludes self and descendants from parent choices."""
        # Create a deeper hierarchy
        room = MietObjekt.objects.create(
            name='Raum 1.1',
            type='RAUM',
            beschreibung='Zimmer in Wohnung 1',
            fläche=Decimal('20.00'),
            standort=self.standort,
            mietpreis=Decimal('400.00'),
            parent=self.apartment1,
            verfuegbar=True
        )
        
        # Form for editing apartment1 should exclude apartment1 and room
        form = MietObjektForm(instance=self.apartment1)
        parent_choices = list(form.fields['parent'].queryset)
        
        # Should include building (parent) and apartment2 (sibling)
        self.assertIn(self.building, parent_choices)
        self.assertIn(self.apartment2, parent_choices)
        
        # Should NOT include self or children
        self.assertNotIn(self.apartment1, parent_choices)
        self.assertNotIn(room, parent_choices)
    
    def test_detail_view_shows_hierarchy(self):
        """Test that detail view shows parent and children."""
        self.client.login(username='testuser', password='testpass123')
        
        # Check building detail page
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.building.pk}))
        self.assertEqual(response.status_code, 200)
        
        # Should show children
        self.assertContains(response, 'Wohnung 1')
        self.assertContains(response, 'Wohnung 2')
        self.assertContains(response, 'Untergeordnete Objekte')
        
        # Check apartment detail page
        response = self.client.get(reverse('vermietung:mietobjekt_detail', kwargs={'pk': self.apartment1.pk}))
        self.assertEqual(response.status_code, 200)
        
        # Should show parent
        self.assertContains(response, 'Gebäude A')
        self.assertContains(response, 'Übergeordnetes Objekt')
    
    def test_create_with_parent(self):
        """Test creating a new MietObjekt with a parent."""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'name': 'Wohnung 3',
            'type': 'RAUM',
            'beschreibung': 'Neues Apartment',
            'fläche': '55.00',
            'standort': self.standort.id,
            'mietpreis': '1100.00',
            'verfuegbare_einheiten': '1',
            'verfuegbar': True,
            'parent': self.building.id
        }
        
        response = self.client.post(reverse('vermietung:mietobjekt_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that object was created with correct parent
        apartment3 = MietObjekt.objects.get(name='Wohnung 3')
        self.assertEqual(apartment3.parent, self.building)
        self.assertIn(apartment3, self.building.children.all())
    
    def test_update_parent(self):
        """Test updating the parent of a MietObjekt."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a second building
        building2 = MietObjekt.objects.create(
            name='Gebäude B',
            type='GEBAEUDE',
            beschreibung='Zweites Gebäude',
            fläche=Decimal('800.00'),
            standort=self.standort,
            mietpreis=Decimal('8000.00'),
            verfuegbar=True
        )
        
        # Move apartment1 from building to building2
        data = {
            'name': self.apartment1.name,
            'type': self.apartment1.type,
            'beschreibung': self.apartment1.beschreibung,
            'fläche': str(self.apartment1.fläche),
            'standort': self.standort.id,
            'mietpreis': str(self.apartment1.mietpreis),
            'verfuegbare_einheiten': self.apartment1.verfuegbare_einheiten,
            'verfuegbar': self.apartment1.verfuegbar,
            'parent': building2.id
        }
        
        response = self.client.post(
            reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.apartment1.pk}),
            data
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that parent was updated
        self.apartment1.refresh_from_db()
        self.assertEqual(self.apartment1.parent, building2)
        self.assertIn(self.apartment1, building2.children.all())
        self.assertNotIn(self.apartment1, self.building.children.all())
    
    def test_remove_parent(self):
        """Test removing the parent from a MietObjekt."""
        self.client.login(username='testuser', password='testpass123')
        
        # Remove parent from apartment1
        data = {
            'name': self.apartment1.name,
            'type': self.apartment1.type,
            'beschreibung': self.apartment1.beschreibung,
            'fläche': str(self.apartment1.fläche),
            'standort': self.standort.id,
            'mietpreis': str(self.apartment1.mietpreis),
            'verfuegbare_einheiten': self.apartment1.verfuegbare_einheiten,
            'verfuegbar': self.apartment1.verfuegbar,
            'parent': ''  # Empty parent
        }
        
        response = self.client.post(
            reverse('vermietung:mietobjekt_edit', kwargs={'pk': self.apartment1.pk}),
            data
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that parent was removed
        self.apartment1.refresh_from_db()
        self.assertIsNone(self.apartment1.parent)
        self.assertNotIn(self.apartment1, self.building.children.all())

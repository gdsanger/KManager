"""
Tests for Kostenarten (Cost Types) model
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from core.models import Kostenart


class KostenartModelTestCase(TestCase):
    """Test Kostenart model"""
    
    def test_create_hauptkostenart(self):
        """Test creating a main cost type (Hauptkostenart)"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        
        self.assertIsNotNone(hauptkostenart.pk)
        self.assertEqual(hauptkostenart.name, "Personal")
        self.assertIsNone(hauptkostenart.parent)
        self.assertTrue(hauptkostenart.is_hauptkostenart())
    
    def test_create_unterkostenart(self):
        """Test creating a sub cost type (Unterkostenart)"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        unterkostenart = Kostenart.objects.create(
            name="Gehälter",
            parent=hauptkostenart
        )
        
        self.assertIsNotNone(unterkostenart.pk)
        self.assertEqual(unterkostenart.name, "Gehälter")
        self.assertEqual(unterkostenart.parent, hauptkostenart)
        self.assertFalse(unterkostenart.is_hauptkostenart())
    
    def test_hauptkostenart_can_have_multiple_children(self):
        """Test that a Hauptkostenart can have multiple Unterkostenarten"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        
        uk1 = Kostenart.objects.create(name="Gehälter", parent=hauptkostenart)
        uk2 = Kostenart.objects.create(name="Sozialversicherung", parent=hauptkostenart)
        uk3 = Kostenart.objects.create(name="Weiterbildung", parent=hauptkostenart)
        
        self.assertEqual(hauptkostenart.children.count(), 3)
        self.assertIn(uk1, hauptkostenart.children.all())
        self.assertIn(uk2, hauptkostenart.children.all())
        self.assertIn(uk3, hauptkostenart.children.all())
    
    def test_prevent_three_level_hierarchy(self):
        """Test that cost types cannot have more than one level of hierarchy"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        unterkostenart = Kostenart.objects.create(
            name="Gehälter",
            parent=hauptkostenart
        )
        
        # Try to create a third level - should raise ValidationError
        invalid_kostenart = Kostenart(
            name="Invalid Sub-Sub Type",
            parent=unterkostenart
        )
        
        with self.assertRaises(ValidationError) as context:
            invalid_kostenart.clean()
        
        self.assertIn('parent', context.exception.message_dict)
        self.assertIn('Hierarchieebene', str(context.exception))
    
    def test_delete_hauptkostenart_with_children_protected(self):
        """Test that Hauptkostenart with children cannot be deleted"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        Kostenart.objects.create(name="Gehälter", parent=hauptkostenart)
        
        # Try to delete - should raise ProtectedError due to PROTECT on_delete
        with self.assertRaises(ProtectedError):
            hauptkostenart.delete()
        
        # Verify it still exists
        self.assertTrue(Kostenart.objects.filter(pk=hauptkostenart.pk).exists())
    
    def test_delete_hauptkostenart_without_children(self):
        """Test that Hauptkostenart without children can be deleted"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        pk = hauptkostenart.pk
        
        hauptkostenart.delete()
        
        self.assertFalse(Kostenart.objects.filter(pk=pk).exists())
    
    def test_delete_unterkostenart(self):
        """Test that Unterkostenart can be deleted"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        unterkostenart = Kostenart.objects.create(
            name="Gehälter",
            parent=hauptkostenart
        )
        pk = unterkostenart.pk
        
        unterkostenart.delete()
        
        self.assertFalse(Kostenart.objects.filter(pk=pk).exists())
        self.assertTrue(Kostenart.objects.filter(pk=hauptkostenart.pk).exists())
    
    def test_str_hauptkostenart(self):
        """Test string representation of Hauptkostenart"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        
        self.assertEqual(str(hauptkostenart), "Personal")
    
    def test_str_unterkostenart(self):
        """Test string representation of Unterkostenart"""
        hauptkostenart = Kostenart.objects.create(name="Personal")
        unterkostenart = Kostenart.objects.create(
            name="Gehälter",
            parent=hauptkostenart
        )
        
        self.assertEqual(str(unterkostenart), "Personal > Gehälter")
    
    def test_ordering(self):
        """Test that Kostenarten are ordered by name"""
        Kostenart.objects.create(name="Zinsen")
        Kostenart.objects.create(name="Personal")
        Kostenart.objects.create(name="Abschreibungen")
        
        kostenarten = list(Kostenart.objects.all())
        
        self.assertEqual(kostenarten[0].name, "Abschreibungen")
        self.assertEqual(kostenarten[1].name, "Personal")
        self.assertEqual(kostenarten[2].name, "Zinsen")
    
    def test_create_complex_structure(self):
        """Test creating a more complex structure with multiple Hauptkostenarten"""
        # Create first Hauptkostenart with children
        personal = Kostenart.objects.create(name="Personal")
        Kostenart.objects.create(name="Gehälter", parent=personal)
        Kostenart.objects.create(name="Sozialversicherung", parent=personal)
        
        # Create second Hauptkostenart with children
        material = Kostenart.objects.create(name="Material")
        Kostenart.objects.create(name="Rohstoffe", parent=material)
        Kostenart.objects.create(name="Verbrauchsmaterial", parent=material)
        
        # Verify structure
        self.assertEqual(Kostenart.objects.filter(parent__isnull=True).count(), 2)
        self.assertEqual(personal.children.count(), 2)
        self.assertEqual(material.children.count(), 2)
        self.assertEqual(Kostenart.objects.count(), 6)

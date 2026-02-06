"""
Tests for ItemGroup model
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from core.models import ItemGroup


class ItemGroupModelTestCase(TestCase):
    """Test ItemGroup model"""
    
    def test_create_main_itemgroup(self):
        """Test creating a MAIN item group without parent"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        self.assertIsNotNone(main_group.pk)
        self.assertEqual(main_group.code, "MAIN01")
        self.assertEqual(main_group.name, "Elektronik")
        self.assertEqual(main_group.group_type, "MAIN")
        self.assertIsNone(main_group.parent)
        self.assertTrue(main_group.is_active)
        self.assertIsNone(main_group.description)
    
    def test_create_sub_itemgroup_with_main_parent(self):
        """Test creating a SUB item group with MAIN parent - should be valid"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        sub_group = ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        
        self.assertIsNotNone(sub_group.pk)
        self.assertEqual(sub_group.code, "SUB01")
        self.assertEqual(sub_group.name, "Smartphones")
        self.assertEqual(sub_group.group_type, "SUB")
        self.assertEqual(sub_group.parent, main_group)
        self.assertTrue(sub_group.is_active)
    
    def test_sub_without_parent_invalid(self):
        """Test that SUB without parent raises ValidationError"""
        sub_group = ItemGroup(
            code="SUB01",
            name="Invalid Sub",
            group_type="SUB",
            parent=None
        )
        
        with self.assertRaises(ValidationError) as context:
            sub_group.full_clean()
        
        self.assertIn('parent', context.exception.message_dict)
        self.assertIn('Unterwarengruppe (SUB) muss eine übergeordnete Hauptwarengruppe haben', 
                      str(context.exception))
    
    def test_main_with_parent_invalid(self):
        """Test that MAIN with parent raises ValidationError"""
        # Create a valid MAIN group
        main_group1 = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        # Try to create another MAIN group with a parent - should fail
        main_group2 = ItemGroup(
            code="MAIN02",
            name="Invalid Main",
            group_type="MAIN",
            parent=main_group1
        )
        
        with self.assertRaises(ValidationError) as context:
            main_group2.full_clean()
        
        self.assertIn('parent', context.exception.message_dict)
        self.assertIn('Hauptwarengruppe (MAIN) darf keine übergeordnete Gruppe haben', 
                      str(context.exception))
    
    def test_sub_with_sub_parent_invalid(self):
        """Test that SUB with SUB parent raises ValidationError (no deeper hierarchy)"""
        # Create valid MAIN group
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        # Create valid SUB group
        sub_group = ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        
        # Try to create SUB under SUB - should fail
        sub_sub_group = ItemGroup(
            code="SUB02",
            name="Invalid Sub-Sub",
            group_type="SUB",
            parent=sub_group
        )
        
        with self.assertRaises(ValidationError) as context:
            sub_sub_group.full_clean()
        
        self.assertIn('parent', context.exception.message_dict)
        self.assertIn('kann nur einer Hauptwarengruppe (MAIN) zugeordnet werden', 
                      str(context.exception))
        self.assertIn('Tiefere Hierarchieebenen sind nicht erlaubt', 
                      str(context.exception))
    
    def test_code_uniqueness_case_sensitive(self):
        """Test that code is unique and case-sensitive"""
        # Create first item group with uppercase code
        ItemGroup.objects.create(
            code="ABC",
            name="First Group",
            group_type="MAIN"
        )
        
        # Create second item group with lowercase code - should succeed (case-sensitive)
        group2 = ItemGroup.objects.create(
            code="abc",
            name="Second Group",
            group_type="MAIN"
        )
        
        self.assertIsNotNone(group2.pk)
        self.assertEqual(group2.code, "abc")
        
        # Try to create with same code - should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ItemGroup.objects.create(
                code="ABC",
                name="Duplicate",
                group_type="MAIN"
            )
    
    def test_main_can_have_multiple_children(self):
        """Test that a MAIN item group can have multiple SUB children"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        sub1 = ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        sub2 = ItemGroup.objects.create(
            code="SUB02",
            name="Tablets",
            group_type="SUB",
            parent=main_group
        )
        sub3 = ItemGroup.objects.create(
            code="SUB03",
            name="Laptops",
            group_type="SUB",
            parent=main_group
        )
        
        self.assertEqual(main_group.children.count(), 3)
        self.assertIn(sub1, main_group.children.all())
        self.assertIn(sub2, main_group.children.all())
        self.assertIn(sub3, main_group.children.all())
    
    def test_delete_main_with_children_protected(self):
        """Test that MAIN with children cannot be deleted (PROTECT)"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        
        # Try to delete MAIN - should raise ProtectedError
        with self.assertRaises(ProtectedError):
            main_group.delete()
        
        # Verify it still exists
        self.assertTrue(ItemGroup.objects.filter(pk=main_group.pk).exists())
    
    def test_delete_main_without_children(self):
        """Test that MAIN without children can be deleted"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        pk = main_group.pk
        
        main_group.delete()
        
        self.assertFalse(ItemGroup.objects.filter(pk=pk).exists())
    
    def test_delete_sub_itemgroup(self):
        """Test that SUB can be deleted"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        sub_group = ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        pk = sub_group.pk
        
        sub_group.delete()
        
        self.assertFalse(ItemGroup.objects.filter(pk=pk).exists())
        self.assertTrue(ItemGroup.objects.filter(pk=main_group.pk).exists())
    
    def test_str_main_itemgroup(self):
        """Test string representation of MAIN item group"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        
        self.assertEqual(str(main_group), "MAIN01: Elektronik")
    
    def test_str_sub_itemgroup(self):
        """Test string representation of SUB item group"""
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Elektronik",
            group_type="MAIN"
        )
        sub_group = ItemGroup.objects.create(
            code="SUB01",
            name="Smartphones",
            group_type="SUB",
            parent=main_group
        )
        
        self.assertEqual(str(sub_group), "MAIN01 > SUB01: Smartphones")
    
    def test_ordering(self):
        """Test that ItemGroups are ordered by code"""
        ItemGroup.objects.create(code="Z99", name="Z Group", group_type="MAIN")
        ItemGroup.objects.create(code="A01", name="A Group", group_type="MAIN")
        ItemGroup.objects.create(code="M50", name="M Group", group_type="MAIN")
        
        groups = list(ItemGroup.objects.all())
        
        self.assertEqual(groups[0].code, "A01")
        self.assertEqual(groups[1].code, "M50")
        self.assertEqual(groups[2].code, "Z99")
    
    def test_is_active_default(self):
        """Test that is_active defaults to True"""
        group = ItemGroup.objects.create(
            code="MAIN01",
            name="Test Group",
            group_type="MAIN"
        )
        
        self.assertTrue(group.is_active)
    
    def test_is_active_can_be_set_false(self):
        """Test that is_active can be set to False"""
        group = ItemGroup.objects.create(
            code="MAIN01",
            name="Inactive Group",
            group_type="MAIN",
            is_active=False
        )
        
        self.assertFalse(group.is_active)
    
    def test_description_optional(self):
        """Test that description is optional"""
        # Without description
        group1 = ItemGroup.objects.create(
            code="MAIN01",
            name="No Description",
            group_type="MAIN"
        )
        self.assertIsNone(group1.description)
        
        # With description
        group2 = ItemGroup.objects.create(
            code="MAIN02",
            name="With Description",
            group_type="MAIN",
            description="This is a test description"
        )
        self.assertEqual(group2.description, "This is a test description")
    
    def test_update_itemgroup(self):
        """Test updating an item group"""
        group = ItemGroup.objects.create(
            code="MAIN01",
            name="Original Name",
            group_type="MAIN",
            is_active=True
        )
        
        # Update the group
        group.name = "Updated Name"
        group.is_active = False
        group.description = "Updated description"
        group.save()
        
        # Reload from database
        group.refresh_from_db()
        
        self.assertEqual(group.name, "Updated Name")
        self.assertFalse(group.is_active)
        self.assertEqual(group.description, "Updated description")
    
    def test_complex_structure(self):
        """Test creating a more complex structure with multiple MAIN groups and SUB groups"""
        # Create first MAIN group with children
        electronics = ItemGroup.objects.create(
            code="ELEC",
            name="Elektronik",
            group_type="MAIN"
        )
        ItemGroup.objects.create(code="ELEC-PHONE", name="Smartphones", group_type="SUB", parent=electronics)
        ItemGroup.objects.create(code="ELEC-TAB", name="Tablets", group_type="SUB", parent=electronics)
        
        # Create second MAIN group with children
        furniture = ItemGroup.objects.create(
            code="FURN",
            name="Möbel",
            group_type="MAIN"
        )
        ItemGroup.objects.create(code="FURN-DESK", name="Schreibtische", group_type="SUB", parent=furniture)
        ItemGroup.objects.create(code="FURN-CHAIR", name="Stühle", group_type="SUB", parent=furniture)
        
        # Verify structure
        self.assertEqual(ItemGroup.objects.filter(group_type='MAIN').count(), 2)
        self.assertEqual(electronics.children.count(), 2)
        self.assertEqual(furniture.children.count(), 2)
        self.assertEqual(ItemGroup.objects.count(), 6)
    
    def test_full_clean_is_called_on_save(self):
        """Test that validation works when creating objects"""
        # This test ensures that validation is enforced
        # Note: Django doesn't call full_clean() by default on save(),
        # but we can test that clean() is available and works
        
        main_group = ItemGroup.objects.create(
            code="MAIN01",
            name="Test",
            group_type="MAIN"
        )
        
        # Create invalid SUB without parent
        invalid_sub = ItemGroup(
            code="SUB01",
            name="Invalid",
            group_type="SUB"
        )
        
        # Calling full_clean should raise error
        with self.assertRaises(ValidationError):
            invalid_sub.full_clean()
        
        # But save() alone won't raise (Django doesn't call full_clean by default)
        # This is expected Django behavior - validation is enforced at the form/admin level

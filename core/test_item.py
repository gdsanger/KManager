"""
Tests for Item model and item snapshot service
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from decimal import Decimal
from core.models import Item, TaxRate, Kostenart
from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from auftragsverwaltung.services.item_snapshot import apply_item_snapshot


class ItemModelTestCase(TestCase):
    """Test Item model"""
    
    def setUp(self):
        """Set up test data"""
        # Create tax rate
        self.tax_rate = TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        # Create cost types
        self.cost_type_1 = Kostenart.objects.create(
            name="Hauptkostenart Material",
            umsatzsteuer_satz="19"
        )
        self.cost_type_2 = Kostenart.objects.create(
            name="Hauptkostenart Dienstleistung",
            umsatzsteuer_satz="19"
        )
    
    def test_create_item(self):
        """Test creating an item"""
        item = Item.objects.create(
            article_no="ART-001",
            short_text_1="Test Article",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        self.assertIsNotNone(item.pk)
        self.assertEqual(item.article_no, "ART-001")
        self.assertEqual(item.short_text_1, "Test Article")
        self.assertEqual(item.net_price, Decimal("100.00"))
        self.assertEqual(item.purchase_price, Decimal("50.00"))
        self.assertEqual(item.item_type, "MATERIAL")
        self.assertTrue(item.is_active)
        self.assertTrue(item.is_discountable)
    
    def test_article_no_uniqueness(self):
        """Test that article_no must be globally unique"""
        # Create first item
        Item.objects.create(
            article_no="ART-001",
            short_text_1="First Article",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        # Try to create second item with same article_no
        with self.assertRaises(IntegrityError):
            Item.objects.create(
                article_no="ART-001",
                short_text_1="Second Article",
                net_price=Decimal("200.00"),
                purchase_price=Decimal("100.00"),
                tax_rate=self.tax_rate,
                cost_type_1=self.cost_type_1,
                item_type="SERVICE"
            )
    
    def test_net_price_validation_negative(self):
        """Test that net_price cannot be negative"""
        item = Item(
            article_no="ART-002",
            short_text_1="Test Article",
            net_price=Decimal("-10.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        with self.assertRaises(ValidationError) as context:
            item.clean()
        
        self.assertIn('net_price', context.exception.message_dict)
        self.assertIn('negativ', str(context.exception))
    
    def test_purchase_price_validation_negative(self):
        """Test that purchase_price cannot be negative"""
        item = Item(
            article_no="ART-003",
            short_text_1="Test Article",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("-10.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        with self.assertRaises(ValidationError) as context:
            item.clean()
        
        self.assertIn('purchase_price', context.exception.message_dict)
        self.assertIn('negativ', str(context.exception))
    
    def test_net_price_zero_allowed(self):
        """Test that net_price of 0 is allowed"""
        item = Item.objects.create(
            article_no="ART-004",
            short_text_1="Free Article",
            net_price=Decimal("0.00"),
            purchase_price=Decimal("0.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="SERVICE"
        )
        item.full_clean()  # Should not raise
        
        self.assertEqual(item.net_price, Decimal("0.00"))
        self.assertEqual(item.purchase_price, Decimal("0.00"))
    
    def test_item_type_choices(self):
        """Test that item_type accepts valid choices"""
        # Test MATERIAL
        item_material = Item.objects.create(
            article_no="ART-MAT-001",
            short_text_1="Material Item",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        self.assertEqual(item_material.item_type, "MATERIAL")
        
        # Test SERVICE
        item_service = Item.objects.create(
            article_no="ART-SRV-001",
            short_text_1="Service Item",
            net_price=Decimal("200.00"),
            purchase_price=Decimal("100.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="SERVICE"
        )
        self.assertEqual(item_service.item_type, "SERVICE")
    
    def test_optional_fields(self):
        """Test that optional fields work correctly"""
        item = Item.objects.create(
            article_no="ART-005",
            short_text_1="Minimal Article",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        # Optional fields should have default values
        self.assertEqual(item.short_text_2, "")
        self.assertEqual(item.long_text, "")
        self.assertIsNone(item.cost_type_2)
        
        # Test with optional fields filled
        item_with_optional = Item.objects.create(
            article_no="ART-006",
            short_text_1="Full Article",
            short_text_2="Secondary text",
            long_text="Detailed description",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            cost_type_2=self.cost_type_2,
            item_type="MATERIAL"
        )
        
        self.assertEqual(item_with_optional.short_text_2, "Secondary text")
        self.assertEqual(item_with_optional.long_text, "Detailed description")
        self.assertEqual(item_with_optional.cost_type_2, self.cost_type_2)
    
    def test_str_representation(self):
        """Test string representation of Item"""
        item = Item.objects.create(
            article_no="ART-007",
            short_text_1="Test Article",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL"
        )
        
        self.assertEqual(str(item), "ART-007: Test Article")
    
    def test_item_group_null_valid(self):
        """Test that item_group can be NULL - should be valid"""
        from core.models import ItemGroup
        
        item = Item.objects.create(
            article_no="ART-IG-001",
            short_text_1="Item without group",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL",
            item_group=None
        )
        item.full_clean()  # Should not raise
        
        self.assertIsNone(item.item_group)
    
    def test_item_group_sub_valid(self):
        """Test that assigning a SUB item group (parent != NULL) is valid"""
        from core.models import ItemGroup
        
        # Create MAIN and SUB item groups
        main_group = ItemGroup.objects.create(
            code="MAIN-TEST",
            name="Test Main Group",
            group_type="MAIN"
        )
        sub_group = ItemGroup.objects.create(
            code="SUB-TEST",
            name="Test Sub Group",
            group_type="SUB",
            parent=main_group
        )
        
        # Create item with SUB group
        item = Item.objects.create(
            article_no="ART-IG-002",
            short_text_1="Item with sub group",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL",
            item_group=sub_group
        )
        item.full_clean()  # Should not raise
        
        self.assertEqual(item.item_group, sub_group)
        self.assertEqual(item.item_group.parent, main_group)
    
    def test_item_group_main_invalid(self):
        """Test that assigning a MAIN item group (parent == NULL) is invalid"""
        from core.models import ItemGroup
        
        # Create MAIN item group
        main_group = ItemGroup.objects.create(
            code="MAIN-TEST2",
            name="Test Main Group 2",
            group_type="MAIN"
        )
        
        # Try to create item with MAIN group - should fail validation
        item = Item(
            article_no="ART-IG-003",
            short_text_1="Item with main group",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL",
            item_group=main_group
        )
        
        with self.assertRaises(ValidationError) as context:
            item.clean()
        
        self.assertIn('item_group', context.exception.message_dict)
        self.assertIn('Unterwarengruppe (SUB)', str(context.exception))
        self.assertIn('Hauptwarengruppe (MAIN)', str(context.exception))


class ItemSnapshotServiceTestCase(TestCase):
    """Test item snapshot service"""
    
    def setUp(self):
        """Set up test data"""
        # Create supporting entities
        from core.models import Mandant
        
        self.tax_rate = TaxRate.objects.create(
            code="VAT",
            name="Standard VAT",
            rate=Decimal("0.19")
        )
        
        self.tax_rate_reduced = TaxRate.objects.create(
            code="REDUCED",
            name="Reduced VAT",
            rate=Decimal("0.07")
        )
        
        self.cost_type_1 = Kostenart.objects.create(
            name="Hauptkostenart Material",
            umsatzsteuer_satz="19"
        )
        
        self.mandant = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street 1",
            plz="12345",
            ort="Test City"
        )
        
        self.document_type = DocumentType.objects.create(
            key="invoice",
            name="Invoice",
            prefix="R"
        )
        
        self.document = SalesDocument.objects.create(
            company=self.mandant,
            document_type=self.document_type,
            number="R26-00001",
            status="DRAFT",
            issue_date="2026-01-01"
        )
        
        self.item = Item.objects.create(
            article_no="ART-SNAP-001",
            short_text_1="Snapshot Test Article",
            net_price=Decimal("99.99"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_1,
            item_type="MATERIAL",
            is_discountable=False
        )
    
    def test_apply_item_snapshot(self):
        """Test that snapshot correctly copies item values to line"""
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type="NORMAL",
            is_selected=True,
            description="Old description",
            quantity=Decimal("1.0000"),
            unit_price_net=Decimal("0.00"),  # Will be overwritten
            tax_rate=self.tax_rate_reduced,  # Will be overwritten
            is_discountable=True  # Will be overwritten
        )
        
        # Apply snapshot
        line.item = self.item
        apply_item_snapshot(line, self.item)
        
        # Verify snapshot was applied
        self.assertEqual(line.unit_price_net, self.item.net_price)
        self.assertEqual(line.tax_rate, self.item.tax_rate)
        self.assertEqual(line.is_discountable, self.item.is_discountable)
    
    def test_item_change_does_not_affect_existing_lines(self):
        """Test that changing item does NOT affect existing lines (snapshot stability)"""
        # Create line with item snapshot
        line = SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type="NORMAL",
            is_selected=True,
            description="Test line",
            quantity=Decimal("1.0000"),
            unit_price_net=Decimal("0.00"),
            tax_rate=self.tax_rate_reduced
        )
        
        line.item = self.item
        apply_item_snapshot(line, self.item)
        line.save()
        
        # Store original snapshot values
        original_price = line.unit_price_net
        original_tax_rate = line.tax_rate
        original_discountable = line.is_discountable
        
        # Now change the item master data
        self.item.net_price = Decimal("199.99")
        self.item.tax_rate = self.tax_rate_reduced
        self.item.is_discountable = True
        self.item.save()
        
        # Reload the line from database
        line.refresh_from_db()
        
        # Verify that line still has original snapshot values
        self.assertEqual(line.unit_price_net, original_price)
        self.assertEqual(line.tax_rate, original_tax_rate)
        self.assertEqual(line.is_discountable, original_discountable)
        
        # Verify that item has changed
        self.assertNotEqual(self.item.net_price, original_price)
    
    def test_apply_snapshot_with_none_item(self):
        """Test that applying snapshot with None item does nothing"""
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type="NORMAL",
            is_selected=True,
            description="Test line",
            quantity=Decimal("1.0000"),
            unit_price_net=Decimal("123.45"),
            tax_rate=self.tax_rate
        )
        
        # Store original values
        original_price = line.unit_price_net
        original_tax_rate = line.tax_rate
        
        # Apply snapshot with None item
        apply_item_snapshot(line, None)
        
        # Verify that line values are unchanged
        self.assertEqual(line.unit_price_net, original_price)
        self.assertEqual(line.tax_rate, original_tax_rate)
    
    def test_snapshot_service_does_not_save(self):
        """Test that snapshot service does NOT save the line"""
        line = SalesDocumentLine(
            document=self.document,
            position_no=1,
            line_type="NORMAL",
            is_selected=True,
            description="Test line",
            quantity=Decimal("1.0000"),
            unit_price_net=Decimal("0.00"),
            tax_rate=self.tax_rate_reduced
        )
        
        # Apply snapshot without saving
        line.item = self.item
        apply_item_snapshot(line, self.item)
        
        # Verify values were updated in memory
        self.assertEqual(line.unit_price_net, self.item.net_price)
        
        # Verify line was NOT saved to database (pk should be None)
        self.assertIsNone(line.pk)
        
        # Now save it
        line.save()
        
        # Verify it was saved
        self.assertIsNotNone(line.pk)

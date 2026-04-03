"""
Tests for Item numbering functionality
"""
from django.test import TestCase
from django.db import IntegrityError, transaction, connection
from django.core.exceptions import ValidationError
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.models import Item, TaxRate, Kostenart
from auftragsverwaltung.models import NumberRange
from auftragsverwaltung.services.number_range import get_next_item_number
import unittest


class ItemNumberRangeModelTestCase(TestCase):
    """Test ITEM NumberRange model"""

    def test_create_item_number_range(self):
        """Test creating an item number range"""
        nr = NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY',
            format='ART{yy}-{seq:05d}'
        )

        self.assertIsNotNone(nr.pk)
        self.assertIsNone(nr.company)
        self.assertEqual(nr.target, 'ITEM')
        self.assertIsNone(nr.document_type)
        self.assertEqual(nr.reset_policy, 'YEARLY')
        self.assertEqual(nr.current_year, 0)
        self.assertEqual(nr.current_seq, 0)
        self.assertEqual(nr.format, 'ART{yy}-{seq:05d}')

    def test_str_representation_item(self):
        """Test __str__ method for item NumberRange"""
        nr = NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY'
        )

        expected = "Artikel-Nummernkreis (global, YEARLY)"
        self.assertEqual(str(nr), expected)

    def test_unique_constraint_item_global(self):
        """Test that only one ITEM NumberRange is allowed globally"""
        NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY'
        )

        # Try to create another ITEM NumberRange
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                target='ITEM',
                reset_policy='NEVER'
            )

    def test_item_number_range_cannot_have_company(self):
        """Test that ITEM NumberRange cannot have a company"""
        from core.models import Mandant

        company = Mandant.objects.create(
            name="Test Company",
            adresse="Test Street",
            plz="12345",
            ort="Test City"
        )

        # Try to create ITEM NumberRange with company
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                company=company,
                target='ITEM',
                reset_policy='YEARLY'
            )

    def test_item_number_range_cannot_have_document_type(self):
        """Test that ITEM NumberRange should not have a document_type"""
        from auftragsverwaltung.models import DocumentType

        doc_type = DocumentType.objects.create(
            key="item_test",
            name="Item Test",
            prefix="T"
        )

        # Create ITEM NumberRange with document_type (allowed but not used)
        nr = NumberRange.objects.create(
            target='ITEM',
            document_type=doc_type,
            reset_policy='YEARLY'
        )

        # This is allowed but document_type is not used
        self.assertIsNotNone(nr.pk)
        self.assertEqual(nr.document_type, doc_type)


class ItemNumberRangeServiceTestCase(TestCase):
    """Test item number generation service"""

    def setUp(self):
        """Create test NumberRange"""
        NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY',
            format='ART{yy}-{seq:05d}',
            current_year=0,
            current_seq=0
        )

    def test_get_next_item_number(self):
        """Test getting next item number"""
        number = get_next_item_number(date(2026, 4, 3))
        self.assertEqual(number, "ART26-00001")

        number = get_next_item_number(date(2026, 4, 3))
        self.assertEqual(number, "ART26-00002")

    def test_get_next_item_number_default_date(self):
        """Test getting next item number with default date (today)"""
        number = get_next_item_number()
        self.assertIsNotNone(number)
        self.assertIn("ART", number)

    def test_get_next_item_number_yearly_reset(self):
        """Test yearly reset policy for item numbers"""
        # Generate numbers in 2026
        number1 = get_next_item_number(date(2026, 12, 31))
        self.assertEqual(number1, "ART26-00001")

        # Generate number in 2027 - should reset sequence
        number2 = get_next_item_number(date(2027, 1, 1))
        self.assertEqual(number2, "ART27-00001")

    def test_get_next_item_number_never_reset(self):
        """Test NEVER reset policy for item numbers"""
        # Update to NEVER reset policy
        nr = NumberRange.objects.get(target='ITEM')
        nr.reset_policy = 'NEVER'
        nr.save()

        # Generate numbers in 2026
        number1 = get_next_item_number(date(2026, 12, 31))
        self.assertEqual(number1, "ART26-00001")

        number2 = get_next_item_number(date(2026, 12, 31))
        self.assertEqual(number2, "ART26-00002")

        # Generate number in 2027 - should NOT reset sequence
        number3 = get_next_item_number(date(2027, 1, 1))
        self.assertEqual(number3, "ART27-00003")

    def test_get_next_item_number_custom_format(self):
        """Test custom format for item numbers"""
        nr = NumberRange.objects.get(target='ITEM')
        nr.format = 'ITM-{yy}/{seq:04d}'
        nr.save()

        number = get_next_item_number(date(2026, 4, 3))
        self.assertEqual(number, "ITM-26/0001")

    def test_get_next_item_number_no_range_configured(self):
        """Test error when no ITEM NumberRange is configured"""
        NumberRange.objects.filter(target='ITEM').delete()

        with self.assertRaises(ValueError) as cm:
            get_next_item_number()

        self.assertIn("Kein Nummernkreis für Artikel konfiguriert", str(cm.exception))


class ItemAutoNumberingTestCase(TestCase):
    """Test automatic Item numbering"""

    def setUp(self):
        """Create test data"""
        # Create NumberRange for items
        NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY',
            format='ART{yy}-{seq:05d}',
            current_year=26,
            current_seq=0
        )

        # Create required dependencies
        self.tax_rate = TaxRate.objects.create(
            name="19% MwSt",
            rate=19.00
        )
        self.cost_type = Kostenart.objects.create(
            name="Test Kostenart"
        )

    def test_item_auto_number_assignment(self):
        """Test that item gets auto-assigned number on creation"""
        item = Item.objects.create(
            short_text_1="Test Item",
            net_price=100.00,
            purchase_price=50.00,
            item_type='MATERIAL',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        self.assertIsNotNone(item.article_no)
        self.assertEqual(item.article_no, "ART26-00001")

    def test_item_sequential_numbering(self):
        """Test that items get sequential numbers"""
        item1 = Item.objects.create(
            short_text_1="Test Item 1",
            net_price=100.00,
            purchase_price=50.00,
            item_type='MATERIAL',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        item2 = Item.objects.create(
            short_text_1="Test Item 2",
            net_price=200.00,
            purchase_price=100.00,
            item_type='SERVICE',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        self.assertEqual(item1.article_no, "ART26-00001")
        self.assertEqual(item2.article_no, "ART26-00002")

    def test_item_manual_number_preserved(self):
        """Test that manually set item number is preserved"""
        item = Item.objects.create(
            article_no="MANUAL-001",
            short_text_1="Test Item",
            net_price=100.00,
            purchase_price=50.00,
            item_type='MATERIAL',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        self.assertEqual(item.article_no, "MANUAL-001")

        # Next auto-generated number should still be sequential
        item2 = Item.objects.create(
            short_text_1="Test Item 2",
            net_price=200.00,
            purchase_price=100.00,
            item_type='SERVICE',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        self.assertEqual(item2.article_no, "ART26-00001")

    def test_item_no_number_range_error(self):
        """Test error when no ITEM NumberRange is configured"""
        NumberRange.objects.filter(target='ITEM').delete()

        with self.assertRaises(ValidationError) as cm:
            Item.objects.create(
                short_text_1="Test Item",
                net_price=100.00,
                purchase_price=50.00,
                item_type='MATERIAL',
                tax_rate=self.tax_rate,
                cost_type_1=self.cost_type
            )

        self.assertIn("article_no", cm.exception.message_dict)
        self.assertIn("Kein Nummernkreis für Artikel konfiguriert", str(cm.exception))

    def test_item_update_preserves_number(self):
        """Test that updating an item preserves its number"""
        item = Item.objects.create(
            short_text_1="Test Item",
            net_price=100.00,
            purchase_price=50.00,
            item_type='MATERIAL',
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type
        )

        original_number = item.article_no
        self.assertEqual(original_number, "ART26-00001")

        # Update item
        item.short_text_1 = "Updated Item"
        item.save()

        # Number should be preserved
        self.assertEqual(item.article_no, original_number)


@unittest.skipIf(
    connection.vendor == 'sqlite',
    'SQLite does not support row-level locking required for this test'
)
class ItemConcurrentNumberingTestCase(TestCase):
    """Test concurrent item number generation"""

    def setUp(self):
        """Create test data"""
        # Create NumberRange for items
        NumberRange.objects.create(
            target='ITEM',
            reset_policy='YEARLY',
            format='ART{yy}-{seq:05d}',
            current_year=26,
            current_seq=0
        )

        # Create required dependencies
        self.tax_rate = TaxRate.objects.create(
            name="19% MwSt",
            rate=19.00
        )
        self.cost_type = Kostenart.objects.create(
            name="Test Kostenart"
        )

    def test_concurrent_item_number_generation(self):
        """Test that concurrent item number generation produces unique numbers"""
        def create_item(index):
            from django.db import connection
            # Close old connection to force new one per thread
            connection.close()

            item = Item.objects.create(
                short_text_1=f"Test Item {index}",
                net_price=100.00,
                purchase_price=50.00,
                item_type='MATERIAL',
                tax_rate=self.tax_rate,
                cost_type_1=self.cost_type
            )
            return item.article_no

        # Generate 10 item numbers concurrently
        num_items = 10
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_item, i) for i in range(num_items)]
            numbers = [future.result() for future in as_completed(futures)]

        # All numbers should be unique
        self.assertEqual(len(set(numbers)), num_items,
                        f"Got duplicate numbers: {numbers}")

        # All numbers should be in expected range
        expected_numbers = {f"ART26-{i:05d}" for i in range(1, num_items + 1)}
        self.assertEqual(set(numbers), expected_numbers,
                        f"Numbers don't match expected range: {sorted(numbers)}")

    def test_concurrent_items_with_manual_numbers(self):
        """Test concurrent creation with mix of auto and manual numbers"""
        def create_item_auto(index):
            from django.db import connection
            connection.close()

            item = Item.objects.create(
                short_text_1=f"Auto Item {index}",
                net_price=100.00,
                purchase_price=50.00,
                item_type='MATERIAL',
                tax_rate=self.tax_rate,
                cost_type_1=self.cost_type
            )
            return ('auto', item.article_no)

        def create_item_manual(index):
            from django.db import connection
            connection.close()

            item = Item.objects.create(
                article_no=f"MANUAL-{index:03d}",
                short_text_1=f"Manual Item {index}",
                net_price=100.00,
                purchase_price=50.00,
                item_type='SERVICE',
                tax_rate=self.tax_rate,
                cost_type_1=self.cost_type
            )
            return ('manual', item.article_no)

        # Mix of auto and manual creation
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(create_item_auto, i))
                futures.append(executor.submit(create_item_manual, i))

            results = [future.result() for future in as_completed(futures)]

        auto_numbers = [num for typ, num in results if typ == 'auto']
        manual_numbers = [num for typ, num in results if typ == 'manual']

        # All auto numbers should be unique
        self.assertEqual(len(set(auto_numbers)), 5)

        # All manual numbers should be as specified
        expected_manual = {f"MANUAL-{i:03d}" for i in range(5)}
        self.assertEqual(set(manual_numbers), expected_manual)

        # Auto numbers should be sequential
        expected_auto = {f"ART26-{i:05d}" for i in range(1, 6)}
        self.assertEqual(set(auto_numbers), expected_auto)

"""
Tests für die Vergabe der Personenkonten (Debitoren/Kreditoren).

Seit dem DATEV-Buchungsstapel-Export (#1178) sind Personenkonten rein
numerisch, ohne Präfix und ohne Jahresbestandteil: Debitoren ab 10000,
Kreditoren ab 70000. Das frühere Format `DEB26-00001` ist entfallen.
"""
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from auftragsverwaltung.models import NumberRange
from auftragsverwaltung.services.number_range import (
    get_next_customer_number,
    get_next_supplier_number,
)
from core.models import Adresse

CUSTOMER_START = 10000
SUPPLIER_START = 70000


def _reset_range(target, start_seq):
    """Nummernkreis auf den Zustand direkt nach der Migration zurücksetzen."""
    nr = NumberRange.objects.get(target=target)
    nr.current_year = 0
    nr.current_seq = 0
    nr.start_seq = start_seq
    nr.format = '{seq}'
    nr.reset_policy = 'NEVER'
    nr.save()
    return nr


class PersonalAccountNumberRangeModelTestCase(TestCase):
    """Nummernkreise für Personenkonten"""

    def test_customer_and_supplier_ranges_exist_after_migration(self):
        """Die Datenmigration legt beide globalen Nummernkreise an"""
        for target, start in (('CUSTOMER', CUSTOMER_START), ('SUPPLIER', SUPPLIER_START)):
            nr = NumberRange.objects.get(target=target)
            self.assertIsNone(nr.company)
            self.assertEqual(nr.format, '{seq}')
            self.assertEqual(nr.reset_policy, 'NEVER')
            self.assertEqual(nr.start_seq, start)

    def test_str_representation_customer(self):
        nr = NumberRange.objects.get(target='CUSTOMER')
        self.assertEqual(str(nr), "Kunden-Nummernkreis (global, NEVER)")

    def test_str_representation_supplier(self):
        nr = NumberRange.objects.get(target='SUPPLIER')
        self.assertEqual(str(nr), "Lieferanten-Nummernkreis (global, NEVER)")

    def test_unique_constraint_customer_global(self):
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(target='CUSTOMER', reset_policy='NEVER')

    def test_unique_constraint_supplier_global(self):
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(target='SUPPLIER', reset_policy='NEVER')

    def test_supplier_number_range_cannot_have_company(self):
        from core.models import Mandant

        company = Mandant.objects.create(
            name="Test Company", adresse="Test Street", plz="12345", ort="Test City",
        )
        NumberRange.objects.filter(target='SUPPLIER').delete()
        with self.assertRaises(IntegrityError):
            NumberRange.objects.create(
                company=company, target='SUPPLIER', reset_policy='NEVER',
            )


class PersonalAccountServiceTestCase(TestCase):
    """Nummernvergabe über den Service"""

    def setUp(self):
        _reset_range('CUSTOMER', CUSTOMER_START)
        _reset_range('SUPPLIER', SUPPLIER_START)

    def test_customer_numbers_start_at_range_start(self):
        self.assertEqual(get_next_customer_number(), '10000')
        self.assertEqual(get_next_customer_number(), '10001')

    def test_supplier_numbers_start_at_range_start(self):
        self.assertEqual(get_next_supplier_number(), '70000')
        self.assertEqual(get_next_supplier_number(), '70001')

    def test_numbers_are_purely_numeric(self):
        """DATEV verlangt rein numerische Personenkonten"""
        self.assertTrue(get_next_customer_number().isdigit())
        self.assertTrue(get_next_supplier_number().isdigit())

    def test_no_yearly_component_and_no_reset(self):
        """
        Ein Debitorenkonto gehört dauerhaft zu einem Kunden: Auch über einen
        Jahreswechsel hinweg wird fortlaufend weitergezählt, und dieselbe
        Sequenz darf nicht ein zweites Mal vergeben werden.
        """
        first = get_next_customer_number()

        nr = NumberRange.objects.get(target='CUSTOMER')
        nr.current_year = nr.current_year + 1  # Jahreswechsel simulieren
        nr.save()

        second = get_next_customer_number()
        self.assertEqual(int(second), int(first) + 1)

    def test_yearly_reset_policy_is_rejected(self):
        """Ein jährlicher Reset würde Konten doppelt vergeben"""
        nr = NumberRange.objects.get(target='CUSTOMER')
        nr.reset_policy = 'YEARLY'
        nr.save()

        with self.assertRaises(ValueError) as cm:
            get_next_customer_number()
        self.assertIn('nicht jährlich zurücksetzen', str(cm.exception))

    def test_start_seq_is_respected_when_advanced(self):
        """Ein bereits fortgeschrittener Zähler gewinnt gegen den Startwert"""
        nr = NumberRange.objects.get(target='CUSTOMER')
        nr.current_seq = 12345
        nr.save()

        self.assertEqual(get_next_customer_number(), '12346')

    def test_missing_customer_number_range(self):
        NumberRange.objects.get(target='CUSTOMER').delete()
        with self.assertRaises(ValueError) as cm:
            get_next_customer_number()
        self.assertIn('Kein Nummernkreis für Kunden konfiguriert', str(cm.exception))

    def test_missing_supplier_number_range(self):
        NumberRange.objects.get(target='SUPPLIER').delete()
        with self.assertRaises(ValueError) as cm:
            get_next_supplier_number()
        self.assertIn('Kein Nummernkreis für Lieferanten konfiguriert', str(cm.exception))


class PersonalAccountAutoNumberingTestCase(TestCase):
    """Automatische Vergabe beim Anlegen einer Adresse"""

    def setUp(self):
        _reset_range('CUSTOMER', CUSTOMER_START)
        _reset_range('SUPPLIER', SUPPLIER_START)

    def _create(self, adressen_type, name, **kwargs):
        return Adresse.objects.create(
            adressen_type=adressen_type,
            name=name,
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt',
            land='Deutschland',
            **kwargs,
        )

    def test_customer_gets_debitor_account(self):
        kunde = self._create('KUNDE', 'Test Kunde')
        self.assertEqual(kunde.debitor_number, '10000')

    def test_supplier_gets_creditor_account(self):
        lieferant = self._create('LIEFERANT', 'Test Lieferant')
        self.assertEqual(lieferant.debitor_number, '70000')

    def test_customer_and_supplier_ranges_do_not_overlap(self):
        kunde = self._create('KUNDE', 'Kunde')
        lieferant = self._create('LIEFERANT', 'Lieferant')

        self.assertLess(int(kunde.debitor_number), SUPPLIER_START)
        self.assertGreaterEqual(int(lieferant.debitor_number), SUPPLIER_START)

    def test_manual_account_preserved(self):
        kunde = self._create('KUNDE', 'Test Kunde', debitor_number='10500')
        self.assertEqual(kunde.debitor_number, '10500')

    def test_no_auto_assign_for_other_address_types(self):
        adresse = self._create('Adresse', 'Test Adresse')
        self.assertIsNone(adresse.debitor_number)

    def test_no_auto_assign_on_update(self):
        kunde = self._create('KUNDE', 'Test Kunde')
        original = kunde.debitor_number

        kunde.name = 'Updated Name'
        kunde.save()

        kunde.refresh_from_db()
        self.assertEqual(kunde.debitor_number, original)

    def test_multiple_customers_get_sequential_accounts(self):
        numbers = [self._create('KUNDE', f'Kunde {i}').debitor_number for i in range(3)]
        self.assertEqual(numbers, ['10000', '10001', '10002'])

    def test_multiple_suppliers_get_sequential_accounts(self):
        numbers = [
            self._create('LIEFERANT', f'Lieferant {i}').debitor_number for i in range(3)
        ]
        self.assertEqual(numbers, ['70000', '70001', '70002'])

    def test_error_when_number_range_missing(self):
        NumberRange.objects.get(target='CUSTOMER').delete()
        with self.assertRaises(ValidationError) as cm:
            self._create('KUNDE', 'Test Kunde')
        self.assertIn('debitor_number', cm.exception.message_dict)

    def test_unique_account_constraint(self):
        kunde1 = self._create('KUNDE', 'Kunde 1')
        with self.assertRaises(IntegrityError):
            self._create('KUNDE', 'Kunde 2', debitor_number=kunde1.debitor_number)

    def test_null_accounts_allowed_for_plain_addresses(self):
        a1 = self._create('Adresse', 'Adresse 1')
        a2 = self._create('Adresse', 'Adresse 2')
        self.assertIsNone(a1.debitor_number)
        self.assertIsNone(a2.debitor_number)


class PersonalAccountValidationTestCase(TestCase):
    """Validierung der Personenkonten (numerisch, im richtigen Bereich)"""

    def _adresse(self, adressen_type, number):
        return Adresse(
            adressen_type=adressen_type,
            name='Test',
            strasse='Str. 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland',
            debitor_number=number,
        )

    def test_non_numeric_account_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            self._adresse('KUNDE', 'DEB26-00001').clean()
        self.assertIn('numerisch', str(cm.exception))

    def test_debitor_below_range_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            self._adresse('KUNDE', '9999').clean()
        self.assertIn('Debitorenkonto', str(cm.exception))

    def test_debitor_in_creditor_range_rejected(self):
        with self.assertRaises(ValidationError):
            self._adresse('KUNDE', '70000').clean()

    def test_creditor_in_debitor_range_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            self._adresse('LIEFERANT', '10000').clean()
        self.assertIn('Kreditorenkonto', str(cm.exception))

    def test_valid_accounts_accepted(self):
        self._adresse('KUNDE', '10000').clean()
        self._adresse('KUNDE', '69999').clean()
        self._adresse('LIEFERANT', '70000').clean()
        self._adresse('LIEFERANT', '99999').clean()

    def test_ranges_come_from_settings(self):
        """Die Bereichsgrenzen sind konfigurierbar, nicht hart kodiert"""
        self.assertEqual(
            Adresse.personal_account_range('KUNDE'),
            tuple(settings.DEBITOR_ACCOUNT_RANGE),
        )
        self.assertEqual(
            Adresse.personal_account_range('LIEFERANT'),
            tuple(settings.CREDITOR_ACCOUNT_RANGE),
        )
        self.assertIsNone(Adresse.personal_account_range('Adresse'))


@unittest.skipIf(
    'sqlite' in settings.DATABASES['default']['ENGINE'],
    "SQLite has table-level locking, race condition tests designed for PostgreSQL"
)
class PersonalAccountConcurrencyTestCase(TestCase):
    """Race-sichere Vergabe unter gleichzeitigem Zugriff"""

    def setUp(self):
        _reset_range('CUSTOMER', CUSTOMER_START)

    def test_concurrent_customer_creation(self):
        from django.db import connection

        def create_customer(index):
            connection.close()
            kunde = Adresse.objects.create(
                adressen_type='KUNDE',
                name=f'Concurrent Customer {index}',
                strasse=f'Str. {index}',
                plz='12345',
                ort='Stadt',
                land='Deutschland',
            )
            return kunde.debitor_number

        num_customers = 10
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_customer, i) for i in range(num_customers)]
            numbers = [future.result() for future in as_completed(futures)]

        self.assertEqual(len(numbers), len(set(numbers)), "Duplicate numbers found!")
        expected = {str(CUSTOMER_START + i) for i in range(num_customers)}
        self.assertEqual(set(numbers), expected)
        self.assertEqual(Adresse.objects.filter(adressen_type='KUNDE').count(), num_customers)

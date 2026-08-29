"""
Tests für die Datenmigration der Personenkonten (core.0037_datev_personenkonten).

Die Migrationsfunktion wird direkt gegen die echten Modelle aufgerufen (die
Feldnamen sind mit dem historischen Modellstand identisch). So lässt sich das
Verhalten für den Bestand prüfen, ohne einen Migrations-Executor zu bemühen.
"""
from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from auftragsverwaltung.models import NumberRange
from core.models import Adresse


def _run_migration():
    """
    Die Migrationsfunktion ausführen.

    Migrationsmodule beginnen mit einer Ziffer und sind deshalb nicht per
    normalem Import erreichbar – daher der Umweg über den Migrations-Loader.
    """
    loader = MigrationLoader(connection)
    migration = loader.disk_migrations[('core', '0037_datev_personenkonten')]
    migration.operations[0].code(apps, connection.schema_editor())


class PersonenkontenMigrationTestCase(TestCase):
    """Bestandsumstellung auf numerische Personenkonten"""

    def _create(self, adressen_type, name, debitor_number=None):
        """
        Adresse ohne automatische Nummernvergabe anlegen.

        `Adresse.objects.create()` würde bereits ein numerisches Konto
        vergeben; für die Migrationstests wird der Altbestand gebraucht.
        """
        adresse = Adresse(
            adressen_type=adressen_type,
            name=name,
            strasse='Str. 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland',
        )
        # save() vergibt nur, wenn noch keine Nummer gesetzt ist – daher hier
        # zuerst einen Altwert setzen bzw. den Typ vorübergehend neutralisieren.
        if debitor_number is None:
            adresse.adressen_type = 'Adresse'
            adresse.save()
            Adresse.objects.filter(pk=adresse.pk).update(
                adressen_type=adressen_type, debitor_number=None,
            )
        else:
            adresse.debitor_number = debitor_number
            adresse.save()
        adresse.refresh_from_db()
        return adresse

    def test_legacy_numbers_are_replaced(self):
        kunde1 = self._create('KUNDE', 'Kunde A', 'DEB26-00001')
        kunde2 = self._create('KUNDE', 'Kunde B', 'DEB26-00002')

        _run_migration()

        kunde1.refresh_from_db()
        kunde2.refresh_from_db()
        self.assertTrue(kunde1.debitor_number.isdigit())
        self.assertTrue(kunde2.debitor_number.isdigit())
        self.assertEqual(int(kunde1.debitor_number), 10000)
        self.assertEqual(int(kunde2.debitor_number), 10001)

    def test_suppliers_get_creditor_range(self):
        lieferant = self._create('LIEFERANT', 'Lieferant A')

        _run_migration()

        lieferant.refresh_from_db()
        self.assertEqual(int(lieferant.debitor_number), 70000)

    def test_existing_numeric_accounts_are_kept(self):
        kunde = self._create('KUNDE', 'Kunde', '10500')

        _run_migration()

        kunde.refresh_from_db()
        self.assertEqual(kunde.debitor_number, '10500')

    def test_no_collision_with_kept_accounts(self):
        kept = self._create('KUNDE', 'Bestandskunde', '10000')
        legacy = self._create('KUNDE', 'Altkunde', 'DEB26-00001')

        _run_migration()

        kept.refresh_from_db()
        legacy.refresh_from_db()
        self.assertEqual(kept.debitor_number, '10000')
        self.assertNotEqual(legacy.debitor_number, '10000')
        self.assertTrue(legacy.debitor_number.isdigit())

    def test_migration_is_idempotent(self):
        kunde = self._create('KUNDE', 'Kunde', 'DEB26-00001')
        lieferant = self._create('LIEFERANT', 'Lieferant', 'KRED-1')

        _run_migration()
        kunde.refresh_from_db()
        lieferant.refresh_from_db()
        first_kunde, first_lieferant = kunde.debitor_number, lieferant.debitor_number

        _run_migration()
        kunde.refresh_from_db()
        lieferant.refresh_from_db()
        self.assertEqual(kunde.debitor_number, first_kunde)
        self.assertEqual(lieferant.debitor_number, first_lieferant)

    def test_accounts_stay_unique(self):
        for i in range(5):
            self._create('KUNDE', f'Kunde {i}', f'DEB26-{i:05d}')
        for i in range(3):
            self._create('LIEFERANT', f'Lieferant {i}')

        _run_migration()

        numbers = list(
            Adresse.objects.exclude(debitor_number=None)
            .values_list('debitor_number', flat=True)
        )
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_number_ranges_are_advanced_past_existing_accounts(self):
        """Neuanlagen nach der Migration dürfen nicht mit dem Bestand kollidieren"""
        self._create('KUNDE', 'Kunde', 'DEB26-00001')
        self._create('LIEFERANT', 'Lieferant', 'KRED-1')

        _run_migration()

        existing = set(
            Adresse.objects.exclude(debitor_number=None)
            .values_list('debitor_number', flat=True)
        )

        neuer_kunde = Adresse.objects.create(
            adressen_type='KUNDE', name='Neu', strasse='S', plz='1', ort='O',
            land='Deutschland',
        )
        neuer_lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT', name='Neu', strasse='S', plz='1', ort='O',
            land='Deutschland',
        )

        self.assertNotIn(neuer_kunde.debitor_number, existing)
        self.assertNotIn(neuer_lieferant.debitor_number, existing)
        self.assertGreaterEqual(int(neuer_kunde.debitor_number), 10000)
        self.assertGreaterEqual(int(neuer_lieferant.debitor_number), 70000)

    def test_number_ranges_are_configured_for_datev(self):
        _run_migration()

        for target, start in (('CUSTOMER', 10000), ('SUPPLIER', 70000)):
            nr = NumberRange.objects.get(target=target)
            self.assertEqual(nr.format, '{seq}')
            self.assertEqual(nr.reset_policy, 'NEVER')
            self.assertEqual(nr.start_seq, start)
            self.assertIsNone(nr.company)

    def test_other_address_types_are_untouched(self):
        adresse = self._create('Adresse', 'Neutrale Adresse')

        _run_migration()

        adresse.refresh_from_db()
        self.assertIsNone(adresse.debitor_number)

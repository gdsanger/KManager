"""
Tests für das zentrale Anzeige-Attribut `Adresse.matchkey` (#1171).

Der Matchkey ist eine DB-generierte, gespeicherte Spalte:

    matchkey = "<firma> (<name>)"   wenn firma gesetzt und nicht leer
    matchkey = "<name>"             sonst
"""

from django.db import connection
from django.test import TestCase

from core.models import Adresse


def make_adresse(**kwargs):
    defaults = {
        'adressen_type': 'KUNDE',
        'name': 'Max Mustermann',
        'strasse': 'Musterstraße 1',
        'plz': '12345',
        'ort': 'Musterstadt',
        'land': 'Deutschland',
    }
    defaults.update(kwargs)
    return Adresse.objects.create(**defaults)


class AdresseMatchkeyTestCase(TestCase):
    """Regelwerk des generierten Matchkeys."""

    def test_matchkey_with_firma(self):
        adresse = make_adresse(firma='Alpha AG', name='Max Mustermann')
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Alpha AG (Max Mustermann)')

    def test_matchkey_without_firma_is_name(self):
        adresse = make_adresse(firma=None, name='Erika Einzel')
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Erika Einzel')

    def test_empty_firma_is_treated_like_null(self):
        with_null = make_adresse(firma=None, name='Anton Allein')
        with_empty = make_adresse(firma='', name='Anton Allein')
        with_null.refresh_from_db()
        with_empty.refresh_from_db()
        self.assertEqual(with_null.matchkey, 'Anton Allein')
        self.assertEqual(with_empty.matchkey, 'Anton Allein')

    def test_matchkey_handles_umlauts_and_special_chars(self):
        adresse = make_adresse(firma='Öko & Söhne (GmbH)', name='Jürgen Groß-Weiß')
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Öko & Söhne (GmbH) (Jürgen Groß-Weiß)')

    def test_matchkey_follows_field_changes(self):
        adresse = make_adresse(firma=None, name='Max Mustermann')
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Max Mustermann')

        adresse.firma = 'Alpha AG'
        adresse.save()
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Alpha AG (Max Mustermann)')

        adresse.firma = ''
        adresse.name = 'Maxi Mustermann'
        adresse.save()
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Maxi Mustermann')

    def test_matchkey_is_filled_on_bulk_create(self):
        """bulk_create umgeht save() - die DB muss den Wert trotzdem setzen."""
        Adresse.objects.bulk_create([
            Adresse(adressen_type='KUNDE', name='Bulk Person', firma='Bulk GmbH',
                    strasse='S 1', plz='12345', ort='Stadt', land='Deutschland'),
            Adresse(adressen_type='KUNDE', name='Bulk Ohne Firma',
                    strasse='S 2', plz='12345', ort='Stadt', land='Deutschland'),
        ])
        self.assertEqual(
            Adresse.objects.get(name='Bulk Person').matchkey,
            'Bulk GmbH (Bulk Person)',
        )
        self.assertEqual(
            Adresse.objects.get(name='Bulk Ohne Firma').matchkey,
            'Bulk Ohne Firma',
        )

    def test_matchkey_is_updated_by_queryset_update(self):
        """QuerySet.update() umgeht save() - der Wert darf nicht veralten."""
        adresse = make_adresse(firma='Alt GmbH', name='Max Mustermann')
        Adresse.objects.filter(pk=adresse.pk).update(firma='Neu GmbH')
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Neu GmbH (Max Mustermann)')

        Adresse.objects.filter(pk=adresse.pk).update(firma=None)
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Max Mustermann')

    def test_matchkey_is_not_writable(self):
        """
        Ein manipulierter Wert darf den gespeicherten Matchkey nicht ändern.

        GeneratedField ist editable=False, wird also von ModelForms ignoriert;
        auch ein direkt gesetztes Attribut landet nicht in der Datenbank.
        """
        field = Adresse._meta.get_field('matchkey')
        self.assertFalse(field.editable)
        self.assertNotIn('matchkey', [f.name for f in Adresse._meta.fields if f.editable])

        adresse = make_adresse(firma='Alpha AG', name='Max Mustermann')
        adresse.matchkey = 'Gefälschter Wert'
        adresse.save()
        adresse.refresh_from_db()
        self.assertEqual(adresse.matchkey, 'Alpha AG (Max Mustermann)')

    def test_matchkey_column_is_persisted(self):
        """db_persist=True: der Wert liegt als echte Spalte in der Tabelle."""
        adresse = make_adresse(firma='Alpha AG', name='Max Mustermann')
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT matchkey FROM core_adresse WHERE id = %s', [adresse.pk]
            )
            self.assertEqual(cursor.fetchone()[0], 'Alpha AG (Max Mustermann)')

    def test_matchkey_is_sortable_and_searchable_in_db(self):
        alpha = make_adresse(firma='Alpha AG', name='Max Mustermann')
        beta = make_adresse(firma='Beta GmbH', name='Max Mustermann')
        solo = make_adresse(name='Anton Allein')

        self.assertEqual(
            list(Adresse.objects.order_by('matchkey').values_list('pk', flat=True)),
            [alpha.pk, solo.pk, beta.pk],
        )
        self.assertEqual(
            list(Adresse.objects.filter(matchkey__icontains='beta')),
            [beta],
        )
        # Suche über den reinen Personennamen findet weiterhin beide Firmen
        self.assertEqual(
            Adresse.objects.filter(matchkey__icontains='Max Mustermann').count(), 2
        )


class AdresseMatchkeyPythonParityTestCase(TestCase):
    """`build_matchkey()`/`full_name()` müssen exakt der DB-Spalte entsprechen."""

    CASES = [
        ('Alpha AG', 'Max Mustermann'),
        (None, 'Erika Einzel'),
        ('', 'Anton Allein'),
        ('Öko & Söhne', 'Jürgen Groß'),
        ('  ', 'Whitespace Firma'),
        ("O'Brien & Co", 'Sean O\'Brien'),
        ('Firma (mit Klammern)', 'Name (auch)'),
    ]

    def test_python_and_db_agree(self):
        for firma, name in self.CASES:
            with self.subTest(firma=firma, name=name):
                adresse = make_adresse(firma=firma, name=name)
                expected = Adresse.build_matchkey(firma, name)
                adresse.refresh_from_db()
                self.assertEqual(adresse.matchkey, expected)
                self.assertEqual(adresse.full_name(), expected)

    def test_full_name_works_on_unsaved_instance(self):
        adresse = Adresse(firma='Alpha AG', name='Max Mustermann')
        self.assertEqual(adresse.full_name(), 'Alpha AG (Max Mustermann)')

    def test_str_returns_matchkey(self):
        adresse = make_adresse(firma='Alpha AG', name='Max Mustermann')
        self.assertEqual(str(adresse), 'Alpha AG (Max Mustermann)')

    def test_full_address_returns_complete_address_line(self):
        adresse = make_adresse(firma='Alpha AG', name='Max Mustermann')
        self.assertEqual(
            adresse.full_address(),
            'Alpha AG (Max Mustermann), Musterstraße 1, 12345 Musterstadt, Deutschland',
        )

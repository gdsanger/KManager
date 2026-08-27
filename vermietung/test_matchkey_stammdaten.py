"""
UI-Tests für den Matchkey in den Stammdaten-Ansichten (#1171).

Abgedeckt: Adressen, Kunden und Lieferanten jeweils in Liste, Detail und
Bearbeiten-Formular sowie der Schutz gegen manipulierte POSTs.
"""

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Adresse


ADDRESS_DEFAULTS = {
    'strasse': 'Musterstraße 1',
    'plz': '12345',
    'ort': 'Musterstadt',
    'land': 'Deutschland',
}


class MatchkeyStammdatenViewsTestCase(TestCase):
    """Matchkey ist in Liste, Detail und Formular sichtbar und readonly."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        group, _ = Group.objects.get_or_create(name='Vermietung')
        self.user.groups.add(group)
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', anrede='HERR',
            name='Max Mustermann', **ADDRESS_DEFAULTS
        )
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT', firma='Beta GmbH',
            name='Bea Bauer', **ADDRESS_DEFAULTS
        )
        self.adresse = Adresse.objects.create(
            adressen_type='Adresse', firma='Gamma KG',
            name='Gerd Gärtner', **ADDRESS_DEFAULTS
        )

    def _get(self, url_name, obj=None):
        url = reverse(url_name, kwargs={'pk': obj.pk}) if obj else reverse(url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_lists_show_matchkey(self):
        cases = [
            ('vermietung:kunde_list', self.kunde),
            ('vermietung:lieferant_list', self.lieferant),
            ('vermietung:adresse_list', self.adresse),
        ]
        for url_name, obj in cases:
            with self.subTest(url_name=url_name):
                content = self._get(url_name)
                self.assertIn(obj.matchkey, content)

    def test_detail_views_show_matchkey(self):
        cases = [
            ('vermietung:kunde_detail', self.kunde),
            ('vermietung:lieferant_detail', self.lieferant),
            ('vermietung:adresse_detail', self.adresse),
        ]
        for url_name, obj in cases:
            with self.subTest(url_name=url_name):
                content = self._get(url_name, obj)
                self.assertIn('Matchkey', content)
                self.assertIn(obj.matchkey, content)

    def test_edit_forms_show_matchkey_readonly(self):
        cases = [
            ('vermietung:kunde_edit', self.kunde),
            ('vermietung:lieferant_edit', self.lieferant),
            ('vermietung:adresse_edit', self.adresse),
        ]
        for url_name, obj in cases:
            with self.subTest(url_name=url_name):
                content = self._get(url_name, obj)
                self.assertIn('id="matchkey_readonly"', content)
                self.assertIn(f'value="{obj.matchkey}"', content)
                # Kein absendbares Eingabefeld für den Matchkey
                self.assertNotIn('name="matchkey"', content)

    def test_create_forms_show_empty_matchkey_placeholder(self):
        for url_name in ('vermietung:kunde_create', 'vermietung:lieferant_create',
                         'vermietung:adresse_create'):
            with self.subTest(url_name=url_name):
                content = self._get(url_name)
                self.assertIn('id="matchkey_readonly"', content)
                self.assertIn('Wird beim Speichern automatisch erzeugt', content)
                self.assertNotIn('name="matchkey"', content)


class MatchkeyNotEditableViaPostTestCase(TestCase):
    """Ein manipulierter POST darf den gespeicherten Matchkey nicht ändern."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        group, _ = Group.objects.get_or_create(name='Vermietung')
        self.user.groups.add(group)
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )

    def _post_data(self, **overrides):
        data = {
            'firma': self.kunde.firma,
            'anrede': '',
            'name': self.kunde.name,
            'strasse': self.kunde.strasse,
            'plz': self.kunde.plz,
            'ort': self.kunde.ort,
            'land': self.kunde.land,
            'telefon': '',
            'mobil': '',
            'email': '',
            'invoice_email': '',
            'bemerkung': '',
            'country_code': 'DE',
            'vat_id': '',
            'debitor_number': self.kunde.debitor_number or '',
        }
        data.update(overrides)
        return data

    def test_posted_matchkey_is_ignored(self):
        response = self.client.post(
            reverse('vermietung:kunde_edit', kwargs={'pk': self.kunde.pk}),
            self._post_data(matchkey='Gefälschter Wert'),
        )
        self.assertIn(response.status_code, (302, 200))
        self.kunde.refresh_from_db()
        self.assertEqual(self.kunde.matchkey, 'Alpha AG (Max Mustermann)')

    def test_matchkey_follows_firma_change_after_edit(self):
        response = self.client.post(
            reverse('vermietung:kunde_edit', kwargs={'pk': self.kunde.pk}),
            self._post_data(firma='Alpha Holding AG'),
        )
        self.assertIn(response.status_code, (302, 200))
        self.kunde.refresh_from_db()
        self.assertEqual(self.kunde.matchkey, 'Alpha Holding AG (Max Mustermann)')

        # Und die Bearbeiten-Maske zeigt beim erneuten Öffnen den neuen Wert
        content = self.client.get(
            reverse('vermietung:kunde_edit', kwargs={'pk': self.kunde.pk})
        ).content.decode()
        self.assertIn('value="Alpha Holding AG (Max Mustermann)"', content)


class MatchkeyDisambiguationTestCase(TestCase):
    """Gleicher Personenname, verschiedene Firmen -> eindeutig unterscheidbar."""

    def test_same_name_different_firma(self):
        alpha = Adresse.objects.create(
            adressen_type='KUNDE', firma='Alpha AG', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )
        beta = Adresse.objects.create(
            adressen_type='KUNDE', firma='Beta GmbH', name='Max Mustermann',
            **ADDRESS_DEFAULTS
        )
        alpha.refresh_from_db()
        beta.refresh_from_db()
        self.assertNotEqual(alpha.matchkey, beta.matchkey)
        self.assertEqual(alpha.matchkey, 'Alpha AG (Max Mustermann)')
        self.assertEqual(beta.matchkey, 'Beta GmbH (Max Mustermann)')

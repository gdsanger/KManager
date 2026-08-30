"""
Tests für die Abrechnungskonditionen am Projekt (Artikel, Stundensatz, Rabatt).

Leistungs- und Anfahrtszeit werden getrennt abgerechnet, daher je ein eigener
Artikel und ein eigener Stundensatz. Alle Angaben sind optional; ein nur
teilweise gepflegtes Projekt ist bewusst erlaubt.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from core.forms import ProjektForm
from core.models import Adresse, Item, Kostenart, Projekt, TaxRate


class AbrechnungskonditionenTestBase(TestCase):
    """Gemeinsame Stammdaten für Artikel und Kunden."""

    def setUp(self):
        self.user = User.objects.create_user(username='billinguser', password='password')
        self.tax_rate = TaxRate.objects.create(
            code='VAT19', name='19% USt', rate=Decimal('0.19')
        )
        self.kostenart = Kostenart.objects.create(
            name='Dienstleistung', umsatzsteuer_satz='19'
        )
        self.leistung = self._item('ART-LEIST', 'Technikerstunde', Decimal('95.00'))
        self.anfahrt = self._item('ART-FAHRT', 'Anfahrtszeit', Decimal('45.00'))
        self.kunde = Adresse.objects.create(
            name='Muster GmbH', adressen_type='KUNDE'
        )

    def _item(self, article_no, short_text, net_price):
        return Item.objects.create(
            article_no=article_no,
            short_text_1=short_text,
            net_price=net_price,
            purchase_price=Decimal('0.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            item_type='SERVICE',
        )

    def _form_data(self, **overrides):
        data = {
            'titel': 'Abrechnungsprojekt',
            'kunde': '',
            'company': '',
            'beschreibung': '',
            'status': 'NEU',
            'billing_item': '',
            'hourly_rate': '',
            'travel_item': '',
            'travel_hourly_rate': '',
            'discount_percent': '0.00',
        }
        data.update(overrides)
        return data


class ProjektAbrechnungModelTestCase(AbrechnungskonditionenTestBase):
    """Modellebene: Speichern und Validierung der Konditionen."""

    def test_save_with_complete_conditions(self):
        """Vollständig gepflegte Konditionen lassen sich speichern."""
        projekt = Projekt(
            titel='Vollständig',
            kunde=self.kunde,
            billing_item=self.leistung,
            hourly_rate=Decimal('110.00'),
            travel_item=self.anfahrt,
            travel_hourly_rate=Decimal('55.00'),
            discount_percent=Decimal('10.00'),
            erstellt_von=self.user,
        )
        projekt.full_clean()
        projekt.save()

        projekt.refresh_from_db()
        self.assertEqual(projekt.billing_item, self.leistung)
        self.assertEqual(projekt.hourly_rate, Decimal('110.00'))
        self.assertEqual(projekt.travel_item, self.anfahrt)
        self.assertEqual(projekt.travel_hourly_rate, Decimal('55.00'))
        self.assertEqual(projekt.discount_percent, Decimal('10.00'))

    def test_save_with_item_but_without_rate(self):
        """Artikel ohne Stundensatz ist erlaubt (halb gepflegtes Projekt)."""
        projekt = Projekt(
            titel='Nur Artikel', billing_item=self.leistung, erstellt_von=self.user
        )
        projekt.full_clean()
        projekt.save()

        projekt.refresh_from_db()
        self.assertEqual(projekt.billing_item, self.leistung)
        self.assertIsNone(projekt.hourly_rate)

    def test_save_with_rate_but_without_item(self):
        """Stundensatz ohne Artikel ist ebenfalls erlaubt."""
        projekt = Projekt(
            titel='Nur Satz', hourly_rate=Decimal('90.00'), erstellt_von=self.user
        )
        projekt.full_clean()
        projekt.save()

        projekt.refresh_from_db()
        self.assertIsNone(projekt.billing_item)
        self.assertEqual(projekt.hourly_rate, Decimal('90.00'))

    def test_existing_projekt_without_conditions_saves(self):
        """Bestandsprojekte ohne Konditionen bleiben speicherbar."""
        projekt = Projekt.objects.create(titel='Intern', erstellt_von=self.user)
        projekt.full_clean()
        projekt.titel = 'Intern (umbenannt)'
        projekt.save()

        projekt.refresh_from_db()
        self.assertEqual(projekt.titel, 'Intern (umbenannt)')
        self.assertIsNone(projekt.billing_item)
        self.assertIsNone(projekt.travel_item)
        self.assertEqual(projekt.discount_percent, Decimal('0.00'))

    def test_negative_hourly_rate_rejected(self):
        """Ein negativer Stundensatz wird als Feldfehler abgewiesen."""
        projekt = Projekt(titel='Negativ', hourly_rate=Decimal('-1.00'))

        with self.assertRaises(ValidationError) as ctx:
            projekt.full_clean()

        self.assertIn('hourly_rate', ctx.exception.error_dict)

    def test_negative_travel_hourly_rate_rejected(self):
        """Auch der Anfahrts-Stundensatz darf nicht negativ sein."""
        projekt = Projekt(titel='Negativ Anfahrt', travel_hourly_rate=Decimal('-0.01'))

        with self.assertRaises(ValidationError) as ctx:
            projekt.full_clean()

        self.assertIn('travel_hourly_rate', ctx.exception.error_dict)

    def test_discount_above_100_rejected(self):
        """Rabatt über 100 % wird abgewiesen."""
        projekt = Projekt(titel='Zu viel Rabatt', discount_percent=Decimal('100.01'))

        with self.assertRaises(ValidationError) as ctx:
            projekt.full_clean()

        self.assertIn('discount_percent', ctx.exception.error_dict)

    def test_negative_discount_rejected(self):
        """Negativer Rabatt wird abgewiesen."""
        projekt = Projekt(titel='Negativer Rabatt', discount_percent=Decimal('-5.00'))

        with self.assertRaises(ValidationError) as ctx:
            projekt.full_clean()

        self.assertIn('discount_percent', ctx.exception.error_dict)

    def test_item_in_use_is_protected(self):
        """Ein als Abrechnungsartikel genutzter Artikel lässt sich nicht löschen."""
        Projekt.objects.create(titel='Mit Artikel', billing_item=self.leistung)

        with self.assertRaises(ProtectedError):
            self.leistung.delete()

    def test_travel_item_in_use_is_protected(self):
        """Gleiches gilt für den Anfahrtsartikel."""
        Projekt.objects.create(titel='Mit Anfahrt', travel_item=self.anfahrt)

        with self.assertRaises(ProtectedError):
            self.anfahrt.delete()


class ProjektAbrechnungFormTestCase(AbrechnungskonditionenTestBase):
    """Formularebene: Pflege der Konditionen über ProjektForm."""

    def test_form_exposes_billing_fields(self):
        """Alle fünf Abrechnungsfelder sind im Formular pflegbar."""
        form = ProjektForm()
        for field in (
            'billing_item', 'hourly_rate', 'travel_item',
            'travel_hourly_rate', 'discount_percent',
        ):
            self.assertIn(field, form.fields)

    def test_form_billing_fields_are_optional(self):
        """Ohne Konditionen bleibt das Formular gültig."""
        form = ProjektForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_saves_complete_conditions(self):
        """Vollständige Konditionen werden gespeichert."""
        form = ProjektForm(data=self._form_data(
            kunde=str(self.kunde.pk),
            billing_item=str(self.leistung.pk),
            hourly_rate='120.50',
            travel_item=str(self.anfahrt.pk),
            travel_hourly_rate='60.00',
            discount_percent='7.50',
        ))
        self.assertTrue(form.is_valid(), form.errors)

        projekt = form.save()
        self.assertEqual(projekt.billing_item, self.leistung)
        self.assertEqual(projekt.hourly_rate, Decimal('120.50'))
        self.assertEqual(projekt.travel_item, self.anfahrt)
        self.assertEqual(projekt.travel_hourly_rate, Decimal('60.00'))
        self.assertEqual(projekt.discount_percent, Decimal('7.50'))

    def test_form_saves_partial_conditions(self):
        """Artikel ohne Satz bzw. Satz ohne Artikel bleiben gültig."""
        nur_artikel = ProjektForm(data=self._form_data(
            billing_item=str(self.leistung.pk)
        ))
        self.assertTrue(nur_artikel.is_valid(), nur_artikel.errors)

        nur_satz = ProjektForm(data=self._form_data(travel_hourly_rate='40.00'))
        self.assertTrue(nur_satz.is_valid(), nur_satz.errors)

    def test_form_rejects_negative_hourly_rate(self):
        """Negativer Stundensatz erzeugt einen Feldfehler."""
        form = ProjektForm(data=self._form_data(hourly_rate='-10.00'))

        self.assertFalse(form.is_valid())
        self.assertIn('hourly_rate', form.errors)

    def test_form_rejects_negative_travel_hourly_rate(self):
        """Negativer Anfahrts-Stundensatz erzeugt einen Feldfehler."""
        form = ProjektForm(data=self._form_data(travel_hourly_rate='-0.01'))

        self.assertFalse(form.is_valid())
        self.assertIn('travel_hourly_rate', form.errors)

    def test_form_rejects_discount_out_of_range(self):
        """Rabatt außerhalb 0–100 erzeugt einen Feldfehler."""
        zu_hoch = ProjektForm(data=self._form_data(discount_percent='101.00'))
        self.assertFalse(zu_hoch.is_valid())
        self.assertIn('discount_percent', zu_hoch.errors)

        negativ = ProjektForm(data=self._form_data(discount_percent='-1.00'))
        self.assertFalse(negativ.is_valid())
        self.assertIn('discount_percent', negativ.errors)


class ProjektAbrechnungAdminTestCase(TestCase):
    """Die Konditionen sind auch im Django-Admin pflegbar."""

    def test_admin_form_contains_billing_fields(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        admin_instance = site._registry[Projekt]
        request = RequestFactory().get('/admin/core/projekt/')
        request.user = User.objects.create_superuser(
            username='adminuser', email='admin@example.com', password='password'
        )
        fields = admin_instance.get_form(request)().fields

        for field in (
            'billing_item', 'hourly_rate', 'travel_item',
            'travel_hourly_rate', 'discount_percent',
        ):
            self.assertIn(field, fields)

    def test_admin_list_display_contains_item_and_rate(self):
        from django.contrib.admin.sites import site

        admin_instance = site._registry[Projekt]

        self.assertIn('billing_item', admin_instance.list_display)
        self.assertIn('hourly_rate', admin_instance.list_display)


class ProjektAbrechnungViewTestCase(AbrechnungskonditionenTestBase):
    """Anzeige der Konditionen auf der Projekt-Detailseite."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(username='billinguser', password='password')

    def test_detail_shows_conditions(self):
        """Artikel, Stundensätze und Rabatt erscheinen auf der Detailseite."""
        projekt = Projekt.objects.create(
            titel='Anzeige',
            kunde=self.kunde,
            billing_item=self.leistung,
            hourly_rate=Decimal('99.00'),
            travel_item=self.anfahrt,
            travel_hourly_rate=Decimal('49.00'),
            discount_percent=Decimal('5.00'),
        )

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': projekt.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Abrechnungskonditionen')
        self.assertContains(response, 'ART-LEIST')
        self.assertContains(response, 'Technikerstunde')
        self.assertContains(response, 'ART-FAHRT')
        self.assertContains(response, 'Anfahrtszeit')
        # floatformat lokalisiert nach de-de (Komma als Dezimaltrenner)
        self.assertContains(response, '99,00')
        self.assertContains(response, '49,00')
        self.assertContains(response, '5,00')

    def test_detail_marks_missing_values_as_gap(self):
        """Nicht gepflegte Werte werden als Lücke dargestellt."""
        projekt = Projekt.objects.create(titel='Ohne Konditionen')

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': projekt.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Abrechnungskonditionen')
        self.assertContains(response, '–')

    def test_detail_warns_when_customer_project_is_incomplete(self):
        """Kunde vorhanden, Leistungskonditionen unvollständig → Hinweis."""
        projekt = Projekt.objects.create(
            titel='Unvollständig', kunde=self.kunde, billing_item=self.leistung
        )

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': projekt.pk}))

        self.assertContains(response, 'noch nicht abrechenbar')

    def test_detail_without_warning_when_complete(self):
        """Vollständige Leistungskonditionen erzeugen keinen Hinweis."""
        projekt = Projekt.objects.create(
            titel='Vollständig',
            kunde=self.kunde,
            billing_item=self.leistung,
            hourly_rate=Decimal('95.00'),
        )

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': projekt.pk}))

        self.assertNotContains(response, 'noch nicht abrechenbar')

    def test_detail_without_warning_for_internal_project(self):
        """Interne Projekte ohne Kunde erzeugen keinen Hinweis."""
        projekt = Projekt.objects.create(titel='Intern')

        response = self.client.get(reverse('projekt_detail', kwargs={'pk': projekt.pk}))

        self.assertNotContains(response, 'noch nicht abrechenbar')

    def test_edit_view_persists_conditions(self):
        """Konditionen lassen sich über die Bearbeiten-Ansicht pflegen."""
        projekt = Projekt.objects.create(titel='Zu pflegen', kunde=self.kunde)

        response = self.client.post(
            reverse('projekt_edit', kwargs={'pk': projekt.pk}),
            self._form_data(
                titel='Zu pflegen',
                kunde=str(self.kunde.pk),
                billing_item=str(self.leistung.pk),
                hourly_rate='105.00',
                discount_percent='2.50',
            ),
        )

        self.assertEqual(response.status_code, 302)
        projekt.refresh_from_db()
        self.assertEqual(projekt.billing_item, self.leistung)
        self.assertEqual(projekt.hourly_rate, Decimal('105.00'))
        self.assertEqual(projekt.discount_percent, Decimal('2.50'))

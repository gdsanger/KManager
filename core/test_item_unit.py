"""
Tests für das Feld "Mengeneinheit" im Artikelstamm (Issue #1177).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from core.admin import ItemAdmin
from core.forms import ItemForm
from core.models import Item, Kostenart, TaxRate, Unit
from core.tables import ItemTable

User = get_user_model()


class ItemUnitModelTests(TestCase):
    """Das Feld ist optional und schützt die Stammdaten."""

    def setUp(self):
        self.tax_rate = TaxRate.objects.create(
            code='UST19', name='Umsatzsteuer 19%', rate=Decimal('0.19'), is_active=True
        )
        self.kostenart = Kostenart.objects.create(name='Erlöse')
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')

    def _create_item(self, article_no='ART-001', **kwargs):
        defaults = dict(
            article_no=article_no,
            short_text_1='Testartikel',
            net_price=Decimal('10.00'),
            purchase_price=Decimal('5.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            item_type='MATERIAL',
        )
        defaults.update(kwargs)
        return Item.objects.create(**defaults)

    def test_artikel_ohne_einheit_bleibt_gueltig(self):
        """Bestandsartikel ohne Einheit müssen weiterhin anlegbar sein."""
        item = self._create_item()
        self.assertIsNone(item.unit)
        item.full_clean()

    def test_artikel_mit_einheit(self):
        item = self._create_item(article_no='ART-002', unit=self.unit)
        item.refresh_from_db()
        self.assertEqual(item.unit, self.unit)
        self.assertIn(item, self.unit.items.all())

    def test_einheit_in_verwendung_ist_geschuetzt(self):
        self._create_item(article_no='ART-003', unit=self.unit)
        with self.assertRaises(ProtectedError):
            self.unit.delete()


class ItemUnitFormTests(TestCase):
    """Das Artikelformular bietet die Einheit an."""

    def setUp(self):
        self.tax_rate = TaxRate.objects.create(
            code='UST19', name='Umsatzsteuer 19%', rate=Decimal('0.19'), is_active=True
        )
        self.kostenart = Kostenart.objects.create(name='Erlöse')
        self.active_unit = Unit.objects.create(code='STK', name='Stück')
        self.inactive_unit = Unit.objects.create(code='ALT', name='Alt', is_active=False)

    def _post_data(self, **overrides):
        data = {
            'article_no': 'ART-100',
            'short_text_1': 'Testartikel',
            'short_text_2': '',
            'long_text': '',
            'net_price': '10.00',
            'purchase_price': '5.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.kostenart.pk,
            'cost_type_2': '',
            'item_group': '',
            'unit': '',
            'item_type': 'MATERIAL',
            'is_discountable': 'on',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_unit_ist_teil_des_formulars(self):
        self.assertIn('unit', ItemForm().fields)

    def test_nur_aktive_einheiten_zur_auswahl(self):
        queryset = ItemForm().fields['unit'].queryset
        self.assertIn(self.active_unit, queryset)
        self.assertNotIn(self.inactive_unit, queryset)

    def test_einheit_darf_leer_bleiben(self):
        form = ItemForm(data=self._post_data())
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertIsNone(item.unit)

    def test_einheit_kann_gesetzt_werden(self):
        form = ItemForm(data=self._post_data(unit=self.active_unit.pk))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().unit, self.active_unit)

    def test_deaktivierte_zugewiesene_einheit_bleibt_speicherbar(self):
        """
        Wird eine Einheit nachträglich deaktiviert, darf das Bearbeiten des
        Artikels nicht an einem Wert scheitern, den niemand gewählt hat.
        """
        item = Item.objects.create(
            article_no='ART-200',
            short_text_1='Bestandsartikel',
            net_price=Decimal('10.00'),
            purchase_price=Decimal('5.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            item_type='MATERIAL',
            unit=self.inactive_unit,
        )
        form = ItemForm(
            data=self._post_data(article_no='ART-200', unit=self.inactive_unit.pk),
            instance=item,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().unit, self.inactive_unit)


class ItemUnitUiTests(TestCase):
    """Einheit ist in Liste, Detailformular und Admin sichtbar."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.tax_rate = TaxRate.objects.create(
            code='UST19', name='Umsatzsteuer 19%', rate=Decimal('0.19'), is_active=True
        )
        self.kostenart = Kostenart.objects.create(name='Erlöse')
        self.unit = Unit.objects.create(code='STK', name='Stück')
        self.item = Item.objects.create(
            article_no='ART-300',
            short_text_1='Testartikel',
            net_price=Decimal('10.00'),
            purchase_price=Decimal('5.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.kostenart,
            item_type='MATERIAL',
            unit=self.unit,
        )

    def test_artikelliste_hat_spalte_einheit(self):
        table = ItemTable(Item.objects.all())
        self.assertIn('unit', table.columns.names())
        self.assertEqual(table.columns['unit'].header, 'Einheit')

    def test_detailformular_rendert_einheit(self):
        response = self.client.get(
            reverse('item_edit_ajax', kwargs={'pk': self.item.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Mengeneinheit', content)
        self.assertIn('name="unit"', content)

    def test_admin_zeigt_einheit(self):
        self.assertIn('unit', ItemAdmin.list_display)
        admin_fields = [f for _, opts in ItemAdmin.fieldsets for f in opts['fields']]
        self.assertIn('unit', admin_fields)

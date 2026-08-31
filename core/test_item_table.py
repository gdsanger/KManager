"""
Tests for the article number rendering in ItemTable (Artikelverwaltung).

Die Artikelnummer ist kein Link, sondern ein Button, der auf der Seite das
Bearbeiten-Modal öffnet (siehe templates/core/item_management.html).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Item, ItemGroup, Kostenart, TaxRate
from core.tables import ItemTable


class ItemTableArticleNoRenderTestCase(TestCase):
    """Test ItemTable.render_article_no()"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tabletester',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='tabletester', password='testpass123')

        self.tax_rate = TaxRate.objects.create(
            code='VAT',
            name='Standard VAT',
            rate=Decimal('0.19')
        )
        self.cost_type = Kostenart.objects.create(
            name='Hauptkostenart Material',
            umsatzsteuer_satz='19'
        )
        self.main_group = ItemGroup.objects.create(
            code='MG-TBL',
            name='Hauptgruppe Tabelle',
            group_type='MAIN'
        )
        self.sub_group = ItemGroup.objects.create(
            code='SG-TBL',
            name='Untergruppe Tabelle',
            group_type='SUB',
            parent=self.main_group
        )
        self.item = Item.objects.create(
            article_no='TBL-001',
            short_text_1='Tabellen-Testartikel',
            net_price=Decimal('100.00'),
            purchase_price=Decimal('50.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type,
            item_group=self.sub_group,
            item_type='MATERIAL',
        )

    def _render_article_no(self):
        table = ItemTable(Item.objects.filter(pk=self.item.pk))
        return str(table.rows[0].get_cell('article_no'))

    def test_article_no_is_rendered_as_button(self):
        """Die Artikelnummer wird als Button ausgegeben, nicht als Link"""
        html = self._render_article_no()

        self.assertIn('<button type="button"', html)
        self.assertIn('TBL-001', html)
        self.assertNotIn('<a ', html)
        self.assertNotIn('href', html)

    def test_article_no_carries_item_id_for_the_modal(self):
        """Der Button trägt die data-item-id, die der Handler auswertet"""
        html = self._render_article_no()

        self.assertIn(f'data-item-id="{self.item.pk}"', html)
        self.assertIn('item-link', html)

    def test_article_no_does_not_produce_selected_parameter(self):
        """Der wirkungslose ?selected=-Parameter wird nicht mehr erzeugt"""
        html = self._render_article_no()

        self.assertNotIn('selected=', html)

    def test_item_management_page_has_no_selected_links(self):
        """Auch die gerenderte Seite enthält keine ?selected=-Links mehr"""
        response = self.client.get(reverse('item_management'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('?selected=', content)
        self.assertIn(f'data-item-id="{self.item.pk}"', content)

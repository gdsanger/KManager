from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from core.models import Item, Kostenart, TaxRate

User = get_user_model()


class AjaxSearchArticlesTestCase(TestCase):
    """Tests for the ajax_search_articles endpoint"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.tax_rate = TaxRate.objects.create(
            code='USt19',
            name='Umsatzsteuer 19%',
            rate=Decimal('0.19'),
            is_active=True
        )

        self.cost_type_main = Kostenart.objects.create(name='Hauptkostenart')
        self.cost_type_child = Kostenart.objects.create(
            name='Unterkostenart',
            parent=self.cost_type_main
        )

        self.item_exact = Item.objects.create(
            article_no='ART-001',
            short_text_1='Basispaket',
            short_text_2='Addon Pack',
            long_text='Beschreibung für Basispaket',
            net_price=Decimal('10.00'),
            purchase_price=Decimal('5.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_main,
            cost_type_2=self.cost_type_child,
            item_type='SERVICE',
            is_discountable=True
        )

        self.item_short_text_1 = Item.objects.create(
            article_no='ART-010',
            short_text_1='Widget Deluxe',
            short_text_2='',
            long_text='Premium Widget Beschreibung',
            net_price=Decimal('20.00'),
            purchase_price=Decimal('10.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_main,
            item_type='SERVICE',
            is_discountable=False
        )

        self.item_short_text_2 = Item.objects.create(
            article_no='ART-020',
            short_text_1='Service Paket',
            short_text_2='Accessory Bundle',
            long_text='',
            net_price=Decimal('15.00'),
            purchase_price=Decimal('7.50'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_main,
            item_type='SERVICE',
            is_discountable=True
        )

        self.item_description = Item.objects.create(
            article_no='ART-030',
            short_text_1='Spezial Service',
            short_text_2='',
            long_text='Ausführliche Spezialbeschreibung für Service',
            net_price=Decimal('30.00'),
            purchase_price=Decimal('15.00'),
            tax_rate=self.tax_rate,
            cost_type_1=self.cost_type_main,
            item_type='SERVICE',
            is_discountable=True
        )

        self.url = reverse('auftragsverwaltung:ajax_search_articles')

    def test_search_by_article_number_exact(self):
        response = self.client.get(self.url, {'q': 'ART-001'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('articles', data)
        self.assertEqual(len(data['articles']), 1)
        self.assertEqual(data['articles'][0]['article_no'], 'ART-001')

        expected_keys = {
            'id', 'article_no', 'short_text_1', 'short_text_2', 'long_text',
            'net_price', 'tax_rate_id', 'tax_rate_code', 'tax_rate',
            'is_discountable', 'cost_type_1_id', 'cost_type_2_id'
        }
        self.assertTrue(expected_keys.issubset(data['articles'][0].keys()))

    def test_search_by_short_text_1_partial(self):
        response = self.client.get(self.url, {'q': 'Widget'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        article_nos = [article['article_no'] for article in data.get('articles', [])]

        self.assertIn(self.item_short_text_1.article_no, article_nos)

    def test_search_by_short_text_2_partial(self):
        response = self.client.get(self.url, {'q': 'Accessory'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        article_nos = [article['article_no'] for article in data.get('articles', [])]

        self.assertIn(self.item_short_text_2.article_no, article_nos)

    def test_search_by_description_partial(self):
        response = self.client.get(self.url, {'q': 'Spezialbeschreibung'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        article_nos = [article['article_no'] for article in data.get('articles', [])]

        self.assertIn(self.item_description.article_no, article_nos)

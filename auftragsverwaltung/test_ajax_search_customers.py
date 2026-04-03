from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from core.models import Adresse

User = get_user_model()


class AjaxSearchCustomersTestCase(TestCase):
    """Tests for the ajax_search_customers endpoint"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create test customers with different name and company combinations
        self.customer_mueller = Adresse.objects.create(
            name='Max Müller',
            firma='',
            adressen_type='KUNDE',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland'
        )

        self.customer_schmidt_gmbh = Adresse.objects.create(
            name='Anna Schmidt',
            firma='Schmidt GmbH',
            adressen_type='KUNDE',
            strasse='Hauptstrasse 2',
            plz='54321',
            ort='München',
            land='Deutschland'
        )

        self.customer_technik = Adresse.objects.create(
            name='Peter Wagner',
            firma='Technik Solutions AG',
            adressen_type='KUNDE',
            strasse='Industrieweg 3',
            plz='67890',
            ort='Hamburg',
            land='Deutschland'
        )

        self.customer_no_firma = Adresse.objects.create(
            name='Lisa Weber',
            firma='',
            adressen_type='KUNDE',
            strasse='Bergstrasse 4',
            plz='98765',
            ort='Köln',
            land='Deutschland'
        )

        # Create a non-customer address (should not appear in results)
        self.supplier = Adresse.objects.create(
            name='Supplier Company',
            firma='Supplier GmbH',
            adressen_type='LIEFERANT',
            strasse='Lieferweg 5',
            plz='11111',
            ort='Frankfurt',
            land='Deutschland'
        )

        self.url = reverse('auftragsverwaltung:ajax_search_customers')

    def test_search_by_name_partial_beginning(self):
        """Test partial match at the beginning of name"""
        response = self.client.get(self.url, {'q': 'Max'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        self.assertEqual(len(data['customers']), 1)
        self.assertEqual(data['customers'][0]['name'], 'Max Müller')

    def test_search_by_name_partial_middle(self):
        """Test partial match in the middle of name (substring search)"""
        response = self.client.get(self.url, {'q': 'isa'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Lisa Weber', customer_names)

    def test_search_by_name_partial_end(self):
        """Test partial match at the end of name"""
        response = self.client.get(self.url, {'q': 'ller'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Max Müller', customer_names)

    def test_search_by_firma_partial(self):
        """Test partial match in firma field"""
        response = self.client.get(self.url, {'q': 'Schmidt'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        # Should match both Anna Schmidt (name) and Schmidt GmbH (firma)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Anna Schmidt', customer_names)

    def test_search_by_firma_middle_substring(self):
        """Test partial match in middle of firma field (Technik Solutions AG)"""
        response = self.client.get(self.url, {'q': 'echnik'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Peter Wagner', customer_names)

    def test_search_case_insensitive(self):
        """Test that search is case-insensitive"""
        # Test with lowercase search for uppercase name
        response = self.client.get(self.url, {'q': 'weber'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Lisa Weber', customer_names)

        # Test with uppercase search for lowercase name
        response = self.client.get(self.url, {'q': 'WAGNER'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        customer_names = [c['name'] for c in data['customers']]
        self.assertIn('Peter Wagner', customer_names)

    def test_search_only_customers(self):
        """Test that only customers (KUNDE) are returned, not suppliers"""
        response = self.client.get(self.url, {'q': 'Supplier'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        # Supplier should not be in results
        self.assertEqual(len(data['customers']), 0)

    def test_search_min_length_requirement(self):
        """Test that queries with less than 2 characters return empty results"""
        response = self.client.get(self.url, {'q': 'M'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        self.assertEqual(len(data['customers']), 0)

    def test_search_empty_query(self):
        """Test that empty query returns empty results"""
        response = self.client.get(self.url, {'q': ''})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        self.assertEqual(len(data['customers']), 0)

    def test_response_structure(self):
        """Test that response contains all expected fields"""
        response = self.client.get(self.url, {'q': 'Müller'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        self.assertGreater(len(data['customers']), 0)

        customer = data['customers'][0]
        expected_keys = {'id', 'name', 'firma', 'full_name'}
        self.assertTrue(expected_keys.issubset(customer.keys()))

    def test_full_name_includes_firma(self):
        """Test that full_name field includes firma when present"""
        response = self.client.get(self.url, {'q': 'Schmidt'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Find customer with firma
        customer_with_firma = next(
            (c for c in data['customers'] if c['name'] == 'Anna Schmidt'),
            None
        )
        self.assertIsNotNone(customer_with_firma)
        self.assertIn('Schmidt GmbH', customer_with_firma['full_name'])
        self.assertIn('Anna Schmidt', customer_with_firma['full_name'])

    def test_full_name_without_firma(self):
        """Test that full_name field works correctly when firma is empty"""
        response = self.client.get(self.url, {'q': 'Lisa'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        customer = data['customers'][0]
        self.assertEqual(customer['full_name'], 'Lisa Weber')
        self.assertEqual(customer['firma'], '')

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access the endpoint"""
        self.client.logout()
        response = self.client.get(self.url, {'q': 'Test'})

        # Should redirect to login page
        self.assertEqual(response.status_code, 302)

    def test_search_returns_max_20_results(self):
        """Test that search returns maximum 20 results"""
        # Create 25 customers with 'Test' in the name
        for i in range(25):
            Adresse.objects.create(
                name=f'Test Customer {i}',
                firma='',
                adressen_type='KUNDE',
                strasse=f'Street {i}',
                plz='12345',
                ort='City',
                land='Deutschland'
            )

        response = self.client.get(self.url, {'q': 'Test'})

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('customers', data)
        # Should return maximum 20 results
        self.assertEqual(len(data['customers']), 20)

"""
Regression test for HTTP 500 error fix when editing Eingangsrechnung.

This test verifies that the fix for issue #615 works correctly:
- The EingangsrechnungAufteilungFormSet uses the correct model (Eingangsrechnung)
- The formset can be initialized with an Eingangsrechnung instance without error
- The edit view returns 200 (not 500) when accessing the edit page
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal
from core.models import Adresse, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung, EingangsrechnungAufteilung
from vermietung.forms import EingangsrechnungAufteilungFormSet


class EingangsrechnungHttp500RegressionTestCase(TestCase):
    """Regression test for HTTP 500 error when editing Eingangsrechnung (Issue #615)"""

    def setUp(self):
        """Set up test data"""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create a supplier
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Supplier GmbH',
            strasse='Teststr. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )

        # Create a location
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Location',
            strasse='Locationstr. 1',
            plz='54321',
            ort='Locationstadt',
            land='Deutschland'
        )

        # Create a MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Building',
            type='GEBAEUDE',
            beschreibung='Test Description',
            fläche=Decimal('100.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )

        # Create cost type
        self.kostenart = Kostenart.objects.create(
            name='Test Cost Type',
            umsatzsteuer_satz=19.0
        )

        # Create an Eingangsrechnung
        self.rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date(2024, 1, 15),
            faelligkeit=date(2024, 2, 15),
            belegnummer='TEST-001',
            betreff='Test Invoice',
            status='NEU'
        )

        # Create an allocation
        self.aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.kostenart,
            nettobetrag=Decimal('100.00')
        )

    def test_formset_initialization_with_eingangsrechnung_instance(self):
        """Test that formset can be initialized with Eingangsrechnung instance without error"""
        # This should NOT raise ValueError: "Cannot query '...': Must be 'InvoiceIn' instance"
        try:
            formset = EingangsrechnungAufteilungFormSet(instance=self.rechnung)
            # If we get here, initialization was successful
            self.assertIsNotNone(formset)
            # Verify that the formset has the correct number of forms
            self.assertEqual(len(formset.forms), 2)  # 1 existing + 1 extra
        except ValueError as e:
            self.fail(f"Formset initialization failed with ValueError: {e}")

    def test_edit_view_returns_200_not_500(self):
        """Test that GET request to edit view returns 200, not 500"""
        url = reverse('vermietung:eingangsrechnung_edit', kwargs={'pk': self.rechnung.pk})

        # This should return 200, not 500
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
            f"Expected status code 200, got {response.status_code}. "
            f"This indicates the HTTP 500 error has not been fixed."
        )

        # Verify that the formset is in the context
        self.assertIn('formset', response.context)

        # Verify that the formset is properly initialized with our invoice
        formset = response.context['formset']
        self.assertEqual(formset.instance, self.rechnung)

        # Verify that the existing allocation is in the formset
        initial_forms = [f for f in formset.forms if f.instance.pk]
        self.assertEqual(len(initial_forms), 1)
        self.assertEqual(initial_forms[0].instance, self.aufteilung)

    def test_formset_saves_correctly_with_eingangsrechnung(self):
        """Test that formset saves correctly with Eingangsrechnung instance"""
        # Create formset with POST data
        post_data = {
            'aufteilungen-TOTAL_FORMS': '1',
            'aufteilungen-INITIAL_FORMS': '1',
            'aufteilungen-MIN_NUM_FORMS': '1',
            'aufteilungen-MAX_NUM_FORMS': '1000',
            'aufteilungen-0-id': self.aufteilung.pk,
            'aufteilungen-0-kostenart1': self.kostenart.pk,
            'aufteilungen-0-nettobetrag': '150.00',
            'aufteilungen-0-beschreibung': 'Updated allocation',
        }

        formset = EingangsrechnungAufteilungFormSet(post_data, instance=self.rechnung)

        # Formset should be valid
        self.assertTrue(formset.is_valid(), f"Formset errors: {formset.errors}")

        # Save should succeed
        formset.save()

        # Verify that the allocation was updated
        self.aufteilung.refresh_from_db()
        self.assertEqual(self.aufteilung.nettobetrag, Decimal('150.00'))
        self.assertEqual(self.aufteilung.beschreibung, 'Updated allocation')

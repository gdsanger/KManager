"""
Tests for Eingangsrechnung edit view, specifically for date field pre-population.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal
from core.models import Adresse, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung, EingangsrechnungAufteilung
from vermietung.forms import EingangsrechnungForm


class EingangsrechnungEditDateFieldsTestCase(TestCase):
    """Test case for date field pre-population in Eingangsrechnung edit form"""
    
    def setUp(self):
        """Set up test data for all tests"""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_staff=True  # Required for vermietung access
        )
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create a supplier (lieferant)
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Lieferant GmbH',
            strasse='Teststrasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland',
            email='test@lieferant.de'
        )
        
        # Create a location (standort)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Test',
            strasse='Standortstrasse 1',
            plz='54321',
            ort='Standortstadt',
            land='Deutschland'
        )
        
        # Create a mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testgebäude',
            type='GEBAEUDE',
            beschreibung='Test Beschreibung',
            fläche=Decimal('100.00'),
            standort=self.standort,
            mietpreis=Decimal('1000.00')
        )
        
        # Create cost types
        self.hauptkostenart = Kostenart.objects.create(
            name='Betriebskosten'
        )
        
        # Create an Eingangsrechnung with all date fields populated
        self.rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date(2024, 1, 15),
            faelligkeit=date(2024, 2, 15),
            belegnummer='INV-2024-001',
            betreff='Test Invoice',
            referenznummer='REF-001',
            leistungszeitraum_von=date(2024, 1, 1),
            leistungszeitraum_bis=date(2024, 1, 31),
            zahlungsdatum=date(2024, 2, 10),
            status='BEZAHLT',
            notizen='Test notes',
            umlagefaehig=True
        )
        
        # Create an allocation for the invoice
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('100.00'),
            beschreibung='Test allocation'
        )
    
    def test_eingangsrechnung_form_date_field_formats(self):
        """Test that EingangsrechnungForm sets correct format for date fields"""
        form = EingangsrechnungForm(instance=self.rechnung)
        
        # Check that all date fields have the correct widget format
        date_fields = ['belegdatum', 'faelligkeit', 'leistungszeitraum_von', 
                       'leistungszeitraum_bis', 'zahlungsdatum']
        
        for field_name in date_fields:
            with self.subTest(field=field_name):
                field = form.fields[field_name]
                self.assertEqual(
                    field.widget.format, 
                    '%Y-%m-%d',
                    f"Field {field_name} should have format '%Y-%m-%d'"
                )
                self.assertIn(
                    '%Y-%m-%d', 
                    field.input_formats,
                    f"Field {field_name} should accept input format '%Y-%m-%d'"
                )
    
    def test_eingangsrechnung_edit_view_renders_date_values(self):
        """Test that the edit view renders date field values correctly"""
        url = reverse('vermietung:eingangsrechnung_edit', kwargs={'pk': self.rechnung.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that date values are in the HTML in ISO format (YYYY-MM-DD)
        # This is the format HTML5 date inputs require
        self.assertContains(response, '2024-01-15')  # belegdatum
        self.assertContains(response, '2024-02-15')  # faelligkeit
        self.assertContains(response, '2024-01-01')  # leistungszeitraum_von
        self.assertContains(response, '2024-01-31')  # leistungszeitraum_bis
        self.assertContains(response, '2024-02-10')  # zahlungsdatum
    
    def test_eingangsrechnung_form_with_optional_date_fields_empty(self):
        """Test that form works correctly when optional date fields are empty"""
        # Create an invoice with only required date fields
        rechnung_minimal = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=date(2024, 3, 1),
            faelligkeit=date(2024, 4, 1),
            belegnummer='INV-2024-002',
            betreff='Minimal Invoice',
            status='NEU',
            umlagefaehig=True
        )
        
        # Create allocation
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=rechnung_minimal,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('50.00')
        )
        
        form = EingangsrechnungForm(instance=rechnung_minimal)
        
        # Required date fields should have values
        self.assertIsNotNone(form.initial.get('belegdatum'))
        self.assertIsNotNone(form.initial.get('faelligkeit'))
        
        # Optional date fields should be None/empty
        self.assertIsNone(form.initial.get('leistungszeitraum_von'))
        self.assertIsNone(form.initial.get('leistungszeitraum_bis'))
        self.assertIsNone(form.initial.get('zahlungsdatum'))
    
    def test_eingangsrechnung_edit_preserves_dates_on_save(self):
        """Test that editing and saving without changing dates preserves them"""
        url = reverse('vermietung:eingangsrechnung_edit', kwargs={'pk': self.rechnung.pk})
        
        # Submit the form without changing date values
        response = self.client.post(url, {
            'lieferant': self.lieferant.pk,
            'mietobjekt': self.mietobjekt.pk,
            'belegdatum': '2024-01-15',
            'faelligkeit': '2024-02-15',
            'belegnummer': 'INV-2024-001',
            'betreff': 'Test Invoice',
            'referenznummer': 'REF-001',
            'leistungszeitraum_von': '2024-01-01',
            'leistungszeitraum_bis': '2024-01-31',
            'zahlungsdatum': '2024-02-10',
            'status': 'BEZAHLT',
            'notizen': 'Test notes',
            'umlagefaehig': True,
            # Formset data
            'aufteilungen-TOTAL_FORMS': '1',
            'aufteilungen-INITIAL_FORMS': '1',
            'aufteilungen-MIN_NUM_FORMS': '1',
            'aufteilungen-MAX_NUM_FORMS': '1000',
            'aufteilungen-0-id': self.rechnung.aufteilungen.first().pk,
            'aufteilungen-0-kostenart1': self.hauptkostenart.pk,
            'aufteilungen-0-nettobetrag': '100.00',
            'aufteilungen-0-beschreibung': 'Test allocation',
        })
        
        # Should redirect to detail view on success
        self.assertEqual(response.status_code, 302)
        
        # Reload the invoice and verify dates are unchanged
        self.rechnung.refresh_from_db()
        self.assertEqual(self.rechnung.belegdatum, date(2024, 1, 15))
        self.assertEqual(self.rechnung.faelligkeit, date(2024, 2, 15))
        self.assertEqual(self.rechnung.leistungszeitraum_von, date(2024, 1, 1))
        self.assertEqual(self.rechnung.leistungszeitraum_bis, date(2024, 1, 31))
        self.assertEqual(self.rechnung.zahlungsdatum, date(2024, 2, 10))

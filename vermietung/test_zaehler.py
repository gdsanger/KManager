"""
Tests for Zaehler (Meter) and Zaehlerstand (Meter Reading) models and views.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from vermietung.models import (
    MietObjekt, Zaehler, Zaehlerstand, ZAEHLER_EINHEITEN
)
from core.models import Adresse, Mandant

User = get_user_model()


class ZaehlerModelTest(TestCase):
    """Test Zaehler model functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        # Create Standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort 1',
            strasse='Hauptstraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testobjekt',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            mandant=self.mandant
        )
    
    def test_create_zaehler(self):
        """Test creating a basic meter."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Hauptzähler Strom',
        )
        
        self.assertEqual(zaehler.mietobjekt, self.mietobjekt)
        self.assertEqual(zaehler.typ, 'STROM')
        self.assertEqual(zaehler.einheit, 'kWh')  # Auto-set from typ
        self.assertIsNone(zaehler.parent)
    
    def test_einheit_auto_set(self):
        """Test that einheit is automatically set based on typ."""
        for typ, expected_einheit in ZAEHLER_EINHEITEN.items():
            zaehler = Zaehler.objects.create(
                mietobjekt=self.mietobjekt,
                typ=typ,
                bezeichnung=f'Test {typ}',
            )
            self.assertEqual(zaehler.einheit, expected_einheit)
    
    def test_sub_meter_creation(self):
        """Test creating a sub-meter with parent."""
        parent = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Hauptzähler',
        )
        
        sub = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Garagenzähler',
            parent=parent
        )
        
        self.assertEqual(sub.parent, parent)
        self.assertIn(sub, parent.sub_zaehler.all())
    
    def test_parent_type_validation(self):
        """Test that parent must have same type."""
        parent = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Hauptzähler Strom',
        )
        
        # Try to create sub-meter with different type
        with self.assertRaises(ValidationError) as cm:
            zaehler = Zaehler(
                mietobjekt=self.mietobjekt,
                typ='GAS',  # Different type
                bezeichnung='Sub-Zähler',
                parent=parent
            )
            zaehler.save()
        
        self.assertIn('parent', cm.exception.error_dict)
    
    def test_circular_parent_validation(self):
        """Test that circular parent relationships are prevented."""
        zaehler1 = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Zähler 1',
        )
        
        zaehler2 = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Zähler 2',
            parent=zaehler1
        )
        
        # Try to create circular reference
        zaehler1.parent = zaehler2
        with self.assertRaises(ValidationError) as cm:
            zaehler1.save()
        
        self.assertIn('parent', cm.exception.error_dict)
    
    def test_get_letzter_zaehlerstand(self):
        """Test getting the latest meter reading."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        # No readings yet
        self.assertIsNone(zaehler.get_letzter_zaehlerstand())
        
        # Add readings
        stand1 = Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        stand2 = Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 2, 1),
            wert=Decimal('200.000')
        )
        
        latest = zaehler.get_letzter_zaehlerstand()
        self.assertEqual(latest, stand2)
    
    def test_berechne_verbrauch(self):
        """Test consumption calculation."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        # Add readings
        Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 2, 1),
            wert=Decimal('250.000')
        )
        Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 3, 1),
            wert=Decimal('350.000')
        )
        
        # Calculate full consumption
        verbrauch = zaehler.berechne_verbrauch()
        self.assertEqual(verbrauch, Decimal('250.000'))  # 350 - 100
        
        # Calculate consumption for specific period
        verbrauch_feb = zaehler.berechne_verbrauch(
            von_datum=date(2024, 2, 1),
            bis_datum=date(2024, 3, 1)
        )
        self.assertEqual(verbrauch_feb, Decimal('100.000'))  # 350 - 250
    
    def test_berechne_effektiver_verbrauch(self):
        """Test effective consumption with sub-meters."""
        # Create parent meter
        parent = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Hauptzähler',
        )
        
        # Create sub-meter
        sub = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Garagenzähler',
            parent=parent
        )
        
        # Add readings to parent
        Zaehlerstand.objects.create(
            zaehler=parent,
            datum=date(2024, 1, 1),
            wert=Decimal('1000.000')
        )
        Zaehlerstand.objects.create(
            zaehler=parent,
            datum=date(2024, 2, 1),
            wert=Decimal('1500.000')
        )
        
        # Add readings to sub-meter
        Zaehlerstand.objects.create(
            zaehler=sub,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        Zaehlerstand.objects.create(
            zaehler=sub,
            datum=date(2024, 2, 1),
            wert=Decimal('200.000')
        )
        
        # Parent consumption: 1500 - 1000 = 500
        # Sub consumption: 200 - 100 = 100
        # Effective consumption: 500 - 100 = 400
        
        effektiv = parent.berechne_effektiver_verbrauch()
        self.assertEqual(effektiv, Decimal('400.000'))


class ZaehlerstandModelTest(TestCase):
    """Test Zaehlerstand model functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        # Create Standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort 1',
            strasse='Hauptstraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testobjekt',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            mandant=self.mandant
        )
        
        # Create Zaehler
        self.zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
    
    def test_create_zaehlerstand(self):
        """Test creating a meter reading."""
        stand = Zaehlerstand.objects.create(
            zaehler=self.zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        
        self.assertEqual(stand.zaehler, self.zaehler)
        self.assertEqual(stand.datum, date(2024, 1, 1))
        self.assertEqual(stand.wert, Decimal('100.000'))
    
    def test_negative_value_validation(self):
        """Test that negative values are not allowed."""
        with self.assertRaises(ValidationError) as cm:
            stand = Zaehlerstand(
                zaehler=self.zaehler,
                datum=date(2024, 1, 1),
                wert=Decimal('-10.000')
            )
            stand.save()
        
        self.assertIn('wert', cm.exception.error_dict)
    
    def test_chronological_validation(self):
        """Test that readings must be chronologically plausible."""
        # Create first reading
        Zaehlerstand.objects.create(
            zaehler=self.zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        
        # Try to add later reading with smaller value
        with self.assertRaises(ValidationError) as cm:
            stand = Zaehlerstand(
                zaehler=self.zaehler,
                datum=date(2024, 2, 1),
                wert=Decimal('50.000')  # Smaller than previous
            )
            stand.save()
        
        self.assertIn('wert', cm.exception.error_dict)
    
    def test_unique_date_per_meter(self):
        """Test that only one reading per date per meter is allowed."""
        Zaehlerstand.objects.create(
            zaehler=self.zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        
        # Try to create another reading for same date
        with self.assertRaises(ValidationError):
            stand = Zaehlerstand(
                zaehler=self.zaehler,
                datum=date(2024, 1, 1),
                wert=Decimal('150.000')
            )
            stand.save()


class ZaehlerViewTest(TestCase):
    """Test Zaehler views."""
    
    def setUp(self):
        """Set up test data and client."""
        self.client = Client()
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.user.vermietung_access = True
        self.user.save()
        self.client.login(username='testuser', password='testpass123')
        
        # Create Mandant
        self.mandant = Mandant.objects.create(
            name="Test Mandant GmbH",
            adresse="Teststraße 1",
            plz="12345",
            ort="Teststadt",
            land="Deutschland"
        )
        
        # Create Standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort 1',
            strasse='Hauptstraße 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Testobjekt',
            type='GEBAEUDE',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('1000.00'),
            mandant=self.mandant
        )
    
    def test_zaehler_create_get(self):
        """Test GET request to create meter."""
        url = reverse('vermietung:zaehler_create', kwargs={'mietobjekt_pk': self.mietobjekt.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neuen Zähler anlegen')
    
    def test_zaehler_create_post(self):
        """Test POST request to create meter."""
        url = reverse('vermietung:zaehler_create', kwargs={'mietobjekt_pk': self.mietobjekt.pk})
        data = {
            'typ': 'STROM',
            'bezeichnung': 'Hauptzähler Strom',
            'einheit': 'kWh',
        }
        response = self.client.post(url, data)
        
        # Should redirect to mietobjekt detail
        self.assertEqual(response.status_code, 302)
        
        # Verify meter was created
        zaehler = Zaehler.objects.filter(mietobjekt=self.mietobjekt).first()
        self.assertIsNotNone(zaehler)
        self.assertEqual(zaehler.typ, 'STROM')
        self.assertEqual(zaehler.bezeichnung, 'Hauptzähler Strom')
    
    def test_zaehler_edit(self):
        """Test editing a meter."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        url = reverse('vermietung:zaehler_edit', kwargs={'pk': zaehler.pk})
        data = {
            'typ': 'STROM',
            'bezeichnung': 'Updated Name',
            'einheit': 'kWh',
        }
        response = self.client.post(url, data)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify update
        zaehler.refresh_from_db()
        self.assertEqual(zaehler.bezeichnung, 'Updated Name')
    
    def test_zaehler_delete(self):
        """Test deleting a meter."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        url = reverse('vermietung:zaehler_delete', kwargs={'pk': zaehler.pk})
        response = self.client.post(url)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify deletion
        self.assertFalse(Zaehler.objects.filter(pk=zaehler.pk).exists())
    
    def test_zaehler_detail(self):
        """Test meter detail view."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        url = reverse('vermietung:zaehler_detail', kwargs={'pk': zaehler.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, zaehler.bezeichnung)
    
    def test_zaehlerstand_create(self):
        """Test creating a meter reading."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        url = reverse('vermietung:zaehlerstand_create', kwargs={'zaehler_pk': zaehler.pk})
        data = {
            'datum': '2024-01-01',
            'wert': '100.000',
        }
        response = self.client.post(url, data)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify reading was created
        stand = Zaehlerstand.objects.filter(zaehler=zaehler).first()
        self.assertIsNotNone(stand)
        self.assertEqual(stand.wert, Decimal('100.000'))
    
    def test_zaehlerstand_delete(self):
        """Test deleting a meter reading."""
        zaehler = Zaehler.objects.create(
            mietobjekt=self.mietobjekt,
            typ='STROM',
            bezeichnung='Test',
        )
        
        stand = Zaehlerstand.objects.create(
            zaehler=zaehler,
            datum=date(2024, 1, 1),
            wert=Decimal('100.000')
        )
        
        url = reverse('vermietung:zaehlerstand_delete', kwargs={'pk': stand.pk})
        response = self.client.post(url)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify deletion
        self.assertFalse(Zaehlerstand.objects.filter(pk=stand.pk).exists())

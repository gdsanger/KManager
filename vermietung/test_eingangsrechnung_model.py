"""
Tests for Eingangsrechnung (Incoming Invoice) models and functionality.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from core.models import Adresse, Kostenart
from vermietung.models import MietObjekt, Eingangsrechnung, EingangsrechnungAufteilung


class EingangsrechnungModelTestCase(TestCase):
    """Test case for Eingangsrechnung model"""
    
    def setUp(self):
        """Set up test data for all tests"""
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
        
        # Create cost types (kostenarten)
        self.hauptkostenart = Kostenart.objects.create(
            name='Betriebskosten',
            umsatzsteuer_satz='19'
        )
        self.unterkostenart = Kostenart.objects.create(
            name='Heizung',
            parent=self.hauptkostenart,
            umsatzsteuer_satz='7'
        )
        
    def test_create_eingangsrechnung(self):
        """Test creating a basic incoming invoice"""
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date() + timezone.timedelta(days=30),
            belegnummer='RE-2024-001',
            betreff='Test Rechnung',
            status='NEU',
            umlagefaehig=True
        )
        
        self.assertIsNotNone(rechnung.pk)
        self.assertEqual(rechnung.belegnummer, 'RE-2024-001')
        self.assertEqual(rechnung.status, 'NEU')
        self.assertTrue(rechnung.umlagefaehig)
        self.assertIsNone(rechnung.zahlungsdatum)
    
    def test_eingangsrechnung_str(self):
        """Test string representation of Eingangsrechnung"""
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date(),
            belegnummer='RE-2024-001',
            betreff='Test'
        )
        
        expected = f"RE-2024-001 - {self.lieferant.name} - {rechnung.belegdatum}"
        self.assertEqual(str(rechnung), expected)
    
    def test_leistungszeitraum_validation(self):
        """Test that leistungszeitraum_bis must be after leistungszeitraum_von"""
        today = timezone.now().date()
        rechnung = Eingangsrechnung(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=today,
            faelligkeit=today,
            belegnummer='RE-2024-001',
            betreff='Test',
            leistungszeitraum_von=today,
            leistungszeitraum_bis=today - timezone.timedelta(days=1)
        )
        
        with self.assertRaises(ValidationError) as context:
            rechnung.full_clean()
        
        self.assertIn('leistungszeitraum_bis', context.exception.error_dict)
    
    def test_bezahlt_status_requires_zahlungsdatum(self):
        """Test that status BEZAHLT requires a payment date"""
        rechnung = Eingangsrechnung(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date(),
            belegnummer='RE-2024-001',
            betreff='Test',
            status='BEZAHLT',
            zahlungsdatum=None
        )
        
        with self.assertRaises(ValidationError) as context:
            rechnung.full_clean()
        
        self.assertIn('zahlungsdatum', context.exception.error_dict)
    
    def test_mark_as_paid(self):
        """Test marking an invoice as paid"""
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date(),
            belegnummer='RE-2024-001',
            betreff='Test',
            status='OFFEN'
        )
        
        payment_date = timezone.now().date()
        rechnung.mark_as_paid(payment_date)
        
        self.assertEqual(rechnung.status, 'BEZAHLT')
        self.assertEqual(rechnung.zahlungsdatum, payment_date)
    
    def test_mark_as_paid_default_date(self):
        """Test marking as paid without specifying date (uses today)"""
        rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date(),
            belegnummer='RE-2024-001',
            betreff='Test',
            status='OFFEN'
        )
        
        rechnung.mark_as_paid()
        
        self.assertEqual(rechnung.status, 'BEZAHLT')
        self.assertEqual(rechnung.zahlungsdatum, timezone.now().date())


class EingangsrechnungAufteilungModelTestCase(TestCase):
    """Test case for EingangsrechnungAufteilung model"""
    
    def setUp(self):
        """Set up test data"""
        # Create required entities
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Test Lieferant',
            strasse='Str 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )
        
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Str 2',
            plz='54321',
            ort='Stadt',
            land='Deutschland'
        )
        
        self.mietobjekt = MietObjekt.objects.create(
            name='Test',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort,
            mietpreis=Decimal('500.00')
        )
        
        self.rechnung = Eingangsrechnung.objects.create(
            lieferant=self.lieferant,
            mietobjekt=self.mietobjekt,
            belegdatum=timezone.now().date(),
            faelligkeit=timezone.now().date(),
            belegnummer='RE-001',
            betreff='Test'
        )
        
        # Create cost types
        self.hauptkostenart = Kostenart.objects.create(
            name='Energie',
            umsatzsteuer_satz='19'
        )
        self.unterkostenart = Kostenart.objects.create(
            name='Strom',
            parent=self.hauptkostenart,
            umsatzsteuer_satz='19'
        )
    
    def test_create_aufteilung(self):
        """Test creating an allocation"""
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('100.00')
        )
        
        self.assertIsNotNone(aufteilung.pk)
        self.assertEqual(aufteilung.nettobetrag, Decimal('100.00'))
    
    def test_umsatzsteuer_calculation(self):
        """Test VAT calculation for allocation"""
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('100.00')
        )
        
        # 19% VAT on 100.00 = 19.00
        self.assertEqual(aufteilung.umsatzsteuer, Decimal('19.00'))
    
    def test_bruttobetrag_calculation(self):
        """Test gross amount calculation"""
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('100.00')
        )
        
        # 100.00 + 19.00 = 119.00
        self.assertEqual(aufteilung.bruttobetrag, Decimal('119.00'))
    
    def test_unterkostenart_vat_rate(self):
        """Test that VAT rate comes from unterkostenart when specified"""
        # Create unterkostenart with different VAT rate
        unterkostenart_7 = Kostenart.objects.create(
            name='Gas',
            parent=self.hauptkostenart,
            umsatzsteuer_satz='7'
        )
        
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            kostenart2=unterkostenart_7,
            nettobetrag=Decimal('100.00')
        )
        
        # Should use 7% from kostenart2
        self.assertEqual(aufteilung.umsatzsteuer_satz, Decimal('7'))
        self.assertEqual(aufteilung.umsatzsteuer, Decimal('7.00'))
    
    def test_negative_nettobetrag_validation(self):
        """Test that negative net amounts are not allowed"""
        aufteilung = EingangsrechnungAufteilung(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('-100.00')
        )
        
        with self.assertRaises(ValidationError) as context:
            aufteilung.full_clean()
        
        self.assertIn('nettobetrag', context.exception.error_dict)
    
    def test_kostenart2_must_belong_to_kostenart1(self):
        """Test that kostenart2 must be a child of kostenart1"""
        # Create another hauptkostenart
        other_hauptkostenart = Kostenart.objects.create(
            name='Reparaturen',
            umsatzsteuer_satz='19'
        )
        
        aufteilung = EingangsrechnungAufteilung(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            kostenart2=other_hauptkostenart,  # Wrong parent!
            nettobetrag=Decimal('100.00')
        )
        
        with self.assertRaises(ValidationError) as context:
            aufteilung.full_clean()
        
        self.assertIn('kostenart2', context.exception.error_dict)
    
    def test_eingangsrechnung_totals(self):
        """Test that invoice totals are calculated from allocations"""
        # Create multiple allocations
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('100.00')
        )
        EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=self.hauptkostenart,
            nettobetrag=Decimal('50.00')
        )
        
        # Refresh from DB to get related allocations
        self.rechnung.refresh_from_db()
        
        # Total net: 150.00
        self.assertEqual(self.rechnung.nettobetrag, Decimal('150.00'))
        # Total VAT: 28.50 (19% of 150.00)
        self.assertEqual(self.rechnung.umsatzsteuer, Decimal('28.50'))
        # Total gross: 178.50
        self.assertEqual(self.rechnung.bruttobetrag, Decimal('178.50'))
    
    def test_zero_vat_calculation(self):
        """Test VAT calculation with 0% rate"""
        kostenart_0 = Kostenart.objects.create(
            name='Steuerfrei',
            umsatzsteuer_satz='0'
        )
        
        aufteilung = EingangsrechnungAufteilung.objects.create(
            eingangsrechnung=self.rechnung,
            kostenart1=kostenart_0,
            nettobetrag=Decimal('100.00')
        )
        
        self.assertEqual(aufteilung.umsatzsteuer, Decimal('0.00'))
        self.assertEqual(aufteilung.bruttobetrag, Decimal('100.00'))

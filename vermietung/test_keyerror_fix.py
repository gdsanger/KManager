"""
Test for KeyError fix in VertragForm when editing existing contracts.
This test verifies the fix for: Exception Type: KeyError at /vermietung/vertraege/1/bearbeiten/
"""

from django.test import TestCase
from datetime import date
from decimal import Decimal
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt
from vermietung.forms import VertragForm


class VertragFormKeyErrorFixTestCase(TestCase):
    """Test case for verifying KeyError fix in VertragForm."""
    
    def setUp(self):
        """Set up test data."""
        # Create test standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Standort',
            strasse='Test Strasse 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create test customer
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Kunde Strasse 1',
            plz='12345',
            ort='Kundestadt',
            land='Deutschland',
            email='kunde@example.com'
        )
        
        # Create test mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Büro',
            type='RAUM',
            beschreibung='Test Beschreibung',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True
        )
        
        # Create test contract with VertragsObjekt
        self.vertrag = Vertrag.objects.create(
            mieter=self.kunde,
            start=date(2024, 1, 1),
            ende=date(2024, 12, 31),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=self.vertrag,
            mietobjekt=self.mietobjekt
        )
        
    def test_vertrag_form_instantiation_with_instance_no_keyerror(self):
        """
        Test that VertragForm can be instantiated with an existing instance 
        without raising KeyError for 'mietobjekte' field.
        
        This reproduces the original issue:
        Exception Type: KeyError at /vermietung/vertraege/1/bearbeiten/
        Exception Value: 'mietobjekte'
        
        The issue occurred at:
        File "/opt/KManager/vermietung/forms.py", line 437, in __init__
            self.fields['mietobjekte'].initial = current_mietobjekte
        KeyError: 'mietobjekte'
        """
        # This should NOT raise a KeyError
        try:
            form = VertragForm(instance=self.vertrag)
            # If we get here, the KeyError is fixed
            self.assertIsNotNone(form)
            # Verify the form has the expected fields
            self.assertIn('mieter', form.fields)
            self.assertIn('start', form.fields)
            self.assertIn('ende', form.fields)
            self.assertIn('miete', form.fields)
            self.assertIn('kaution', form.fields)
            self.assertIn('status', form.fields)
            # Verify mietobjekte is NOT in the form fields (it's managed by formset)
            self.assertNotIn('mietobjekte', form.fields)
        except KeyError as e:
            self.fail(f"KeyError raised when instantiating VertragForm with instance: {e}")
    
    def test_vertrag_form_instantiation_without_instance_no_keyerror(self):
        """Test that VertragForm can be instantiated without an instance."""
        try:
            form = VertragForm()
            self.assertIsNotNone(form)
            self.assertNotIn('mietobjekte', form.fields)
        except KeyError as e:
            self.fail(f"KeyError raised when instantiating VertragForm: {e}")

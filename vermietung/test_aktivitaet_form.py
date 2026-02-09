"""
Tests for Aktivitaet form ensuring ersteller is set automatically.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from vermietung.models import Aktivitaet
from vermietung.forms import AktivitaetForm

User = get_user_model()


class AktivitaetFormErstellerTest(TestCase):
    """Tests for automatic ersteller setting in AktivitaetForm."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True
        )
    
    def test_form_sets_ersteller_for_new_activity(self):
        """Test that form automatically sets ersteller for new activities."""
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': 'Test description',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
            'privat': False,
            # Note: ersteller is not set in form data
        }
        
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        
        activity = form.save()
        
        # ersteller should be automatically set to current_user
        self.assertEqual(activity.ersteller, self.user)
    
    def test_form_respects_explicit_ersteller(self):
        """Test that form respects explicitly set ersteller."""
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            is_staff=True
        )
        
        form_data = {
            'titel': 'Test Activity',
            'beschreibung': 'Test description',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
            'ersteller': other_user.pk,  # Explicitly set to other_user
            'privat': False,
        }
        
        form = AktivitaetForm(data=form_data, current_user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        
        activity = form.save()
        
        # ersteller should be the explicitly set user, not current_user
        self.assertEqual(activity.ersteller, other_user)
    
    def test_form_does_not_override_ersteller_on_edit(self):
        """Test that form does not override ersteller when editing existing activity."""
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            is_staff=True
        )
        
        # Create activity with other_user as ersteller
        activity = Aktivitaet.objects.create(
            titel='Existing Activity',
            beschreibung='Test',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=other_user,
            privat=False,
        )
        
        # Edit the activity with current_user
        form_data = {
            'titel': 'Updated Activity',
            'beschreibung': 'Updated description',
            'status': 'IN_BEARBEITUNG',
            'prioritaet': 'HOCH',
            'ersteller': other_user.pk,  # Include the existing ersteller
            'privat': False,
        }
        
        form = AktivitaetForm(data=form_data, instance=activity, current_user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        
        activity = form.save()
        
        # ersteller should remain the original user
        self.assertEqual(activity.ersteller, other_user)
    
    def test_form_preserves_ersteller_when_cleared(self):
        """Test that ersteller is preserved even if cleared in form data during edit."""
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123',
            is_staff=True
        )
        
        # Create activity with other_user as ersteller
        activity = Aktivitaet.objects.create(
            titel='Existing Activity',
            beschreibung='Test',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=other_user,
            privat=False,
        )
        
        # Edit the activity and try to clear ersteller
        form_data = {
            'titel': 'Updated Activity',
            'beschreibung': 'Updated description',
            'status': 'IN_BEARBEITUNG',
            'prioritaet': 'HOCH',
            'ersteller': '',  # Try to clear ersteller
            'privat': False,
        }
        
        form = AktivitaetForm(data=form_data, instance=activity, current_user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        
        activity = form.save()
        
        # ersteller should be preserved (not cleared)
        self.assertEqual(activity.ersteller, other_user)

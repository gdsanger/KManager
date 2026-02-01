"""
Tests for Activity CC Users Feature.
Tests the M2M relationship, delta calculation, email notifications, and deduplication.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from datetime import date
from unittest.mock import patch, MagicMock, call

from core.models import Adresse, MailTemplate
from vermietung.models import MietObjekt, Aktivitaet
from core.mailing.service import send_mail, MailServiceError

User = get_user_model()


class ActivityCCUsersPersistenceTest(TestCase):
    """Test M2M relationship persistence for CC users."""
    
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com')
        self.user2 = User.objects.create_user(username='user2', email='user2@test.com')
        self.user3 = User.objects.create_user(username='user3', email='user3@test.com')
        self.creator = User.objects.create_user(username='creator', email='creator@test.com')
        
        # Create a standort for MietObjekt
        self.standort = Adresse.objects.create(
            name='Test Standort',
            adressen_type='STANDORT',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt'
        )
        
        # Create a test MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Object',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort
        )
    
    def test_cc_users_can_be_added_to_new_activity(self):
        """Test that CC users can be added when creating an activity."""
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        
        # Add CC users
        activity.cc_users.add(self.user1, self.user2)
        
        # Verify CC users are saved
        self.assertEqual(activity.cc_users.count(), 2)
        self.assertIn(self.user1, activity.cc_users.all())
        self.assertIn(self.user2, activity.cc_users.all())
    
    def test_cc_users_can_be_modified(self):
        """Test that CC users can be added and removed."""
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        
        # Add initial CC users
        activity.cc_users.add(self.user1)
        self.assertEqual(activity.cc_users.count(), 1)
        
        # Add more CC users
        activity.cc_users.add(self.user2, self.user3)
        self.assertEqual(activity.cc_users.count(), 3)
        
        # Remove a CC user
        activity.cc_users.remove(self.user1)
        self.assertEqual(activity.cc_users.count(), 2)
        self.assertNotIn(self.user1, activity.cc_users.all())
        self.assertIn(self.user2, activity.cc_users.all())
        self.assertIn(self.user3, activity.cc_users.all())
    
    def test_cc_users_persist_across_saves(self):
        """Test that CC users are maintained across saves."""
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        
        activity.cc_users.add(self.user1, self.user2)
        activity_id = activity.id
        
        # Reload from database
        activity = Aktivitaet.objects.get(id=activity_id)
        self.assertEqual(activity.cc_users.count(), 2)
        
        # Modify and save
        activity.titel = 'Updated Title'
        activity.save()
        
        # Reload and verify CC users are still there
        activity = Aktivitaet.objects.get(id=activity_id)
        self.assertEqual(activity.cc_users.count(), 2)
        self.assertIn(self.user1, activity.cc_users.all())
        self.assertIn(self.user2, activity.cc_users.all())


class ActivityCCUsersDeltaCalculationTest(TransactionTestCase):
    """Test delta calculation for CC users."""
    
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com')
        self.user2 = User.objects.create_user(username='user2', email='user2@test.com')
        self.user3 = User.objects.create_user(username='user3', email='user3@test.com')
        self.creator = User.objects.create_user(username='creator', email='creator@test.com')
        
        # Create a standort for MietObjekt
        self.standort = Adresse.objects.create(
            name='Test Standort',
            adressen_type='STANDORT',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt'
        )
        
        # Create a test MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Object',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort
        )
    
    @patch('vermietung.signals.send_mail')
    def test_added_cc_users_calculated_correctly(self, mock_send_mail):
        """Test that only newly added CC users receive notifications."""
        # Create activity with initial CC user
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        activity.cc_users.add(self.user1)
        
        # Clear mail outbox and mock calls
        mail.outbox = []
        mock_send_mail.reset_mock()
        
        # Add new CC users
        activity.cc_users.add(self.user2, self.user3)
        
        # Verify send_mail was called for only the newly added users
        self.assertTrue(mock_send_mail.called)
        
        # Check that the call included user2 and user3 but not user1
        calls = mock_send_mail.call_args_list
        self.assertTrue(len(calls) > 0)
        
        # Get the 'to' parameter from the call
        to_emails = calls[0][1]['to']
        self.assertIn('user2@test.com', to_emails)
        self.assertIn('user3@test.com', to_emails)
        self.assertNotIn('user1@test.com', to_emails)
    
    @patch('vermietung.signals.send_mail')
    def test_removed_cc_users_dont_get_notification(self, mock_send_mail):
        """Test that removed CC users don't receive notifications."""
        # Create activity with CC users
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        activity.cc_users.add(self.user1, self.user2)
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Remove a CC user
        activity.cc_users.remove(self.user1)
        
        # Verify no notification was sent for removal
        # (send_mail should not be called for removal)
        # The signal handler only triggers on 'post_add', not 'post_remove'
        # So we just verify that if it was called, it wasn't for user1
        if mock_send_mail.called:
            to_emails = mock_send_mail.call_args[1].get('to', [])
            self.assertNotIn('user1@test.com', to_emails)


class ActivityCCUsersEmailNotificationTest(TransactionTestCase):
    """Test email notifications for CC users."""
    
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com', first_name='User', last_name='One')
        self.user2 = User.objects.create_user(username='user2', email='user2@test.com', first_name='User', last_name='Two')
        self.assigned_user = User.objects.create_user(username='assigned', email='assigned@test.com', first_name='Assigned', last_name='User')
        self.creator = User.objects.create_user(username='creator', email='creator@test.com', first_name='Creator', last_name='User')
        
        # Create a standort for MietObjekt
        self.standort = Adresse.objects.create(
            name='Test Standort',
            adressen_type='STANDORT',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt'
        )
        
        # Create a test MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Object',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort
        )
    
    @patch('vermietung.signals.send_mail')
    def test_cc_users_receive_notification_on_creation(self, mock_send_mail):
        """Test that CC users receive notification when activity is created."""
        # Create activity with CC users
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assigned_user
        )
        activity.cc_users.add(self.user1, self.user2)
        
        # Verify send_mail was called for CC users
        self.assertTrue(mock_send_mail.called)
        
        # Find the call for CC users (should be the last one)
        calls = mock_send_mail.call_args_list
        cc_call = None
        for call in calls:
            to_emails = call[1].get('to', [])
            if 'user1@test.com' in to_emails or 'user2@test.com' in to_emails:
                cc_call = call
                break
        
        self.assertIsNotNone(cc_call, "CC users should have received notification")
        to_emails = cc_call[1]['to']
        self.assertIn('user1@test.com', to_emails)
        self.assertIn('user2@test.com', to_emails)
    
    @patch('vermietung.signals.send_mail')
    def test_cc_users_receive_notification_when_activity_completed(self, mock_send_mail):
        """Test that CC users receive notification when activity is completed."""
        # Create activity with CC users
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assigned_user,
            status='OFFEN'
        )
        activity.cc_users.add(self.user1, self.user2)
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        activity.status = 'ERLEDIGT'
        activity.save()
        
        # Verify send_mail was called
        self.assertTrue(mock_send_mail.called)
        
        # Check that CC users are in the recipient list
        call_args = mock_send_mail.call_args
        to_emails = call_args[1]['to']
        
        # All stakeholders should receive notification
        self.assertIn('user1@test.com', to_emails)
        self.assertIn('user2@test.com', to_emails)
        self.assertIn('creator@test.com', to_emails)
        self.assertIn('assigned@test.com', to_emails)


class ActivityCCUsersDeduplicationTest(TransactionTestCase):
    """Test email deduplication for CC users."""
    
    def setUp(self):
        """Set up test data."""
        # Create a user who will be both assigned and CC
        self.user1 = User.objects.create_user(username='user1', email='user1@test.com', first_name='User', last_name='One')
        self.creator = User.objects.create_user(username='creator', email='creator@test.com', first_name='Creator', last_name='User')
        
        # Create a standort for MietObjekt
        self.standort = Adresse.objects.create(
            name='Test Standort',
            adressen_type='STANDORT',
            strasse='Test Str. 1',
            plz='12345',
            ort='Test Stadt'
        )
        
        # Create a test MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Object',
            type='RAUM',
            beschreibung='Test',
            standort=self.standort
        )
    
    @patch('vermietung.signals.send_mail')
    def test_assigned_user_not_duplicated_in_cc_notification(self, mock_send_mail):
        """Test that assigned user doesn't receive duplicate notifications."""
        # Create activity where assigned user is also in CC list
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.user1
        )
        
        # Clear mock from assignment notification
        mock_send_mail.reset_mock()
        
        # Add assigned user to CC list
        activity.cc_users.add(self.user1)
        
        # Verify that if CC notification was sent, user1 is not in it
        # (because they already received assignment notification)
        if mock_send_mail.called:
            call_args = mock_send_mail.call_args
            to_emails = call_args[1].get('to', [])
            # user1 should be excluded from CC notification
            self.assertNotIn('user1@test.com', to_emails)
    
    @patch('vermietung.signals.send_mail')
    def test_creator_not_duplicated_in_cc_notification(self, mock_send_mail):
        """Test that creator doesn't receive duplicate CC notifications."""
        # Create activity where creator is also in CC list
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Add creator to CC list
        activity.cc_users.add(self.creator)
        
        # Verify that creator is excluded from CC notification
        if mock_send_mail.called:
            call_args = mock_send_mail.call_args
            to_emails = call_args[1].get('to', [])
            # Creator should be excluded from CC notification
            self.assertNotIn('creator@test.com', to_emails)
    
    @patch('vermietung.signals.send_mail')
    def test_completion_notification_deduplicated(self, mock_send_mail):
        """Test that completion notification is deduplicated correctly."""
        # Create activity where user is creator, assigned, and CC
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            mietobjekt=self.mietobjekt,
            ersteller=self.user1,
            assigned_user=self.user1,
            status='OFFEN'
        )
        activity.cc_users.add(self.user1)
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        activity.status = 'ERLEDIGT'
        activity.save()
        
        # Verify send_mail was called
        self.assertTrue(mock_send_mail.called)
        
        # Check that user1 appears only once in recipient list
        call_args = mock_send_mail.call_args
        to_emails = call_args[1]['to']
        
        # Count occurrences of user1's email
        user1_count = to_emails.count('user1@test.com')
        self.assertEqual(user1_count, 1, "User should receive only one email, not duplicates")

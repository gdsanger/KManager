"""
Tests for Activity Reminder Email functionality.
Tests the management command, template, and reminder logic.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch, MagicMock

from core.models import Adresse, MailTemplate
from vermietung.models import MietObjekt, Aktivitaet
from core.mailing.service import render_template

User = get_user_model()


class ActivityReminderMailTemplateTest(TestCase):
    """Test that the activity reminder mail template exists and renders correctly."""
    
    def test_reminder_template_exists(self):
        """Test that activity-reminder template exists."""
        template = MailTemplate.objects.filter(key='activity-reminder').first()
        self.assertIsNotNone(template, "activity-reminder template should exist after migration")
        self.assertEqual(template.subject, 'Erinnerung: {{ activity_title }} fällig in 2 Tagen')
        self.assertTrue(template.is_active)
    
    def test_render_reminder_template_complete_context(self):
        """Test rendering reminder template with all variables."""
        template = MailTemplate.objects.get(key='activity-reminder')
        
        context = {
            'assignee_name': 'John Doe',
            'activity_title': 'Wichtige Aufgabe',
            'activity_description': 'Dies ist eine wichtige Aufgabe',
            'activity_priority': 'Hoch',
            'activity_due_date': '02.02.2026',
            'activity_context': 'Mietobjekt: Büro 1',
            'activity_url': 'http://localhost:8000/aktivitaeten/1/bearbeiten/',
            'creator_name': 'Jane Smith',
            'creator_email': 'jane@example.com',
        }
        
        subject, html = render_template(template, context)
        
        # Check subject
        self.assertEqual(subject, 'Erinnerung: Wichtige Aufgabe fällig in 2 Tagen')
        
        # Check HTML contains key elements
        self.assertIn('John Doe', html)
        self.assertIn('Wichtige Aufgabe', html)
        self.assertIn('Dies ist eine wichtige Aufgabe', html)
        self.assertIn('Hoch', html)
        self.assertIn('02.02.2026', html)
        self.assertIn('Mietobjekt: Büro 1', html)
        self.assertIn('Jane Smith', html)
        self.assertIn('jane@example.com', html)
        self.assertIn('http://localhost:8000/aktivitaeten/1/bearbeiten/', html)
        # Check for reminder-specific text
        self.assertIn('2 Tagen', html)
        self.assertIn('Erinnerung', html)
    
    def test_render_reminder_template_minimal_context(self):
        """Test rendering with minimal required context."""
        template = MailTemplate.objects.get(key='activity-reminder')
        
        context = {
            'assignee_name': 'John Doe',
            'activity_title': 'Einfache Aufgabe',
            'activity_description': '',
            'activity_priority': 'Normal',
            'activity_due_date': '',
            'activity_context': '',
            'activity_url': 'http://localhost:8000/aktivitaeten/2/',
            'creator_name': '',
            'creator_email': '',
        }
        
        subject, html = render_template(template, context)
        
        # Should not crash with empty values
        self.assertEqual(subject, 'Erinnerung: Einfache Aufgabe fällig in 2 Tagen')
        self.assertIn('John Doe', html)
        self.assertIn('Einfache Aufgabe', html)


class ActivityReminderCommandTest(TestCase):
    """Test the send_activity_reminders management command."""
    
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.assignee = User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            first_name='Max',
            last_name='Mustermann'
        )
        
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com'
        )
        
        self.user_no_email = User.objects.create_user(
            username='nomail',
            email=''
        )
        
        # Create test address (for context)
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststr. 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland'
        )
        
        # Create test standort (location address)
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort Berlin',
            strasse='Berliner Str. 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland'
        )
        
        # Create test mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Objekt',
            type='LAGERRAUM',
            beschreibung='Test Beschreibung',
            standort=self.standort,
            mietpreis=1000.00,
            nebenkosten=200.00
        )
        
        # Calculate dates
        self.today = date.today()
        self.in_2_days = self.today + timedelta(days=2)
        self.in_3_days = self.today + timedelta(days=3)
        self.yesterday = self.today - timedelta(days=1)
    
    def test_finds_activity_due_in_2_days(self):
        """Test that command finds activities due in exactly 2 days."""
        activity = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test',
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('Found 1 activity/activities', output)
        self.assertIn('Test Aktivität', output)
    
    def test_sends_reminder_email(self):
        """Test that reminder email is actually sent."""
        activity = Aktivitaet.objects.create(
            titel='Test Aktivität',
            beschreibung='Test Beschreibung',
            status='OFFEN',
            prioritaet='HOCH',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            mietobjekt=self.mietobjekt
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        # Check that send_mail was called
        mock_send.assert_called_once()
        
        # Check the arguments
        call_args = mock_send.call_args
        self.assertEqual(call_args[1]['template_key'], 'activity-reminder')
        self.assertEqual(call_args[1]['to'], ['assignee@example.com'])
        
        # Check context
        context = call_args[1]['context']
        self.assertEqual(context['activity_title'], 'Test Aktivität')
        self.assertEqual(context['assignee_name'], 'Max Mustermann')
        self.assertIn('Mietobjekt:', context['activity_context'])
        
        # Check that reminder_sent_at was set
        activity.refresh_from_db()
        self.assertIsNotNone(activity.reminder_sent_at)
    
    def test_idempotency_no_duplicate_reminders(self):
        """Test that reminder is only sent once (idempotent)."""
        activity = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde,
            reminder_sent_at=timezone.now()  # Already sent
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        # Should not send email
        mock_send.assert_not_called()
        
        output = out.getvalue()
        self.assertIn('No activities found', output)
    
    def test_ignores_completed_activities(self):
        """Test that completed activities don't get reminders."""
        activity = Aktivitaet.objects.create(
            titel='Completed Aktivität',
            status='ERLEDIGT',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        # Should not send email
        mock_send.assert_not_called()
        
        output = out.getvalue()
        self.assertIn('No activities found', output)
    
    def test_ignores_cancelled_activities(self):
        """Test that cancelled activities don't get reminders."""
        activity = Aktivitaet.objects.create(
            titel='Cancelled Aktivität',
            status='ABGEBROCHEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        mock_send.assert_not_called()
    
    def test_ignores_activities_not_due_in_2_days(self):
        """Test that only activities due in exactly 2 days get reminders."""
        # Activity due in 3 days
        activity1 = Aktivitaet.objects.create(
            titel='Due in 3 days',
            status='OFFEN',
            faellig_am=self.in_3_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        # Activity due yesterday
        activity2 = Aktivitaet.objects.create(
            titel='Due yesterday',
            status='OFFEN',
            faellig_am=self.yesterday,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        # Should not send any emails
        mock_send.assert_not_called()
    
    def test_ignores_activities_without_assigned_user(self):
        """Test that activities without assigned user don't get reminders."""
        activity = Aktivitaet.objects.create(
            titel='Unassigned Aktivität',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=None,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        mock_send.assert_not_called()
    
    def test_ignores_activities_with_user_without_email(self):
        """Test that activities assigned to users without email don't get reminders."""
        activity = Aktivitaet.objects.create(
            titel='User without email',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.user_no_email,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        mock_send.assert_not_called()
    
    def test_dry_run_mode(self):
        """Test that dry-run mode doesn't send emails or mark reminders as sent."""
        activity = Aktivitaet.objects.create(
            titel='Test Aktivität',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', '--dry-run', stdout=out)
        
        # Should not actually send email
        mock_send.assert_not_called()
        
        # Should not mark as sent
        activity.refresh_from_db()
        self.assertIsNone(activity.reminder_sent_at)
        
        # Should show in output
        output = out.getvalue()
        self.assertIn('[DRY RUN]', output)
        self.assertIn('Would send reminder', output)
    
    def test_handles_multiple_activities(self):
        """Test that command handles multiple activities correctly."""
        activity1 = Aktivitaet.objects.create(
            titel='Aktivität 1',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        activity2 = Aktivitaet.objects.create(
            titel='Aktivität 2',
            status='IN_BEARBEITUNG',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            mietobjekt=self.mietobjekt
        )
        
        out = StringIO()
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            call_command('send_activity_reminders', stdout=out)
        
        # Should send 2 emails
        self.assertEqual(mock_send.call_count, 2)
        
        # Both should be marked as sent
        activity1.refresh_from_db()
        activity2.refresh_from_db()
        self.assertIsNotNone(activity1.reminder_sent_at)
        self.assertIsNotNone(activity2.reminder_sent_at)
    
    def test_continues_on_error(self):
        """Test that command continues processing even if one email fails."""
        activity1 = Aktivitaet.objects.create(
            titel='Aktivität 1',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        activity2 = Aktivitaet.objects.create(
            titel='Aktivität 2',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            mietobjekt=self.mietobjekt
        )
        
        out = StringIO()
        
        # Mock send_mail to fail on first call, succeed on second
        with patch('vermietung.management.commands.send_activity_reminders.send_mail') as mock_send:
            from core.mailing.service import MailServiceError
            mock_send.side_effect = [
                MailServiceError("Test error"),
                None  # Success
            ]
            
            call_command('send_activity_reminders', stdout=out)
        
        # Should have attempted to send 2 emails
        self.assertEqual(mock_send.call_count, 2)
        
        # Exactly one should be marked as sent (the one that succeeded)
        activity1.refresh_from_db()
        activity2.refresh_from_db()
        sent_count = sum([
            activity1.reminder_sent_at is not None,
            activity2.reminder_sent_at is not None
        ])
        self.assertEqual(sent_count, 1, "Exactly one activity should be marked as sent")
        
        # Output should show error
        output = out.getvalue()
        self.assertIn('Error', output)


class ActivityReminderEmailCCTest(TestCase):
    """Test CC functionality in activity reminder emails."""
    
    def setUp(self):
        """Set up test data."""
        # Create users with different emails
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            first_name='Creator',
            last_name='User'
        )
        
        self.assignee = User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            first_name='Assignee',
            last_name='User'
        )
        
        self.same_user = User.objects.create_user(
            username='sameuser',
            email='same@example.com',
            first_name='Same',
            last_name='User'
        )
        
        # Create test address
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Test Kunde',
            strasse='Teststr. 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland'
        )
        
        # Calculate dates
        self.today = date.today()
        self.in_2_days = self.today + timedelta(days=2)
    
    @patch('vermietung.management.commands.send_activity_reminders.send_mail')
    def test_reminder_email_includes_creator_in_cc(self, mock_send_mail):
        """Test that reminder email includes creator in CC when creator != assignee."""
        activity = Aktivitaet.objects.create(
            titel='Test Activity',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=self.creator,
            kunde=self.kunde
        )
        
        out = StringIO()
        call_command('send_activity_reminders', stdout=out)
        
        # Check that send_mail was called with CC
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.assignee.email])
        
        # Verify CC includes creator
        self.assertIn('cc', call_args[1])
        self.assertIn(self.creator.email, call_args[1]['cc'])
        
        # Verify no duplicate (creator should not be in To)
        self.assertNotIn(self.creator.email, call_args[1]['to'])
    
    @patch('vermietung.management.commands.send_activity_reminders.send_mail')
    def test_reminder_email_no_cc_when_creator_is_assignee(self, mock_send_mail):
        """Test that reminder email has no CC when creator == assignee."""
        activity = Aktivitaet.objects.create(
            titel='Self-Assigned Activity',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.same_user,
            ersteller=self.same_user,
            kunde=self.kunde
        )
        
        out = StringIO()
        call_command('send_activity_reminders', stdout=out)
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.same_user.email])
        
        # Verify CC is empty (no duplicate)
        self.assertEqual(call_args[1]['cc'], [])
    
    @patch('vermietung.management.commands.send_activity_reminders.send_mail')
    def test_reminder_email_no_cc_when_creator_has_no_email(self, mock_send_mail):
        """Test that reminder email has no CC when creator has no email."""
        creator_no_email = User.objects.create_user(
            username='no_email_creator',
            email='',  # No email
        )
        
        activity = Aktivitaet.objects.create(
            titel='Activity without creator email',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=creator_no_email,
            kunde=self.kunde
        )
        
        out = StringIO()
        call_command('send_activity_reminders', stdout=out)
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.assignee.email])
        
        # Verify CC is empty (creator has no email)
        self.assertEqual(call_args[1]['cc'], [])
    
    @patch('vermietung.management.commands.send_activity_reminders.send_mail')
    def test_reminder_email_no_cc_when_no_creator(self, mock_send_mail):
        """Test that reminder email has no CC when there's no creator."""
        activity = Aktivitaet.objects.create(
            titel='Activity without creator',
            status='OFFEN',
            faellig_am=self.in_2_days,
            assigned_user=self.assignee,
            ersteller=None,
            kunde=self.kunde
        )
        
        out = StringIO()
        call_command('send_activity_reminders', stdout=out)
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.assignee.email])
        
        # Verify CC is empty (no creator)
        self.assertEqual(call_args[1]['cc'], [])

"""
Tests for Activity Mail Templates and Notifications.
Tests the migration, signal handlers, template rendering, and UI integration.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from core.models import Adresse, MailTemplate
from vermietung.models import MietObjekt, Aktivitaet
from core.mailing.service import render_template, MailServiceError

User = get_user_model()


class ActivityMailTemplateCreationTest(TestCase):
    """Test that mail templates are created by migration."""
    
    def test_activity_assigned_template_exists(self):
        """Test that activity-assigned template exists."""
        template = MailTemplate.objects.filter(key='activity-assigned').first()
        self.assertIsNotNone(template, "activity-assigned template should exist after migration")
        self.assertEqual(template.subject, 'Neue Aktivität zugewiesen: {{ activity_title }}')
        self.assertTrue(template.is_active)
        
    def test_activity_completed_template_exists(self):
        """Test that activity-completed template exists."""
        template = MailTemplate.objects.filter(key='activity-completed').first()
        self.assertIsNotNone(template, "activity-completed template should exist after migration")
        self.assertEqual(template.subject, 'Aktivität erledigt: {{ activity_title }}')
        self.assertTrue(template.is_active)


class ActivityMailTemplateRenderingTest(TestCase):
    """Test template rendering with various contexts."""
    
    def setUp(self):
        """Set up test templates and context."""
        # Templates should exist from migration
        self.assigned_template = MailTemplate.objects.get(key='activity-assigned')
        self.completed_template = MailTemplate.objects.get(key='activity-completed')
    
    def test_render_assigned_template_complete_context(self):
        """Test rendering assigned template with all variables."""
        context = {
            'assignee_name': 'John Doe',
            'activity_title': 'Fix bug in system',
            'activity_description': 'The login page has an error',
            'activity_priority': 'Hoch',
            'activity_due_date': '31.01.2026',
            'activity_context': 'Mietobjekt: Büro 1',
            'activity_url': 'http://localhost:8000/aktivitaeten/1/bearbeiten/',
            'creator_name': 'Jane Smith',
            'creator_email': 'jane@example.com',
        }
        
        subject, html = render_template(self.assigned_template, context)
        
        # Check subject
        self.assertEqual(subject, 'Neue Aktivität zugewiesen: Fix bug in system')
        
        # Check HTML contains key elements
        self.assertIn('John Doe', html)
        self.assertIn('Fix bug in system', html)
        self.assertIn('The login page has an error', html)
        self.assertIn('Hoch', html)
        self.assertIn('31.01.2026', html)
        self.assertIn('Mietobjekt: Büro 1', html)
        self.assertIn('Jane Smith', html)
        self.assertIn('jane@example.com', html)
        self.assertIn('http://localhost:8000/aktivitaeten/1/bearbeiten/', html)
    
    def test_render_assigned_template_minimal_context(self):
        """Test rendering with minimal required context."""
        context = {
            'assignee_name': 'John Doe',
            'activity_title': 'Simple task',
            'activity_description': '',
            'activity_priority': 'Normal',
            'activity_due_date': '',
            'activity_context': '',
            'activity_url': 'http://localhost:8000/aktivitaeten/2/',
            'creator_name': '',
            'creator_email': '',
        }
        
        subject, html = render_template(self.assigned_template, context)
        
        # Should not crash with empty values
        self.assertEqual(subject, 'Neue Aktivität zugewiesen: Simple task')
        self.assertIn('John Doe', html)
        self.assertIn('Simple task', html)
    
    def test_render_completed_template(self):
        """Test rendering completed template."""
        context = {
            'creator_name': 'Jane Smith',
            'activity_title': 'Fixed bug',
            'activity_context': 'Vertrag: V-2025-001',
            'activity_url': 'http://localhost:8000/aktivitaeten/1/',
            'completed_by_name': 'John Doe',
            'completed_at': '30.01.2026 14:30',
        }
        
        subject, html = render_template(self.completed_template, context)
        
        # Check subject
        self.assertEqual(subject, 'Aktivität erledigt: Fixed bug')
        
        # Check HTML
        self.assertIn('Jane Smith', html)
        self.assertIn('Fixed bug', html)
        self.assertIn('John Doe', html)
        self.assertIn('30.01.2026 14:30', html)
        self.assertIn('Vertrag: V-2025-001', html)


class ActivitySignalNotificationTest(TestCase):
    """Test signal handlers that send email notifications."""
    
    def setUp(self):
        """Set up test data."""
        # Clear the test outbox
        mail.outbox = []
        
        # Create users
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123'
        )
        
        self.assignee = User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            password='pass123'
        )
        
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass123'
        )
        
        # Create a standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )
        
        # Create a MietObjekt for context
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            verfuegbar=True
        )
    
    @patch('vermietung.signals.send_mail')
    def test_signal_sends_mail_on_create_with_assignee(self, mock_send_mail):
        """Test that creating activity with assignee sends email."""
        # Create activity with assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test description',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify call arguments
        self.assertEqual(call_args[1]['template_key'], 'activity-assigned')
        self.assertIn(self.assignee.email, call_args[1]['to'])
        self.assertIn('activity_title', call_args[1]['context'])
        self.assertEqual(call_args[1]['context']['activity_title'], 'Test Activity')
    
    @patch('vermietung.signals.send_mail')
    def test_signal_does_not_send_mail_on_create_without_assignee(self, mock_send_mail):
        """Test that creating activity without assignee does NOT send email."""
        # Create activity without assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Unassigned Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=None
        )
        
        # No mail should be sent
        self.assertFalse(mock_send_mail.called)
    
    @patch('vermietung.signals.send_mail')
    def test_signal_sends_mail_on_assignee_change(self, mock_send_mail):
        """Test that changing assignee sends email to new assignee."""
        # Create activity without assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Reassigned Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=None
        )
        
        # Clear the mock
        mock_send_mail.reset_mock()
        
        # Assign user
        aktivitaet.assigned_user = self.assignee
        aktivitaet.save()
        
        # Check that mail was sent
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['template_key'], 'activity-assigned')
        self.assertIn(self.assignee.email, call_args[1]['to'])
    
    @patch('vermietung.signals.send_mail')
    def test_signal_sends_mail_on_reassignment(self, mock_send_mail):
        """Test reassigning to different user sends mail to new user only."""
        # Create activity with first assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity to Reassign',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Reassign to other user
        aktivitaet.assigned_user = self.other_user
        aktivitaet.save()
        
        # Check mail sent to new assignee only
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        self.assertIn(self.other_user.email, call_args[1]['to'])
        # Should NOT contain old assignee
        self.assertNotIn(self.assignee.email, call_args[1]['to'])
    
    @patch('vermietung.signals.send_mail')
    def test_signal_does_not_send_mail_on_save_without_assignee_change(self, mock_send_mail):
        """Test that saving without changing assignee does not send duplicate mail."""
        # Create activity with assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='No Change Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Save again without changing assignee
        aktivitaet.beschreibung = 'Updated description'
        aktivitaet.save()
        
        # No mail should be sent (deduplication)
        self.assertFalse(mock_send_mail.called)
    
    @patch('vermietung.signals.send_mail')
    def test_signal_sends_completed_mail_to_creator(self, mock_send_mail):
        """Test that marking activity as completed sends mail to creator."""
        # Create activity
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity to Complete',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        aktivitaet.status = 'ERLEDIGT'
        aktivitaet.save()
        
        # Check completed mail sent to creator
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['template_key'], 'activity-completed')
        self.assertIn(self.creator.email, call_args[1]['to'])
    
    @patch('vermietung.signals.send_mail')
    def test_signal_does_not_send_completed_mail_twice(self, mock_send_mail):
        """Test that saving already completed activity does not send duplicate mail."""
        # Create completed activity
        aktivitaet = Aktivitaet.objects.create(
            titel='Already Completed',
            status='ERLEDIGT',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Save again
        aktivitaet.beschreibung = 'Update'
        aktivitaet.save()
        
        # No completed mail should be sent (deduplication)
        self.assertFalse(mock_send_mail.called)


class ActivityMarkCompletedViewTest(TestCase):
    """Test the mark completed view and UI integration."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='pass123',
            is_staff=True  # Need staff permission for vermietung views
        )
        self.client.login(username='testuser', password='pass123')
        
        # Add user to Vermietung group if it exists, or make superuser
        self.user.is_superuser = True
        self.user.save()
        
        # Create standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Standort',
            strasse='Str 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )
        
        # Create mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Raum 1',
            type='RAUM',
            standort=self.standort,
            mietpreis=Decimal('100.00'),
            verfuegbar=True
        )
        
        # Create activity
        self.aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.user
        )
    
    @patch('vermietung.signals.send_mail')
    def test_mark_completed_view_changes_status(self, mock_send_mail):
        """Test that mark completed view changes status to ERLEDIGT."""
        url = reverse('vermietung:aktivitaet_mark_completed', kwargs={'pk': self.aktivitaet.pk})
        
        response = self.client.post(url)
        
        # Should redirect to edit view
        self.assertEqual(response.status_code, 302)
        
        # Check status changed
        self.aktivitaet.refresh_from_db()
        self.assertEqual(self.aktivitaet.status, 'ERLEDIGT')
    
    @patch('vermietung.signals.send_mail')
    def test_mark_completed_already_completed(self, mock_send_mail):
        """Test marking already completed activity shows info message."""
        # Clear mock first
        mock_send_mail.reset_mock()
        
        # Set activity to completed
        self.aktivitaet.status = 'ERLEDIGT'
        self.aktivitaet.save()
        
        # Clear mock again after save
        mock_send_mail.reset_mock()
        
        url = reverse('vermietung:aktivitaet_mark_completed', kwargs={'pk': self.aktivitaet.pk})
        
        response = self.client.post(url, follow=True)
        
        # Check message
        messages = list(response.context['messages'])
        self.assertTrue(any('bereits' in str(m).lower() for m in messages))
    
    def test_mark_completed_button_visible_when_not_completed(self):
        """Test that mark completed button is visible in edit form when status != ERLEDIGT."""
        url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': self.aktivitaet.pk})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Als erledigt markieren')
        self.assertContains(response, 'markAsCompleted()')
    
    def test_mark_completed_button_not_visible_when_completed(self):
        """Test that mark completed button is NOT visible when activity is already completed."""
        # Set to completed
        self.aktivitaet.status = 'ERLEDIGT'
        self.aktivitaet.save()
        
        url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': self.aktivitaet.pk})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Button should not be present
        self.assertNotContains(response, 'Als erledigt markieren')


class ActivityAssignmentButtonTest(TransactionTestCase):
    """Test the assignment button and modal functionality."""
    
    def setUp(self):
        """Set up test data."""
        from core.models import Mandant
        
        # Create mandant
        self.mandant = Mandant.objects.create(name='Test Mandant')
        
        # Create users
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='testpass123'
        )
        self.assignee1 = User.objects.create_user(
            username='assignee1',
            email='assignee1@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.assignee2 = User.objects.create_user(
            username='assignee2',
            email='assignee2@example.com',
            password='testpass123',
            first_name='Jane',
            last_name='Smith'
        )
        
        # Create standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Test Standort',
            strasse='Test Str.',
            plz='12345',
            ort='Test Stadt'
        )
        
        # Create mietobjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Test Objekt',
            mandant=self.mandant,
            standort=self.standort,
            verfuegbare_einheiten=10,
            mietpreis=Decimal('1000.00')
        )
        
        # Create activity
        self.aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test Description',
            ersteller=self.creator,
            assigned_user=self.assignee1,
            mietobjekt=self.mietobjekt,
            status='OFFEN'
        )
        
        # Mark creator as staff to pass vermietung_required
        self.creator.is_staff = True
        self.creator.save()
        
        # Login
        self.client.login(username='creator', password='testpass123')
    
    def test_assignment_button_visible_in_edit_view(self):
        """Test that assignment button is visible in edit view."""
        url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': self.aktivitaet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that button is visible
        self.assertContains(response, 'Zuweisen')
        self.assertContains(response, 'id="assignModal"')
    
    def test_assignment_button_not_visible_in_create_view(self):
        """Test that assignment button is NOT visible in create view."""
        url = reverse('vermietung:aktivitaet_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that modal is NOT present
        self.assertNotContains(response, 'id="assignModal"')
    
    def test_assignment_modal_contains_users(self):
        """Test that assignment modal contains list of users."""
        url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': self.aktivitaet.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that users are in the select options
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Jane Smith')
    
    @patch('vermietung.signals.send_mail')
    def test_assign_user_via_modal(self, mock_send_mail):
        """Test assigning activity to new user via assignment button."""
        url = reverse('vermietung:aktivitaet_assign', kwargs={'pk': self.aktivitaet.pk})
        
        # Assign to assignee2
        response = self.client.post(url, {
            'assigned_user': self.assignee2.pk
        })
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Reload activity
        self.aktivitaet.refresh_from_db()
        
        # Check that assignment changed
        self.assertEqual(self.aktivitaet.assigned_user, self.assignee2)
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        
        # Check that it was called with correct template
        call_args = mock_send_mail.call_args
        self.assertEqual(call_args[1]['template_key'], 'activity-assigned')
        self.assertEqual(call_args[1]['to'], [self.assignee2.email])
    
    def test_assign_same_user_shows_info_message(self):
        """Test that assigning to same user shows info message."""
        url = reverse('vermietung:aktivitaet_assign', kwargs={'pk': self.aktivitaet.pk})
        
        # Assign to same user (assignee1)
        response = self.client.post(url, {
            'assigned_user': self.assignee1.pk
        }, follow=True)
        
        # Check that info message is shown
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('bereits', str(messages[0]))
    
    def test_assign_without_user_shows_error(self):
        """Test that assigning without selecting user shows error."""
        url = reverse('vermietung:aktivitaet_assign', kwargs={'pk': self.aktivitaet.pk})
        
        # POST without assigned_user
        response = self.client.post(url, {}, follow=True)
        
        # Check that error message is shown
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('wählen', str(messages[0]))


class ActivityEmailCCTest(TestCase):
    """Test CC functionality in activity email notifications."""
    
    def setUp(self):
        """Set up test data."""
        # Clear the test outbox
        mail.outbox = []
        
        # Create users with different emails
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123',
            first_name='Creator',
            last_name='User'
        )
        
        self.assignee = User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            password='pass123',
            first_name='Assignee',
            last_name='User'
        )
        
        self.same_user = User.objects.create_user(
            username='sameuser',
            email='same@example.com',
            password='pass123',
            first_name='Same',
            last_name='User'
        )
        
        # Create a standort
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Stadt',
            land='Deutschland'
        )
        
        # Create a MietObjekt for context
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            verfuegbar=True
        )
    
    @patch('vermietung.signals.send_mail')
    def test_assignment_email_includes_creator_in_cc(self, mock_send_mail):
        """Test that assignment email includes creator in CC when creator != assignee."""
        # Create activity with different creator and assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='Test description',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
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
    
    @patch('vermietung.signals.send_mail')
    def test_assignment_email_no_cc_when_creator_is_assignee(self, mock_send_mail):
        """Test that assignment email has no CC when creator == assignee."""
        # Create activity where creator is also the assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Self-Assigned Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.same_user,
            assigned_user=self.same_user
        )
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.same_user.email])
        
        # Verify CC is empty (no duplicate)
        self.assertEqual(call_args[1]['cc'], [])
    
    @patch('vermietung.signals.send_mail')
    def test_assignment_email_no_cc_when_creator_has_no_email(self, mock_send_mail):
        """Test that assignment email has no CC when creator has no email."""
        # Create user without email
        creator_no_email = User.objects.create_user(
            username='no_email_creator',
            email='',  # No email
            password='pass123'
        )
        
        # Create activity
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity without creator email',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=creator_no_email,
            assigned_user=self.assignee
        )
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient
        self.assertEqual(call_args[1]['to'], [self.assignee.email])
        
        # Verify CC is empty (creator has no email)
        self.assertEqual(call_args[1]['cc'], [])
    
    @patch('vermietung.signals.send_mail')
    def test_completed_email_includes_assignee_in_cc(self, mock_send_mail):
        """Test that completed email includes assignee in CC when assignee != creator."""
        # Create activity
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity to Complete',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=self.assignee
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        aktivitaet.status = 'ERLEDIGT'
        aktivitaet.save()
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # With new CC functionality, all recipients are in 'to' field (deduplicated)
        to_emails = call_args[1]['to']
        
        # Verify both creator and assignee are in recipients
        self.assertIn(self.creator.email, to_emails)
        self.assertIn(self.assignee.email, to_emails)
        
        # Verify no duplicates
        self.assertEqual(len(to_emails), len(set(to_emails)))
    
    @patch('vermietung.signals.send_mail')
    def test_completed_email_no_cc_when_assignee_is_creator(self, mock_send_mail):
        """Test that completed email has no CC when assignee == creator."""
        # Create activity where creator is also the assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Self-Completed Activity',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.same_user,
            assigned_user=self.same_user
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        aktivitaet.status = 'ERLEDIGT'
        aktivitaet.save()
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient (same user should only appear once)
        self.assertEqual(call_args[1]['to'], [self.same_user.email])
        
        # With new CC functionality, no separate cc field is used
        # All recipients are deduplicated in 'to' field
    
    @patch('vermietung.signals.send_mail')
    def test_completed_email_no_cc_when_no_assignee(self, mock_send_mail):
        """Test that completed email has no CC when there's no assignee."""
        # Create activity without assignee
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity without assignee',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=None
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        aktivitaet.status = 'ERLEDIGT'
        aktivitaet.save()
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient (only creator, no assignee)
        self.assertEqual(call_args[1]['to'], [self.creator.email])
        
        # With new CC functionality, no separate cc field is used
    
    @patch('vermietung.signals.send_mail')
    def test_completed_email_no_cc_when_assignee_has_no_email(self, mock_send_mail):
        """Test that completed email has no CC when assignee has no email."""
        # Create user without email
        assignee_no_email = User.objects.create_user(
            username='no_email_assignee',
            email='',  # No email
            password='pass123'
        )
        
        # Create activity
        aktivitaet = Aktivitaet.objects.create(
            titel='Activity with assignee without email',
            status='OFFEN',
            mietobjekt=self.mietobjekt,
            ersteller=self.creator,
            assigned_user=assignee_no_email
        )
        
        # Clear mock
        mock_send_mail.reset_mock()
        
        # Mark as completed
        aktivitaet.status = 'ERLEDIGT'
        aktivitaet.save()
        
        # Check that send_mail was called
        self.assertTrue(mock_send_mail.called)
        call_args = mock_send_mail.call_args
        
        # Verify To recipient (only creator, assignee has no email)
        self.assertEqual(call_args[1]['to'], [self.creator.email])
        
        # With new CC functionality, no separate cc field is used

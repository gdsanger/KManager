"""
Tests for Aktivitaet (Activity/Task) CRUD views and UI integration.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta
from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, Aktivitaet

User = get_user_model()


class AktivitaetViewTest(TestCase):
    """Tests for the Aktivitaet views."""
    
    def setUp(self):
        """Set up test data for all tests."""
        # Create a Mandant (required for ActivityStream)
        from core.models import Mandant
        self.mandant = Mandant.objects.create(
            name='Test Mandant',
            adresse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True  # Grant vermietung access
        )
        self.assigned_user = User.objects.create_user(
            username='assigneduser',
            password='testpass123',
            email='assigned@example.com',
            is_staff=True  # Grant vermietung access
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
        
        # Create addresses
        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Hauptstandort',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Hauptstadt',
            land='Deutschland'
        )
        
        self.kunde = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Max Mustermann',
            strasse='Musterstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland',
            email='max@example.com'
        )
        
        self.lieferant = Adresse.objects.create(
            adressen_type='LIEFERANT',
            name='Lieferant GmbH',
            strasse='Lieferstrasse 2',
            plz='54321',
            ort='Lieferstadt',
            land='Deutschland'
        )
        
        # Create a MietObjekt
        self.mietobjekt = MietObjekt.objects.create(
            name='Büro 1',
            type='RAUM',
            beschreibung='Kleines Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True
        )
        
        # Create a Vertrag
        self.vertrag = Vertrag.objects.create(
            mietobjekt=self.mietobjekt,
            mieter=self.kunde,
            start=date.today(),
            ende=date.today() + timedelta(days=365),
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
    
    def test_kanban_view_accessible(self):
        """Test that Kanban view is accessible."""
        response = self.client.get(reverse('vermietung:aktivitaet_kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/kanban.html')
    
    def test_list_view_accessible(self):
        """Test that list view is accessible."""
        response = self.client.get(reverse('vermietung:aktivitaet_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/list.html')
    
    def test_create_aktivitaet_from_vertrag(self):
        """Test creating an activity from a contract."""
        url = reverse('vermietung:aktivitaet_create_from_vertrag', args=[self.vertrag.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/form.html')
        
        # POST to create
        response = self.client.post(url, {
            'titel': 'Test Aktivität',
            'beschreibung': 'Test Beschreibung',
            'status': 'OFFEN',
            'prioritaet': 'HOCH',
            'faellig_am': (date.today() + timedelta(days=7)).isoformat(),
            'ersteller': self.user.pk,
        })
        
        # Should redirect to vertrag detail
        self.assertEqual(response.status_code, 302)
        
        # Check activity was created
        aktivitaet = Aktivitaet.objects.get(titel='Test Aktivität')
        self.assertEqual(aktivitaet.vertrag, self.vertrag)
        self.assertEqual(aktivitaet.status, 'OFFEN')
        self.assertEqual(aktivitaet.prioritaet, 'HOCH')
        self.assertEqual(aktivitaet.ersteller, self.user)
    
    def test_create_aktivitaet_from_mietobjekt(self):
        """Test creating an activity from a mietobjekt."""
        url = reverse('vermietung:aktivitaet_create_from_mietobjekt', args=[self.mietobjekt.pk])
        response = self.client.post(url, {
            'titel': 'Wartung',
            'beschreibung': 'Jährliche Wartung',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
            'ersteller': self.user.pk,
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check activity was created
        aktivitaet = Aktivitaet.objects.get(titel='Wartung')
        self.assertEqual(aktivitaet.mietobjekt, self.mietobjekt)
        self.assertEqual(aktivitaet.ersteller, self.user)
    
    def test_create_aktivitaet_from_kunde(self):
        """Test creating an activity from a customer."""
        url = reverse('vermietung:aktivitaet_create_from_kunde', args=[self.kunde.pk])
        response = self.client.post(url, {
            'titel': 'Kunde kontaktieren',
            'beschreibung': 'Vertragsverlängerung besprechen',
            'status': 'OFFEN',
            'prioritaet': 'HOCH',
            'ersteller': self.user.pk,
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check activity was created
        aktivitaet = Aktivitaet.objects.get(titel='Kunde kontaktieren')
        self.assertEqual(aktivitaet.kunde, self.kunde)
        self.assertEqual(aktivitaet.ersteller, self.user)
    
    def test_edit_aktivitaet(self):
        """Test editing an existing activity."""
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Original Title',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Update the activity - need to include hidden context fields
        response = self.client.post(url, {
            'titel': 'Updated Title',
            'beschreibung': 'Updated description',
            'status': 'IN_BEARBEITUNG',
            'prioritaet': 'HOCH',
            'vertrag': self.vertrag.pk,  # Hidden field
            'ersteller': self.user.pk,
        })
        
        # Should redirect after successful save
        if response.status_code != 302:
            # Print errors for debugging
            if hasattr(response, 'context') and 'form' in response.context:
                print(f"Form errors: {response.context['form'].errors}")
        
        self.assertEqual(response.status_code, 302)
        
        # Check changes were saved
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.titel, 'Updated Title')
        self.assertEqual(aktivitaet.status, 'IN_BEARBEITUNG')
        self.assertEqual(aktivitaet.prioritaet, 'HOCH')
    
    def test_delete_aktivitaet(self):
        """Test deleting an activity."""
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='To Delete',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_delete', args=[aktivitaet.pk])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 302)
        
        # Check activity was deleted
        self.assertFalse(Aktivitaet.objects.filter(pk=aktivitaet.pk).exists())
    
    def test_update_status_ajax(self):
        """Test quick status update for Kanban."""
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Test',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_update_status', args=[aktivitaet.pk])
        response = self.client.post(url, {'status': 'IN_BEARBEITUNG'})
        
        self.assertEqual(response.status_code, 200)
        
        # Check status was updated
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.status, 'IN_BEARBEITUNG')
    
    def test_aktivitaeten_shown_in_vertrag_detail(self):
        """Test that activities are shown in contract detail view."""
        # Create an activity for the contract
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Vertrag Aktivität',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='HOCH'
        )
        
        url = reverse('vermietung:vertrag_detail', args=[self.vertrag.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vertrag Aktivität')
        self.assertIn('aktivitaeten_page_obj', response.context)
    
    def test_aktivitaeten_shown_in_mietobjekt_detail(self):
        """Test that activities are shown in mietobjekt detail view."""
        # Create an activity for the mietobjekt
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Mietobjekt Aktivität',
            mietobjekt=self.mietobjekt,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:mietobjekt_detail', args=[self.mietobjekt.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mietobjekt Aktivität')
        self.assertIn('aktivitaeten_page_obj', response.context)
    
    def test_aktivitaeten_shown_in_kunde_detail(self):
        """Test that activities are shown in customer detail view."""
        # Create an activity for the customer
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Kunden Aktivität',
            kunde=self.kunde,
            status='OFFEN',
            prioritaet='HOCH'
        )
        
        url = reverse('vermietung:kunde_detail', args=[self.kunde.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kunden Aktivität')
        self.assertIn('aktivitaeten_page_obj', response.context)
    
    def test_kanban_groups_by_status(self):
        """Test that Kanban view properly groups activities by status."""
        # Create activities with different statuses, assigned to self.user
        # so they show up in the default 'responsible' filter
        Aktivitaet.objects.create(
            ersteller=self.user,
            assigned_user=self.user,  # Assign to user so it shows in default filter
            titel='Offen 1',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        Aktivitaet.objects.create(
            ersteller=self.user,
            assigned_user=self.user,  # Assign to user so it shows in default filter
            titel='In Bearbeitung 1',
            vertrag=self.vertrag,
            status='IN_BEARBEITUNG',
            prioritaet='NORMAL'
        )
        Aktivitaet.objects.create(
            ersteller=self.user,
            assigned_user=self.user,  # Assign to user so it shows in default filter
            titel='Erledigt 1',
            vertrag=self.vertrag,
            status='ERLEDIGT',
            prioritaet='NORMAL'
        )
        
        response = self.client.get(reverse('vermietung:aktivitaet_kanban'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['aktivitaeten_offen'].count(), 1)
        self.assertEqual(response.context['aktivitaeten_in_bearbeitung'].count(), 1)
        self.assertEqual(response.context['aktivitaeten_erledigt'].count(), 1)
    
    def test_assignment_to_user(self):
        """Test assigning an activity to a user."""
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Assign Test',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk])
        response = self.client.post(url, {
            'titel': 'Assign Test',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
            'assigned_user': self.assigned_user.pk,
            'vertrag': self.vertrag.pk,  # Hidden field
            'ersteller': self.user.pk,
        })
        
        # Should redirect after successful save
        if response.status_code != 302:
            # Print errors for debugging
            if hasattr(response, 'context') and 'form' in response.context:
                print(f"Form errors: {response.context['form'].errors}")
        
        self.assertEqual(response.status_code, 302)
        
        # Check assignment was saved
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.assigned_user, self.assigned_user)
    
    def test_assigned_activities_list(self):
        """Test the list of activities assigned to current user."""
        # Create activities assigned to test user
        Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Assigned to me',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='HOCH',
            assigned_user=self.user
        )
        
        # Create activity assigned to different user
        Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Assigned to someone else',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL',
            assigned_user=self.assigned_user
        )
        
        # Create unassigned activity
        Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Unassigned',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_assigned_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/list.html')
        
        # Only the activity assigned to the current user should be shown
        self.assertContains(response, 'Assigned to me')
        self.assertNotContains(response, 'Assigned to someone else')
        self.assertNotContains(response, 'Unassigned')
    
    def test_created_activities_list(self):
        """Test the list of activities created by current user."""
        # Create activities created by test user
        Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Created by me',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='HOCH'
        )
        
        # Create activity created by different user
        Aktivitaet.objects.create(
            ersteller=self.assigned_user,
            titel='Created by someone else',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL'
        )
        
        url = reverse('vermietung:aktivitaet_created_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'vermietung/aktivitaeten/list.html')
        
        # Only the activity created by the current user should be shown
        self.assertContains(response, 'Created by me')
        self.assertNotContains(response, 'Created by someone else')
    
    def test_series_activity_creation(self):
        """Test creating a series activity with intervall."""
        url = reverse('vermietung:aktivitaet_create_from_vertrag', args=[self.vertrag.pk])
        
        response = self.client.post(url, {
            'titel': 'Monthly Inspection',
            'beschreibung': 'Regular monthly inspection',
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
            'faellig_am': (date.today() + timedelta(days=30)).isoformat(),
            'ersteller': self.user.pk,
            'ist_serie': True,
            'intervall_monate': 1,
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check series activity was created with correct fields
        aktivitaet = Aktivitaet.objects.get(titel='Monthly Inspection')
        self.assertTrue(aktivitaet.ist_serie)
        self.assertEqual(aktivitaet.intervall_monate, 1)
        self.assertIsNotNone(aktivitaet.faellig_am)
    
    def test_series_activity_auto_create_next(self):
        """Test that completing a series activity creates the next one."""
        # Create a series activity
        series_aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Monthly Check',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=date.today(),
            ist_serie=True,
            intervall_monate=1
        )
        
        original_id = series_aktivitaet.pk
        
        # Mark it as ERLEDIGT
        series_aktivitaet.status = 'ERLEDIGT'
        series_aktivitaet.save()
        
        # Check that a new activity was created
        new_activities = Aktivitaet.objects.filter(
            titel='Monthly Check',
            status='OFFEN'
        ).exclude(pk=original_id)
        
        self.assertEqual(new_activities.count(), 1)
        
        new_aktivitaet = new_activities.first()
        self.assertTrue(new_aktivitaet.ist_serie)
        self.assertEqual(new_aktivitaet.intervall_monate, 1)
        self.assertEqual(new_aktivitaet.vertrag, self.vertrag)
        self.assertEqual(new_aktivitaet.ersteller, self.user)
        
        # Check that due date was incremented by 1 month
        from dateutil.relativedelta import relativedelta
        expected_date = date.today() + relativedelta(months=1)
        self.assertEqual(new_aktivitaet.faellig_am, expected_date)
        
        # Check that serien_id is the same
        self.assertEqual(new_aktivitaet.serien_id, series_aktivitaet.serien_id)
    
    def test_edit_view_shows_date_field_values(self):
        """Test that date fields are properly pre-filled in edit view."""
        # Create an activity with a due date
        due_date = date.today() + timedelta(days=14)
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Activity with Date',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=due_date
        )
        
        # Get the edit view
        url = reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the form has the correct initial value for faellig_am
        form = response.context['form']
        self.assertEqual(form.initial.get('faellig_am') or form.instance.faellig_am, due_date)
        
        # Check that the rendered HTML contains the date in ISO format (YYYY-MM-DD)
        # The HTML5 date input should have value="YYYY-MM-DD"
        expected_date_str = due_date.strftime('%Y-%m-%d')
        self.assertContains(response, f'value="{expected_date_str}"')
    
    def test_edit_view_preserves_date_when_not_changed(self):
        """Test that saving without changing date preserves the original date."""
        # Create an activity with a due date
        due_date = date.today() + timedelta(days=21)
        aktivitaet = Aktivitaet.objects.create(
            ersteller=self.user,
            titel='Date Preservation Test',
            vertrag=self.vertrag,
            status='OFFEN',
            prioritaet='NORMAL',
            faellig_am=due_date
        )
        
        # Edit the activity but don't change the date
        url = reverse('vermietung:aktivitaet_edit', args=[aktivitaet.pk])
        response = self.client.post(url, {
            'titel': 'Date Preservation Test - Updated',
            'status': 'IN_BEARBEITUNG',
            'prioritaet': 'NORMAL',
            'faellig_am': due_date.strftime('%Y-%m-%d'),  # Send date in ISO format
            'vertrag': self.vertrag.pk,
            'ersteller': self.user.pk,
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Check that date was preserved
        aktivitaet.refresh_from_db()
        self.assertEqual(aktivitaet.faellig_am, due_date)
        self.assertEqual(aktivitaet.titel, 'Date Preservation Test - Updated')

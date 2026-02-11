"""
Tests for Kanban empty column drop functionality.

Tests verify that empty columns have the necessary CSS to be droppable.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from vermietung.models import Aktivitaet

User = get_user_model()


class KanbanEmptyColumnDropTest(TestCase):
    """Tests for empty Kanban column drop zone CSS."""
    
    def setUp(self):
        """Set up test data."""
        # Create a Mandant (required for ActivityStream)
        from core.models import Mandant
        self.mandant = Mandant.objects.create(
            name='Test Mandant',
            adresse='Test Str. 1',
            plz='12345',
            ort='Teststadt',
            land='Deutschland'
        )
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
            is_staff=True  # Grant vermietung access
        )
        
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_kanban_cards_have_min_height_css(self):
        """Test that .kanban-cards elements have min-height CSS for drop zones."""
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the CSS includes min-height for .kanban-cards
        self.assertContains(response, '.kanban-cards')
        self.assertContains(response, 'min-height:')
        
    def test_kanban_cards_have_flex_grow_css(self):
        """Test that .kanban-cards elements have flex-grow CSS to fill columns."""
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the CSS includes flex-grow for .kanban-cards
        self.assertContains(response, '.kanban-cards')
        self.assertContains(response, 'flex-grow:')
        
    def test_kanban_empty_state_has_pointer_events_none(self):
        """Test that empty state text has pointer-events: none to allow drops."""
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the CSS includes pointer-events: none for empty state
        self.assertContains(response, 'pointer-events:')
        self.assertContains(response, '.kanban-cards .text-muted')
    
    def test_empty_columns_render_with_kanban_cards_class(self):
        """Test that empty columns still have .kanban-cards container."""
        # Don't create any activities - all columns should be empty
        
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that all columns have .kanban-cards containers
        # There should be 4 columns: OFFEN, IN_BEARBEITUNG, ERLEDIGT, ABGEBROCHEN
        content = response.content.decode('utf-8')
        self.assertEqual(content.count('class="kanban-cards"'), 4)
        
        # Check that empty state messages are rendered
        self.assertContains(response, 'Keine offenen Aktivitäten')
        self.assertContains(response, 'Keine Aktivitäten in Bearbeitung')
        self.assertContains(response, 'Keine erledigten Aktivitäten')
        self.assertContains(response, 'Keine abgebrochenen Aktivitäten')
    
    def test_kanban_column_has_flex_display(self):
        """Test that .kanban-column has flexbox display to support child growth."""
        # Get Kanban view
        url = reverse('vermietung:aktivitaet_kanban')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check that the CSS includes flex display for .kanban-column
        self.assertContains(response, '.kanban-column')
        content = response.content.decode('utf-8')
        
        # Check for flex-related CSS in .kanban-column
        # Find the .kanban-column style block
        kanban_column_start = content.find('.kanban-column {')
        kanban_column_end = content.find('}', kanban_column_start)
        kanban_column_css = content[kanban_column_start:kanban_column_end]
        
        self.assertIn('display:', kanban_column_css)
        self.assertIn('flex', kanban_column_css)

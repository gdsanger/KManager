"""
Tests for AI Core Service
"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from core.models import AIProvider, AIModel, AIJobsHistory
from core.services.ai import AIRouter
from core.services.ai.pricing import calculate_cost
from core.services.ai.schemas import AIResponse, ProviderResponse
from core.services.base import ServiceNotConfigured


class PricingTestCase(TestCase):
    """Test cost calculation functionality"""
    
    def test_calculate_cost_with_tokens(self):
        """Test cost calculation with valid token counts"""
        cost = calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            input_price_per_1m=Decimal('10.00'),
            output_price_per_1m=Decimal('30.00')
        )
        
        # (1000/1000000 * 10) + (500/1000000 * 30) = 0.01 + 0.015 = 0.025
        self.assertEqual(cost, Decimal('0.025000'))
    
    def test_calculate_cost_zero_tokens(self):
        """Test cost calculation with zero tokens"""
        cost = calculate_cost(
            input_tokens=0,
            output_tokens=0,
            input_price_per_1m=Decimal('10.00'),
            output_price_per_1m=Decimal('30.00')
        )
        
        self.assertEqual(cost, Decimal('0.000000'))
    
    def test_calculate_cost_no_tokens(self):
        """Test cost calculation when tokens are None"""
        cost = calculate_cost(
            input_tokens=None,
            output_tokens=500,
            input_price_per_1m=Decimal('10.00'),
            output_price_per_1m=Decimal('30.00')
        )
        
        self.assertIsNone(cost)
    
    def test_calculate_cost_large_numbers(self):
        """Test cost calculation with large token counts"""
        cost = calculate_cost(
            input_tokens=1_500_000,
            output_tokens=800_000,
            input_price_per_1m=Decimal('5.00'),
            output_price_per_1m=Decimal('15.00')
        )
        
        # (1500000/1000000 * 5) + (800000/1000000 * 15) = 7.5 + 12 = 19.5
        self.assertEqual(cost, Decimal('19.500000'))


class AIModelSelectionTestCase(TestCase):
    """Test model selection logic in AIRouter"""
    
    def setUp(self):
        """Create test providers and models"""
        self.openai_provider = AIProvider.objects.create(
            name="Test OpenAI",
            provider_type="OpenAI",
            api_key="sk-test-key",
            is_active=True
        )
        
        self.gemini_provider = AIProvider.objects.create(
            name="Test Gemini",
            provider_type="Gemini",
            api_key="test-gemini-key",
            is_active=True
        )
        
        self.openai_model = AIModel.objects.create(
            provider=self.openai_provider,
            name="GPT-3.5 Turbo",
            model_id="gpt-3.5-turbo",
            input_price_per_1m_tokens=Decimal('0.50'),
            output_price_per_1m_tokens=Decimal('1.50'),
            is_active=True
        )
        
        self.gemini_model = AIModel.objects.create(
            provider=self.gemini_provider,
            name="Gemini Pro",
            model_id="gemini-pro",
            input_price_per_1m_tokens=Decimal('0.25'),
            output_price_per_1m_tokens=Decimal('0.50'),
            is_active=True
        )
        
        self.router = AIRouter()
    
    def test_select_default_model(self):
        """Test default model selection (should prefer OpenAI)"""
        provider, model = self.router._select_model()
        
        self.assertEqual(provider.provider_type, "OpenAI")
        self.assertEqual(model.model_id, "gpt-3.5-turbo")
    
    def test_select_by_provider_type(self):
        """Test model selection by provider type only"""
        provider, model = self.router._select_model(provider_type="Gemini")
        
        self.assertEqual(provider.provider_type, "Gemini")
        self.assertEqual(model.model_id, "gemini-pro")
    
    def test_select_by_provider_and_model(self):
        """Test explicit provider and model selection"""
        provider, model = self.router._select_model(
            provider_type="OpenAI",
            model_id="gpt-3.5-turbo"
        )
        
        self.assertEqual(provider.provider_type, "OpenAI")
        self.assertEqual(model.model_id, "gpt-3.5-turbo")
    
    def test_select_inactive_provider_fails(self):
        """Test that inactive providers are not selected"""
        self.openai_provider.is_active = False
        self.openai_provider.save()
        
        # Should fall back to Gemini
        provider, model = self.router._select_model()
        self.assertEqual(provider.provider_type, "Gemini")
    
    def test_select_no_active_model_fails(self):
        """Test error when no active models exist"""
        AIModel.objects.all().update(is_active=False)
        
        with self.assertRaises(ServiceNotConfigured) as cm:
            self.router._select_model()
        
        self.assertIn("No active AI model configured", str(cm.exception))
    
    def test_select_nonexistent_provider_fails(self):
        """Test error for nonexistent provider"""
        with self.assertRaises(ServiceNotConfigured) as cm:
            self.router._select_model(provider_type="Claude")
        
        self.assertIn("Provider 'Claude' not found", str(cm.exception))


class AIRouterTestCase(TestCase):
    """Test AIRouter functionality"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.provider = AIProvider.objects.create(
            name="Test OpenAI",
            provider_type="OpenAI",
            api_key="sk-test-key",
            is_active=True
        )
        
        self.model = AIModel.objects.create(
            provider=self.provider,
            name="GPT-3.5 Turbo",
            model_id="gpt-3.5-turbo",
            input_price_per_1m_tokens=Decimal('0.50'),
            output_price_per_1m_tokens=Decimal('1.50'),
            is_active=True
        )
        
        self.router = AIRouter()
    
    @patch('openai.OpenAI')
    def test_chat_success(self, mock_openai_class):
        """Test successful chat request"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Make request
        response = self.router.chat(
            messages=[{"role": "user", "content": "Hello"}],
            user=self.user,
            client_ip="127.0.0.1",
            agent="test_agent"
        )
        
        # Verify response
        self.assertEqual(response.text, "Hello! How can I help you?")
        self.assertEqual(response.input_tokens, 10)
        self.assertEqual(response.output_tokens, 8)
        self.assertEqual(response.provider, "OpenAI")
        self.assertEqual(response.model, "gpt-3.5-turbo")
        
        # Verify job history was created
        job = AIJobsHistory.objects.latest('timestamp')
        self.assertEqual(job.status, 'Completed')
        self.assertEqual(job.agent, 'test_agent')
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.provider, self.provider)
        self.assertEqual(job.model, self.model)
        self.assertEqual(job.input_tokens, 10)
        self.assertEqual(job.output_tokens, 8)
        self.assertIsNotNone(job.costs)
        self.assertIsNotNone(job.duration_ms)
    
    @patch('openai.OpenAI')
    def test_chat_error_handling(self, mock_openai_class):
        """Test error handling in chat request"""
        # Mock OpenAI to raise an error
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client
        
        # Make request
        with self.assertRaises(Exception) as cm:
            self.router.chat(
                messages=[{"role": "user", "content": "Hello"}],
                agent="test_agent"
            )
        
        self.assertIn("API Error", str(cm.exception))
        
        # Verify job history was created with error status
        job = AIJobsHistory.objects.latest('timestamp')
        self.assertEqual(job.status, 'Error')
        self.assertEqual(job.agent, 'test_agent')
        self.assertIn("API Error", job.error_message)
        self.assertIsNotNone(job.duration_ms)
    
    @patch('openai.OpenAI')
    def test_generate_shortcut(self, mock_openai_class):
        """Test generate() shortcut method"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a haiku"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 4
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Make request
        response = self.router.generate(
            prompt="Write a haiku",
            agent="test_agent"
        )
        
        # Verify response
        self.assertEqual(response.text, "This is a haiku")
        
        # Verify OpenAI was called with correct message format
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertEqual(messages[0]['content'], 'Write a haiku')
    
    @patch('openai.OpenAI')
    def test_chat_with_parameters(self, mock_openai_class):
        """Test chat with temperature and max_tokens"""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 2
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        # Make request with parameters
        response = self.router.chat(
            messages=[{"role": "user", "content": "Test"}],
            temperature=0.7,
            max_tokens=100
        )
        
        # Verify parameters were passed to OpenAI
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args[1]['temperature'], 0.7)
        self.assertEqual(call_args[1]['max_tokens'], 100)


class AIJobsHistoryTestCase(TestCase):
    """Test AIJobsHistory model and admin"""
    
    def setUp(self):
        """Create test data"""
        self.user = User.objects.create_user(username='testuser')
        
        self.provider = AIProvider.objects.create(
            name="Test Provider",
            provider_type="OpenAI",
            api_key="test-key",
            is_active=True
        )
        
        self.model = AIModel.objects.create(
            provider=self.provider,
            name="Test Model",
            model_id="test-model",
            input_price_per_1m_tokens=Decimal('1.00'),
            output_price_per_1m_tokens=Decimal('2.00'),
            is_active=True
        )
    
    def test_create_job_history(self):
        """Test creating job history record"""
        job = AIJobsHistory.objects.create(
            agent="test_agent",
            user=self.user,
            provider=self.provider,
            model=self.model,
            status='Completed',
            client_ip='127.0.0.1',
            input_tokens=1000,
            output_tokens=500,
            costs=Decimal('0.025'),
            duration_ms=1500
        )
        
        self.assertEqual(job.agent, 'test_agent')
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.status, 'Completed')
        self.assertIsNotNone(job.timestamp)
    
    def test_job_history_without_tokens(self):
        """Test job history can be created without token counts"""
        job = AIJobsHistory.objects.create(
            agent="test_agent",
            provider=self.provider,
            model=self.model,
            status='Completed',
            input_tokens=None,
            output_tokens=None,
            costs=None
        )
        
        self.assertIsNone(job.input_tokens)
        self.assertIsNone(job.output_tokens)
        self.assertIsNone(job.costs)


class AIAdminTestCase(TestCase):
    """Test AI admin configurations"""
    
    def test_provider_admin_registered(self):
        """Test that AIProvider is registered in admin"""
        from django.contrib import admin
        from core.models import AIProvider
        
        self.assertTrue(admin.site.is_registered(AIProvider))
    
    def test_model_admin_registered(self):
        """Test that AIModel is registered in admin"""
        from django.contrib import admin
        from core.models import AIModel
        
        self.assertTrue(admin.site.is_registered(AIModel))
    
    def test_jobs_history_admin_registered(self):
        """Test that AIJobsHistory is registered in admin"""
        from django.contrib import admin
        from core.models import AIJobsHistory
        
        self.assertTrue(admin.site.is_registered(AIJobsHistory))

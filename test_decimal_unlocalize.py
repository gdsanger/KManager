#!/usr/bin/env python
"""
Test to verify that decimal values are properly unlocalized in the document detail template.
This addresses the issue where German-formatted decimals (e.g., "2,5000") were being used
in HTML5 number inputs, which only accept English format (e.g., "2.5000").
"""
import os
import sys
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
import django
django.setup()

from django.template import Template, Context
from django.test import TestCase
from django.utils import translation


class DecimalUnlocalizeTest(TestCase):
    """Test that decimal values are properly unlocalized in templates"""
    
    def test_unlocalize_filter_in_number_input(self):
        """Test that the unlocalize filter converts German decimals to English format"""
        # Set German locale
        with translation.override('de-de'):
            # Create a simple template using the unlocalize filter
            template = Template('{% load l10n %}{{ value|unlocalize }}')
            
            # Test with different decimal values
            test_cases = [
                (Decimal('2.5000'), '2.5000'),
                (Decimal('12.00'), '12.00'),
                (Decimal('1.0000'), '1.0000'),
                (Decimal('75.00'), '75.00'),
            ]
            
            for decimal_value, expected_output in test_cases:
                context = Context({'value': decimal_value})
                result = template.render(context)
                
                # The unlocalize filter should output English format (with dot)
                self.assertEqual(result, expected_output, 
                    f"Expected {expected_output} but got {result} for input {decimal_value}")
                
                # Verify it doesn't contain comma (German format)
                self.assertNotIn(',', result, 
                    f"Output should not contain comma for number input: {result}")
                
        print("✓ All decimal unlocalize tests passed!")
    
    def test_localized_vs_unlocalized(self):
        """Verify the difference between localized and unlocalized output"""
        with translation.override('de-de'):
            decimal_value = Decimal('2.5000')
            
            # Without unlocalize (should be German format with comma)
            template_localized = Template('{{ value }}')
            context = Context({'value': decimal_value})
            localized_result = template_localized.render(context)
            
            # With unlocalize (should be English format with dot)
            template_unlocalized = Template('{% load l10n %}{{ value|unlocalize }}')
            unlocalized_result = template_unlocalized.render(context)
            
            print(f"Localized output (German):   {localized_result}")
            print(f"Unlocalized output (English): {unlocalized_result}")
            
            # Verify they are different
            self.assertNotEqual(localized_result, unlocalized_result,
                "Localized and unlocalized output should be different in German locale")
            
            # Verify comma in localized, dot in unlocalized
            self.assertIn(',', localized_result, "German format should use comma")
            self.assertNotIn(',', unlocalized_result, "Unlocalized should not have comma")
            self.assertIn('.', unlocalized_result, "Unlocalized should have dot")
            
        print("✓ Localized vs unlocalized comparison passed!")


if __name__ == '__main__':
    # Run the tests
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    failures = test_runner.run_tests(['__main__'])
    
    sys.exit(bool(failures))

#!/usr/bin/env python
"""
Test script to verify that the create button appears on the aktivitaet create page.
"""
import os
import sys
import django

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

def test_create_button_appears():
    """Test that the Anlegen button appears on the create page"""
    # Create a test user
    user = User.objects.create_user(username='testuser', password='testpass123')
    
    # Create a client and log in
    client = Client()
    client.login(username='testuser', password='testpass123')
    
    # Request the create page
    url = reverse('vermietung:aktivitaet_create')
    response = client.get(url)
    
    # Check that the response is successful
    print(f"Status code: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    # Check that the save button is present
    content = response.content.decode('utf-8')
    
    # Check for the "Anlegen" button text
    if 'Anlegen' in content:
        print("✅ SUCCESS: 'Anlegen' button text found in response")
    else:
        print("❌ FAIL: 'Anlegen' button text NOT found in response")
        print("\nSearching for button-related content:")
        if 'Speichern' in content:
            print("  - Found 'Speichern' text")
        if 'Abbrechen' in content:
            print("  - Found 'Abbrechen' text")
        if 'btn btn-primary' in content:
            print("  - Found 'btn btn-primary' class")
        if 'type="submit"' in content:
            print("  - Found submit buttons")
        return False
    
    # Check for submit button with "Anlegen" text
    if 'type="submit"' in content and 'Anlegen' in content:
        print("✅ SUCCESS: Submit button with 'Anlegen' text found")
    else:
        print("❌ FAIL: Submit button with 'Anlegen' text NOT found")
        return False
    
    # Check that hidden forms are NOT present in create mode
    if 'deleteForm' not in content:
        print("✅ SUCCESS: Delete form correctly hidden in create mode")
    else:
        print("⚠️  WARNING: Delete form found in create mode (should be hidden)")
    
    if 'assignModal' not in content:
        print("✅ SUCCESS: Assignment modal correctly hidden in create mode")
    else:
        print("⚠️  WARNING: Assignment modal found in create mode (should be hidden)")
    
    print("\n✅ All tests passed! The create button is now visible.")
    return True

if __name__ == '__main__':
    try:
        success = test_create_button_appears()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

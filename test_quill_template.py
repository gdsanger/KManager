"""
Simple test to validate item_edit_form.html template rendering
"""
import os
import sys
import django

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_server_settings')
django.setup()

from django.template.loader import render_to_string
from django.test import RequestFactory
from core.forms import ItemForm
from core.models import Item, TaxRate, Kostenart
from decimal import Decimal

def test_template_rendering():
    """Test that the item_edit_form template renders correctly with Quill"""
    
    # Create required dependencies
    tax_rate, _ = TaxRate.objects.get_or_create(
        code='VAT19',
        defaults={
            'name': 'Standard VAT',
            'rate': Decimal('19.00')
        }
    )
    
    kostenart, _ = Kostenart.objects.get_or_create(
        name='Test Kostenart',
        defaults={'parent': None}
    )
    
    # Create or get a test item with HTML content in long_text
    item, created = Item.objects.update_or_create(
        article_no='TEST001',
        defaults={
            'short_text_1': 'Test Artikel',
            'short_text_2': 'Zusätzlicher Text',
            'long_text': '<p>Dies ist ein <strong>Test Langtext</strong> mit <em>HTML Formatierung</em>.</p><ul><li>Punkt 1</li><li>Punkt 2</li></ul>',
            'net_price': Decimal('100.00'),
            'purchase_price': Decimal('50.00'),
            'tax_rate': tax_rate,
            'cost_type_1': kostenart,
            'item_type': 'MATERIAL',
            'is_active': True,
            'is_discountable': True
        }
    )
    
    print(f"Item {'created' if created else 'updated'}: {item.article_no}")
    print(f"Long text content: {item.long_text}")
    
    # Create a form instance
    form = ItemForm(instance=item)
    
    # Render template
    html = render_to_string('core/item_edit_form.html', {
        'form': form,
        'item': item
    })
    
    # Verify key elements are present
    assert 'longTextEditor' in html, "Quill editor container not found"
    assert 'quill.snow.css' in html, "Quill CSS not loaded"
    assert 'quill.js' in html, "Quill JS not loaded"
    assert 'new Quill' in html, "Quill initialization not found"
    assert item.long_text in html, "Long text content not in template"
    
    print("\n✓ Template renders correctly with Quill Editor")
    print("✓ Quill CSS is included")
    print("✓ Quill JS is included")
    print("✓ Quill editor initialization is present")
    print("✓ Long text content is preserved")
    
    # Save the HTML for inspection
    with open('/tmp/item_edit_form_rendered.html', 'w') as f:
        f.write(html)
    print("\n✓ Rendered HTML saved to /tmp/item_edit_form_rendered.html")
    
    return True

if __name__ == '__main__':
    try:
        test_template_rendering()
        print("\n✓✓✓ All tests passed! ✓✓✓")
    except Exception as e:
        print(f"\n✗✗✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python
"""
Demo script for Core Printing Framework

Generates an example PDF to demonstrate the framework's capabilities.
"""

import os
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kmanager.settings')
import django
django.setup()

from core.printing import PdfRenderService

def main():
    """Generate example PDF."""
    print("=" * 60)
    print("Core Printing Framework Demo")
    print("=" * 60)
    print()
    
    # Initialize service
    service = PdfRenderService()
    print("✓ PdfRenderService initialized")
    
    # Prepare context
    context = {
        'title': 'Demo Document',
        'company_name': 'KManager Demo GmbH',
    }
    print("✓ Context prepared")
    
    # Get base_url for static assets
    from core.printing import get_static_base_url
    base_url = get_static_base_url()
    print(f"✓ Base URL: {base_url}")
    
    # Render PDF
    print()
    print("Rendering PDF...")
    result = service.render(
        template_name='printing/example.html',
        context=context,
        base_url=base_url,
        filename='example-document.pdf'
    )
    print(f"✓ PDF rendered successfully ({len(result.pdf_bytes)} bytes)")
    
    # Save to file
    output_dir = project_root / 'tmp'
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / result.filename
    
    with open(output_path, 'wb') as f:
        f.write(result.pdf_bytes)
    
    print(f"✓ PDF saved to: {output_path}")
    print()
    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)
    print()
    print(f"You can open the PDF with: xdg-open {output_path}")
    print(f"Or manually at: {output_path}")

if __name__ == '__main__':
    main()

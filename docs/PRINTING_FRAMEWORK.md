# Core Printing Framework Documentation

## Overview

The Core Printing Framework provides a modular, extensible system for generating PDF documents from HTML templates using WeasyPrint. It's designed to be used by all modules (e.g., `auftragsverwaltung`, `vermietung`) for consistent PDF generation.

## Architecture

### Components

1. **Interfaces** (`core/printing/interfaces.py`)
   - `IPdfRenderer`: Contract for PDF rendering engines
   - `IContextBuilder`: Contract for building template contexts (placeholder for module implementations)

2. **WeasyPrint Renderer** (`core/printing/weasyprint_renderer.py`)
   - Infrastructure adapter for WeasyPrint engine
   - Supports CSS Paged Media, static assets, fonts

3. **PDF Render Service** (`core/printing/service.py`)
   - Main service orchestrating the rendering pipeline
   - Template loading → HTML rendering → PDF generation

4. **DTO** (`core/printing/dto.py`)
   - `PdfResult`: Encapsulates PDF bytes and metadata

5. **Sanitizer** (`core/printing/sanitizer.py`)
   - Optional HTML sanitization layer (bleach-based)

6. **Base Template** (`core/templates/printing/base.html`)
   - Foundation template for PDF documents
   - Includes print CSS, defines content blocks

7. **Print CSS** (`core/static/printing/print.css`)
   - CSS Paged Media rules (@page)
   - Running headers/footers
   - Page counters (Seite X von Y)

## Usage

### Basic Example

```python
from core.printing import PdfRenderService

# Initialize service (uses default WeasyPrint renderer)
service = PdfRenderService()

# Prepare context for template
context = {
    'title': 'Invoice #12345',
    'customer_name': 'Max Mustermann',
    'items': [...],
}

# Render PDF
result = service.render(
    template_name='auftragsverwaltung/invoice.html',
    context=context,
    base_url='file:///path/to/static/',  # For resolving CSS, images
    filename='invoice-12345.pdf'
)

# Access PDF bytes
pdf_bytes = result.pdf_bytes
filename = result.filename
content_type = result.content_type  # 'application/pdf'
```

### Creating Document-Specific Templates

Create templates that extend the base template:

```html
{# auftragsverwaltung/templates/auftragsverwaltung/invoice.html #}
{% extends "printing/base.html" %}

{% block title %}Invoice {{ document.number }}{% endblock %}

{% block first_page_header %}
<div class="header">
    <img src="/static/images/logo.png" alt="Company Logo">
    <h1>RECHNUNG</h1>
</div>
{% endblock %}

{% block content %}
<div class="invoice-header">
    <p><strong>Rechnungsnummer:</strong> {{ document.number }}</p>
    <p><strong>Datum:</strong> {{ document.date }}</p>
</div>

<table>
    <thead>
        <tr>
            <th>Pos.</th>
            <th>Beschreibung</th>
            <th class="numeric">Menge</th>
            <th class="numeric">Preis</th>
            <th class="numeric">Gesamt</th>
        </tr>
    </thead>
    <tbody>
        {% for item in items %}
        <tr>
            <td>{{ item.position }}</td>
            <td>{{ item.description }}</td>
            <td class="numeric">{{ item.quantity }}</td>
            <td class="numeric">{{ item.price }}</td>
            <td class="numeric">{{ item.total }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### Context Builders (Module Implementation)

Modules should implement `IContextBuilder` for their domain objects:

```python
from core.printing.interfaces import IContextBuilder

class InvoiceContextBuilder(IContextBuilder):
    """Build context for invoice documents."""
    
    def build_context(self, obj, *, company=None):
        """Build template context from SalesDocument."""
        return {
            'document': obj,
            'items': obj.lines.all(),
            'company': company or obj.company,
            'total': obj.calculate_total(),
        }
    
    def get_template_name(self, obj):
        """Get template based on document type."""
        if obj.doc_type.code == 'INVOICE':
            return 'auftragsverwaltung/invoice.html'
        elif obj.doc_type.code == 'QUOTE':
            return 'auftragsverwaltung/quote.html'
        return 'auftragsverwaltung/document.html'
```

## CSS Paged Media Features

### Page Setup

The base print.css defines:
- A4 page size
- Standard margins (2.5cm top, 2cm right/left, 3cm bottom)
- First page with extra top margin (3.5cm for letterhead)
- Different margins for left/right pages (double-sided printing)

### Running Footer

Default footer appears on all pages:
```
Seite 1 von 3
```

### Page Breaks

Control page breaks with CSS classes:
```html
<div class="keep-together">Content that shouldn't break</div>
<h2>Section Title</h2>  <!-- Headers avoid break after -->
<div class="page-break-before">Starts on new page</div>
```

### Table Headers

Table headers repeat on each page automatically:
```html
<table>
    <thead>
        <tr><th>Header</th></tr>
    </thead>
    <tbody>
        <!-- Many rows... -->
    </tbody>
</table>
```

## Configuration

### Default Renderer

Currently, WeasyPrint is the default renderer. In the future, you can configure via settings:

```python
# settings.py (future)
PDF_RENDERER = 'weasyprint'  # or 'other_renderer'
```

### Custom Renderer

You can inject a custom renderer:

```python
from core.printing import PdfRenderService
from my_module.renderers import MyCustomRenderer

service = PdfRenderService(renderer=MyCustomRenderer())
result = service.render(...)
```

## Static Assets

WeasyPrint needs a `base_url` to resolve relative paths for:
- CSS files
- Images (logos, etc.)
- Fonts

In development:
```python
base_url = 'file:///path/to/project/static/'
```

In production (after `collectstatic`):
```python
from django.conf import settings
base_url = f'file://{settings.STATIC_ROOT}/'
```

## HTML Sanitization

Optional second layer of protection (Quill content is already sanitized on save):

```python
result = service.render(
    template_name='...',
    context={...},
    base_url='...',
    sanitize=True  # Enable HTML sanitization
)
```

## Error Handling

```python
from core.printing.service import TemplateNotFoundError, RenderError

try:
    result = service.render(...)
except TemplateNotFoundError as e:
    # Template doesn't exist
    logger.error(f"Template not found: {e}")
except RenderError as e:
    # PDF rendering failed
    logger.error(f"Rendering failed: {e}")
```

## Testing

See `core/test_printing.py` for examples:

```python
from django.test import TestCase
from core.printing import PdfRenderService, PdfResult

class MyDocumentTest(TestCase):
    def test_generate_invoice_pdf(self):
        service = PdfRenderService()
        context = {...}
        
        result = service.render(
            template_name='my_module/invoice.html',
            context=context,
            base_url='file:///tmp/',
        )
        
        self.assertIsInstance(result, PdfResult)
        self.assertTrue(result.pdf_bytes.startswith(b'%PDF'))
        self.assertTrue(len(result.pdf_bytes) > 1000)
```

## WeasyPrint Installation

### Linux (Ubuntu/Debian)
```bash
# Install system dependencies
sudo apt-get install python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Install Python package
pip install weasyprint
```

### macOS
```bash
brew install cairo pango gdk-pixbuf libffi
pip install weasyprint
```

### Docker
```dockerfile
FROM python:3.11

RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

RUN pip install weasyprint
```

## Limitations and Future Enhancements

### Current Limitations
- Only WeasyPrint renderer implemented
- Base template is minimal (no default header/logo)
- No built-in document persistence (modules handle this)

### Future Enhancements
- Renderer registry/factory pattern
- Multiple renderer support (ReportLab, etc.)
- Enhanced base templates with company branding
- Font management
- Watermark support
- Digital signatures

## Module Integration Checklist

When integrating the printing framework into a module:

1. ✅ Create document-specific templates extending `printing/base.html`
2. ✅ Implement `IContextBuilder` for your domain objects
3. ✅ Add print-specific CSS if needed
4. ✅ Write tests for PDF generation
5. ✅ Handle static assets (logos, etc.)
6. ✅ Configure `base_url` correctly for your environment
7. ✅ Optionally persist PDF as attachment/file
8. ✅ Add download/print endpoints to your views

## Support

For issues or questions:
- Check tests in `core/test_printing.py` for examples
- Review WeasyPrint docs: https://doc.courtbouillon.org/weasyprint/
- CSS Paged Media spec: https://www.w3.org/TR/css-page-3/

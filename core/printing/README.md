# Core Printing Framework

This directory contains the core printing framework for generating PDF documents from HTML templates.

## Quick Start

```python
from core.printing import PdfRenderService

# 1. Initialize service
service = PdfRenderService()

# 2. Render PDF
result = service.render(
    template_name='printing/example.html',
    context={'title': 'My Document'},
    base_url='file:///path/to/static/',
    filename='document.pdf'
)

# 3. Use the PDF bytes
with open('output.pdf', 'wb') as f:
    f.write(result.pdf_bytes)
```

## Demo

Run the demo script to see the framework in action:

```bash
python demo_printing.py
```

This generates an example PDF in `tmp/example-document.pdf`.

## Components

- **interfaces.py** - Core interfaces (IPdfRenderer, IContextBuilder)
- **service.py** - Main PdfRenderService orchestrating the pipeline
- **weasyprint_renderer.py** - WeasyPrint renderer implementation
- **dto.py** - PdfResult data transfer object
- **sanitizer.py** - HTML sanitization (optional security layer)

## Templates

- **base.html** - Foundation template for PDF documents
- **example.html** - Example template demonstrating features

## Static Assets

- **print.css** - CSS Paged Media rules for PDF layout

## Documentation

For detailed documentation, see:
- [PRINTING_FRAMEWORK.md](../../docs/PRINTING_FRAMEWORK.md)

## Testing

Run tests with:

```bash
python manage.py test core.test_printing
```

## Requirements

- Django 5.2+
- WeasyPrint 62.0+
- bleach 6.0+ (for sanitization)

### System Dependencies (Linux)

```bash
sudo apt-get install python3-dev libcairo2 libpango-1.0-0 \
    libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

## Features

- ✅ HTML to PDF conversion using WeasyPrint
- ✅ CSS Paged Media support (@page rules)
- ✅ Running headers and footers
- ✅ Page numbering (Seite X von Y)
- ✅ Different first page layout
- ✅ Table header repetition across pages
- ✅ Page break control
- ✅ HTML sanitization
- ✅ Static asset support (CSS, images, fonts)
- ✅ Modular renderer architecture

## Architecture

```
┌─────────────────────────────────────────┐
│         PdfRenderService                │
│  (Orchestrates rendering pipeline)      │
└──────────┬──────────────────────────────┘
           │
           ├─► Template Loader (Django)
           ├─► HTML Renderer (Django Templates)
           └─► PDF Renderer (WeasyPrint)
                    │
                    ├─► CSS Processor
                    ├─► Asset Resolver
                    └─► PDF Generator
```

## Usage in Modules

See [PRINTING_FRAMEWORK.md](../../docs/PRINTING_FRAMEWORK.md) for detailed integration guide.

### Example: Sales Document Printing

```python
# auftragsverwaltung/services/printing.py
from core.printing import PdfRenderService, IContextBuilder

class SalesDocumentContextBuilder(IContextBuilder):
    def build_context(self, obj, *, company=None):
        return {
            'document': obj,
            'lines': obj.lines.all(),
            'company': company,
        }
    
    def get_template_name(self, obj):
        return f'auftragsverwaltung/{obj.doc_type.code.lower()}.html'

# View
def print_document(request, pk):
    document = get_object_or_404(SalesDocument, pk=pk)
    
    builder = SalesDocumentContextBuilder()
    context = builder.build_context(document)
    template = builder.get_template_name(document)
    
    service = PdfRenderService()
    result = service.render(
        template_name=template,
        context=context,
        base_url=f'file://{settings.STATIC_ROOT}/',
        filename=f'{document.number}.pdf'
    )
    
    return FileResponse(
        BytesIO(result.pdf_bytes),
        content_type=result.content_type,
        filename=result.filename
    )
```

## License

See root LICENSE file.

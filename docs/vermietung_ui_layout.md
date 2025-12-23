# Vermietung UI Base Layout Documentation

## Overview

This document describes the UI structure and layout system for the Vermietung (rental management) section of K-Manager v1.0. The system is built with Bootstrap 5.3 and provides a consistent, modern dark-mode interface.

![Vermietung Dashboard](https://github.com/user-attachments/assets/f0c94d70-1f6d-43c4-8945-2d1ac6622ce8)
*Figure 1: Vermietung Dashboard with sidebar navigation and quick action cards*

## Template Structure

### Base Template: `vermietung_base.html`

The base template provides the core layout for all Vermietung pages, including:

- **Top Navigation Bar**: Main site navigation with K-Manager branding
- **Sidebar Navigation**: Vermietung-specific menu with the following items:
  - Dashboard
  - Mietobjekte (Rental Objects)
  - Verträge (Contracts)
  - Kunden (Customers)
  - Übergaben (Handovers)
  - Dokumente (Documents)
- **Flash Messages**: Dismissible alerts with icons for success, error, warning, and info messages
- **Page Header**: Consistent header section with title and action buttons
- **Content Area**: Main content region
- **Footer**: Site footer with branding

### Layout Templates

Three specialized layout templates are provided in `templates/vermietung/layouts/`:

#### 1. List Layout (`list_layout.html`)

For displaying tables/lists of items.

**Features:**
- Search/filter section
- Responsive table with hover effects
- Action buttons per row
- Pagination controls

**Usage:**
```django
{% extends "vermietung/layouts/list_layout.html" %}

{% block page_title %}Mietobjekte{% endblock %}

{% block table_headers %}
    <th>Name</th>
    <th>Type</th>
    <th>Status</th>
    <th class="text-end">Aktionen</th>
{% endblock %}

{% block table_rows %}
    {% for objekt in objekte %}
    <tr>
        <td>{{ objekt.name }}</td>
        <td>{{ objekt.get_type_display }}</td>
        <td><span class="badge bg-success">Verfügbar</span></td>
        <td class="text-end">
            <a href="#" class="btn btn-sm btn-warning">
                <i class="bi bi-pencil"></i>
            </a>
        </td>
    </tr>
    {% endfor %}
{% endblock %}
```

#### 2. Detail Layout (`detail_layout.html`)

For displaying details of a single item.

**Features:**
- Two-column detail display using definition lists
- Related data section with tabs
- Action buttons in header

**Usage:**
```django
{% extends "vermietung/layouts/detail_layout.html" %}

{% block page_title %}Mietobjekt: {{ objekt.name }}{% endblock %}

{% block page_actions %}
    <a href="{% url 'vermietung:objekt_edit' objekt.id %}" class="btn btn-warning">
        <i class="bi bi-pencil"></i> Bearbeiten
    </a>
{% endblock %}

{% block detail_content %}
    <dl class="row">
        <dt class="col-sm-4">Name:</dt>
        <dd class="col-sm-8">{{ objekt.name }}</dd>
        
        <dt class="col-sm-4">Typ:</dt>
        <dd class="col-sm-8">{{ objekt.get_type_display }}</dd>
    </dl>
{% endblock %}
```

#### 3. Form Layout (`form_layout.html`)

For create/edit forms.

**Features:**
- Two-column layout (form on left, help text on right)
- CSRF token included
- Consistent button styling
- Form validation support

**Usage:**
```django
{% extends "vermietung/layouts/form_layout.html" %}

{% block page_title %}Neues Mietobjekt{% endblock %}

{% block form_content %}
    <div class="mb-3">
        <label for="name" class="form-label">Name *</label>
        <input type="text" class="form-control" id="name" name="name" required>
    </div>
    
    <div class="mb-3">
        <label for="type" class="form-label">Typ *</label>
        <select class="form-select" id="type" name="type" required>
            <option value="">Bitte wählen...</option>
            <option value="RAUM">Raum</option>
            <option value="GEBAEUDE">Gebäude</option>
        </select>
    </div>
{% endblock %}

{% block form_actions %}
    <button type="submit" class="btn btn-primary">
        <i class="bi bi-save"></i> Speichern
    </button>
    <a href="{% url 'vermietung:objekt_list' %}" class="btn btn-secondary">
        <i class="bi bi-x-circle"></i> Abbrechen
    </a>
{% endblock %}
```

## UI Components

### Components Reference Page

Access at `/vermietung/components/` to see all available UI components in action:

- **Buttons**: Primary, Success, Warning, Danger, Secondary, Outline variants, Sizes
- **Badges**: Status badges, Pill badges, Color variants
- **Alerts**: Success, Error, Warning, Info with dismissible functionality
- **Cards**: With header, footer, badges
- **Tables**: Dark mode, hover effects, action buttons
- **Forms**: Text inputs, Selects, Textareas, Checkboxes, Radio buttons
- **Breadcrumbs**: Navigation breadcrumbs
- **Loading Spinners**: Different sizes

### Standard Components

#### Buttons

```html
<!-- Primary action -->
<button class="btn btn-primary">
    <i class="bi bi-plus-circle"></i> Neu
</button>

<!-- Success action -->
<button class="btn btn-success">
    <i class="bi bi-save"></i> Speichern
</button>

<!-- Warning action -->
<button class="btn btn-warning">
    <i class="bi bi-pencil"></i> Bearbeiten
</button>

<!-- Danger action -->
<button class="btn btn-danger">
    <i class="bi bi-trash"></i> Löschen
</button>
```

#### Badges

```html
<!-- Status badges -->
<span class="badge bg-success">Aktiv</span>
<span class="badge bg-danger">Beendet</span>
<span class="badge bg-warning">Entwurf</span>
<span class="badge bg-info">Info</span>
```

#### Alerts

```html
<!-- Success message -->
<div class="alert alert-success alert-dismissible fade show" role="alert">
    <i class="bi bi-check-circle-fill"></i>
    <strong>Erfolg!</strong> Der Vorgang wurde erfolgreich abgeschlossen.
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
```

## Flash Messages

Flash messages are automatically displayed in the base template. Use Django's messages framework:

```python
from django.contrib import messages

# In your view
def my_view(request):
    messages.success(request, 'Erfolgreich gespeichert!')
    messages.error(request, 'Ein Fehler ist aufgetreten.')
    messages.warning(request, 'Bitte überprüfen Sie Ihre Eingaben.')
    messages.info(request, 'Information: Dies ist ein Hinweis.')
    return redirect('vermietung:home')
```

The messages will appear at the top of the content area with appropriate icons and styling.

## Styling

### Color Scheme

The application uses a modern dark mode color palette defined in `static/css/site.css`:

- **Primary**: Indigo (#6366f1)
- **Secondary**: Purple (#8b5cf6)
- **Success**: Green (#10b981)
- **Warning**: Amber (#f59e0b)
- **Danger**: Red (#ef4444)
- **Accent**: Cyan (#06b6d4)

### Dark Mode

All components are styled for dark mode with:
- Dark backgrounds (#0f172a, #1e293b)
- Light text (#f1f5f9, #cbd5e1)
- Appropriate contrast ratios for accessibility

## Navigation

### Sidebar Menu

The sidebar navigation is fixed on desktop screens and collapses on mobile. Menu items automatically highlight based on the current URL path.

Active menu items have:
- Primary color text
- Left border accent
- Background highlight

### Breadcrumbs (Optional)

Add breadcrumbs to any page by overriding the `breadcrumb` block:

```django
{% block breadcrumb %}
<nav aria-label="breadcrumb">
    <ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="{% url 'vermietung:home' %}">Dashboard</a></li>
        <li class="breadcrumb-item"><a href="{% url 'vermietung:objekt_list' %}">Mietobjekte</a></li>
        <li class="breadcrumb-item active" aria-current="page">{{ objekt.name }}</li>
    </ol>
</nav>
{% endblock %}
```

## Bootstrap 5.3

The application uses Bootstrap 5.3.2 loaded from CDN:
- CSS: https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
- JS Bundle: https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
- Icons: https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.2/font/bootstrap-icons.css

## HTMX Integration

HTMX 1.9.10 is included for dynamic content updates without full page reloads.

## Responsive Design

All layouts are responsive and work on:
- Desktop (>= 992px): Full sidebar and content
- Tablet (768px - 991px): Collapsible sidebar
- Mobile (< 768px): Hidden sidebar with toggle button

## Customization

### Custom CSS

Additional custom styles are in `static/css/site.css`. Override Bootstrap defaults by modifying CSS variables in the `:root` selector.

### Adding New Pages

1. Create a new template extending `vermietung_base.html` or one of the layout templates
2. Override the necessary blocks
3. Create a view function in `vermietung/views.py`
4. Add URL pattern in `vermietung/urls.py`

### Example:

```python
# views.py
@vermietung_required
def objekt_list(request):
    objekte = MietObjekt.objects.all()
    return render(request, 'vermietung/objekt_list.html', {'objekte': objekte})

# urls.py
urlpatterns = [
    path('objekte/', views.objekt_list, name='objekt_list'),
]
```

```django
{# objekt_list.html #}
{% extends "vermietung/layouts/list_layout.html" %}

{% block page_title %}Mietobjekte{% endblock %}

{% block page_actions %}
    <a href="{% url 'vermietung:objekt_create' %}" class="btn btn-primary">
        <i class="bi bi-plus-circle"></i> Neu
    </a>
{% endblock %}

{# ... override other blocks as needed #}
```

## Accessibility

All components follow accessibility best practices:
- Semantic HTML5 elements
- ARIA labels where appropriate
- Keyboard navigation support
- Sufficient color contrast
- Screen reader-friendly alerts

## Testing

The template structure has been validated and all templates load correctly without errors. To test:

1. Start the development server
2. Log in as a user with Vermietung permissions
3. Navigate to `/vermietung/` for the dashboard
4. Navigate to `/vermietung/components/` for the components reference page

## Future Enhancements

Potential improvements:
- Dark/Light mode toggle
- User preferences for sidebar collapse state
- Additional layout variants (grid view, card view)
- More complex filter components
- Advanced table features (sorting, column visibility)

# KManager v1.0 - Entwicklungs-Guide

## Entwicklungsumgebung

### Empfohlene IDE
- Visual Studio Code
- PyCharm Professional
- Sublime Text mit Python-Plugins

### Nützliche VS Code Extensions
- Python
- Django
- Pylance
- GitLens
- Bootstrap 5 Snippets

## Code-Style

### Python
- Folgen Sie PEP 8 Guidelines
- Verwenden Sie Type Hints wo sinnvoll
- Docstrings für Funktionen und Klassen

Beispiel:
```python
def calculate_rental_period(start_date: datetime, end_date: datetime | None) -> int:
    """
    Calculate the rental period in days.
    
    Args:
        start_date: Start of the rental period
        end_date: End of the rental period (None for open-ended)
    
    Returns:
        Number of days in the rental period
    """
    # Implementation
    pass
```

### HTML/Templates
- Verwenden Sie Django Template-Tags
- Konsistente Einrückung (4 Spaces)
- Semantisches HTML5

### CSS
- Alle Styles in `static/css/site.css`
- Verwenden Sie CSS-Variablen für Farben
- Mobile-First Approach
- Keine Inline-Styles

## Git Workflow

### Branches
- `main` - Produktions-Code
- `develop` - Development-Branch
- `feature/*` - Feature-Branches
- `bugfix/*` - Bugfix-Branches

### Commit Messages
Format: `<type>: <description>`

Types:
- `feat`: Neues Feature
- `fix`: Bugfix
- `docs`: Dokumentation
- `style`: Formatierung, Styling
- `refactor`: Code-Refactoring
- `test`: Tests
- `chore`: Maintenance

Beispiel:
```
feat: Add asset management module
fix: Correct date range validation
docs: Update setup instructions
```

## Django Entwicklung

### Neue App erstellen
```bash
python manage.py startapp app_name
```

Dann in `settings.py` registrieren:
```python
INSTALLED_APPS = [
    # ...
    'app_name',
]
```

### Models erstellen
```python
from django.db import models

class Asset(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
```

### Migrationen
```bash
# Migrationen erstellen
python manage.py makemigrations

# Migrationen anwenden
python manage.py migrate

# Migrationen anzeigen
python manage.py showmigrations
```

### Views erstellen
```python
from django.shortcuts import render, get_object_or_404
from .models import Asset

def asset_list(request):
    assets = Asset.objects.all()
    return render(request, 'assets/list.html', {'assets': assets})

def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    return render(request, 'assets/detail.html', {'asset': asset})
```

### URLs konfigurieren
```python
from django.urls import path
from . import views

app_name = 'assets'

urlpatterns = [
    path('', views.asset_list, name='list'),
    path('<int:pk>/', views.asset_detail, name='detail'),
]
```

## HTMX Best Practices

### Einfache GET-Requests
```html
<button hx-get="/api/data/" hx-target="#result">
    Daten laden
</button>
<div id="result"></div>
```

### POST-Requests mit CSRF
```html
<form hx-post="/api/submit/" hx-target="#response">
    {% csrf_token %}
    <input type="text" name="field">
    <button type="submit">Absenden</button>
</form>
```

### Loading Indicators
```html
<button hx-get="/api/slow/" hx-target="#result">
    <span class="htmx-indicator spinner-border spinner-border-sm"></span>
    Laden
</button>
```

### Partial Templates
Erstellen Sie separate Templates für HTMX-Responses:
```
templates/
├── asset_list.html          # Vollständige Seite
└── partials/
    └── asset_table.html     # Nur die Tabelle
```

## Testing

### Unit Tests
```python
from django.test import TestCase
from .models import Asset

class AssetTestCase(TestCase):
    def setUp(self):
        Asset.objects.create(name="Test Asset")
    
    def test_asset_creation(self):
        asset = Asset.objects.get(name="Test Asset")
        self.assertEqual(asset.name, "Test Asset")
```

### Tests ausführen
```bash
# Alle Tests
python manage.py test

# Spezifische App
python manage.py test core

# Mit Coverage
coverage run --source='.' manage.py test
coverage report
```

## Bootstrap Komponenten

### Cards
```html
<div class="card">
    <div class="card-header">
        <h5>Titel</h5>
    </div>
    <div class="card-body">
        Inhalt
    </div>
</div>
```

### Buttons
```html
<button class="btn btn-primary">Primary</button>
<button class="btn btn-secondary">Secondary</button>
<button class="btn btn-success">Success</button>
```

### Forms
```html
<div class="mb-3">
    <label for="field" class="form-label">Label</label>
    <input type="text" class="form-control" id="field">
</div>
```

## Debugging

### Django Debug Toolbar (optional)
```bash
pip install django-debug-toolbar
```

### Print Debugging
```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")
```

### Django Shell
```bash
python manage.py shell

# Interaktiv mit Models arbeiten
>>> from core.models import Asset
>>> Asset.objects.all()
```

## Performance

### Database Queries optimieren
```python
# Vermeiden Sie N+1 Queries
assets = Asset.objects.select_related('category').all()

# Prefetch related objects
assets = Asset.objects.prefetch_related('attributes').all()
```

### Static Files
```bash
# Entwicklung: Automatisch geladen
# Produktion: Sammeln
python manage.py collectstatic
```

## Deployment Checkliste

- [ ] `DEBUG = False` in Production
- [ ] `SECRET_KEY` aus Environment Variable
- [ ] `ALLOWED_HOSTS` konfiguriert
- [ ] Static Files gesammelt
- [ ] Database Migrationen ausgeführt
- [ ] PostgreSQL konfiguriert
- [ ] Backup-Strategie implementiert
- [ ] Logging konfiguriert
- [ ] HTTPS aktiviert

## Ressourcen

### Offizielle Dokumentation
- [Django Documentation](https://docs.djangoproject.com/)
- [Bootstrap Documentation](https://getbootstrap.com/docs/5.3/)
- [HTMX Documentation](https://htmx.org/docs/)

### Tutorials
- Django Girls Tutorial
- Real Python Django Tutorials
- HTMX Examples

## Hilfe & Support

Bei Fragen:
1. Dokumentation prüfen
2. Django Logs analysieren
3. Team-Mitglieder fragen
4. Stack Overflow durchsuchen

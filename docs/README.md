# KManager v1.0 - Projekt-Dokumentation

## Überblick

Dieses Dokument beschreibt die Grundstruktur der KManager v1.0 Anwendung, die im Rahmen des Issues "Grundgerüst App auf Basis von Django + HTMX + Bootstrap 5.3 erstellen" implementiert wurde.

## Was wurde implementiert

### 1. Django Projekt-Struktur
- Django 5.0.1 Projekt erstellt
- Core App als Hauptapplikation angelegt
- PostgreSQL als Datenbank konfiguriert
- Environment Variables Integration (.env)

### 2. Frontend Framework
- **Bootstrap 5.3** integriert (via CDN)
  - Dark Mode Theme aktiviert
  - Responsive Design
  - Bootstrap Icons eingebunden
  
- **HTMX 1.9.10** integriert (via CDN)
  - Dynamische Partial Updates
  - Demo-Funktionalität implementiert

### 3. Custom Styling
- Zentrale CSS-Datei: `static/css/site.css`
- Moderne Dark Mode Farbpalette:
  - Primary: Indigo (#6366f1)
  - Secondary: Purple (#8b5cf6)
  - Accent: Cyan (#06b6d4)
  - Success: Green (#10b981)
  - Warning: Amber (#f59e0b)
  - Danger: Red (#ef4444)
- Keine Inline-Styles
- Konsistente Verwendung von CSS-Variablen

### 4. Templates
- `base.html` - Basis-Template mit Navigation und Footer
- `home.html` - Startseite mit Feature-Übersicht
- `htmx_demo.html` - HTMX Funktionalitäts-Demo

### 5. Konfiguration
- `requirements.txt` - Python-Abhängigkeiten
- `.env.example` - Template für Umgebungsvariablen
- `settings.py` - Django-Konfiguration mit Environment Variables

### 6. Dokumentation
- `docs/setup.md` - Installations- und Setup-Anleitung
- `docs/architecture.md` - Architektur-Übersicht
- `docs/development.md` - Entwicklungs-Guide
- `docs/README.md` - Diese Datei

## Verzeichnisstruktur

```
KManager/
├── kmanager/                 # Django Projekt
│   ├── __init__.py
│   ├── settings.py          # Konfiguration mit env vars
│   ├── urls.py              # Haupt-URL-Routing
│   ├── asgi.py
│   └── wsgi.py
│
├── core/                    # Kern-Applikation
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py            # Home & HTMX Demo Views
│   ├── urls.py             # URL-Konfiguration
│   └── tests.py
│
├── templates/              # HTML Templates
│   ├── base.html          # Basis-Template
│   ├── home.html          # Home-Seite
│   └── htmx_demo.html     # HTMX Demo
│
├── static/                # Statische Dateien
│   ├── css/
│   │   └── site.css      # Zentrale CSS-Datei
│   └── js/               # (leer, für zukünftige JS-Dateien)
│
├── docs/                  # Dokumentation
│   ├── README.md         # Dieses Dokument
│   ├── setup.md          # Setup-Anleitung
│   ├── architecture.md   # Architektur
│   └── development.md    # Entwicklungs-Guide
│
├── .env.example          # Umgebungsvariablen-Template
├── .gitignore           # Git Ignore Rules
├── requirements.txt     # Python-Abhängigkeiten
├── manage.py           # Django Management-Script
└── README.md          # Haupt-README

```

## Features

### Home-Seite
- Willkommens-Nachricht
- Feature-Übersicht in Cards:
  - Assets-Verwaltung
  - Verfügbarkeits-Management
  - Vertragsverwaltung
- Tech Stack Information
- HTMX Demo-Button

### HTMX Integration
- Funktionierender HTMX-Button auf der Home-Seite
- Demonstriert Partial Page Updates
- Loading-Indicator während des Requests
- Dynamische Zeitstempel-Anzeige

### Dark Mode Design
- Professionelles, modernes Dark Theme
- Konsistente Farbpalette
- Hover-Effekte auf Cards und Buttons
- Responsive Navigation
- Optimierte Lesbarkeit

## Technische Details

### Python Packages
```
Django==5.0.1
psycopg2-binary==2.9.9
python-dotenv==1.0.0
django-extensions==3.2.3
```

### Frontend Bibliotheken (CDN)
- Bootstrap 5.3.2
- Bootstrap Icons 1.11.2
- HTMX 1.9.10

### Datenbank
- PostgreSQL (konfiguriert)
- Fallback auf SQLite für Development (optional)

## Environment Variables

Erforderliche Variablen in `.env`:
```
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=kmanager
DB_USER=kmanager_user
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
```

## Nächste Schritte

### Phase 1 - Domain Models
- [ ] Tenant Model (Multi-Tenant)
- [ ] Party Model (Mieter/Kunden)
- [ ] Asset Models (Mietobjekte)
- [ ] Location Model (Standorte)
- [ ] Reservation Model (Verfügbarkeit)
- [ ] Contract Models (Verträge)

### Phase 1.5 - UI & Workflows
- [ ] CRUD-Views für alle Models
- [ ] Verfügbarkeitsprüfung
- [ ] Reservierungs-Workflow
- [ ] Vertrags-Workflow

### Phase 2 - Erweiterte Features
- [ ] Dashboard (Vermietung)
- [ ] Reporting
- [ ] Finanzverwaltung
- [ ] Dashboard (Finanzen)

## Best Practices implementiert

1. **Keine Inline-Styles**: Alle Styles in zentraler CSS-Datei
2. **Environment Variables**: Sensible Daten in .env
3. **Template Inheritance**: Wiederverwendbare Base-Templates
4. **URL Namespacing**: Named URLs für Reverse-Lookups
5. **Static Files Organization**: Klare Struktur für CSS/JS
6. **Documentation**: Umfassende MD-Dokumentation
7. **Git Best Practices**: .gitignore für sensible Dateien

## Testing

### Server starten
```bash
python manage.py runserver
```

### Erwartetes Ergebnis
- Home-Seite lädt unter http://localhost:8000
- Dark Mode ist aktiv
- Bootstrap-Styling funktioniert
- HTMX-Button lädt dynamisch Content
- Navigation ist funktional
- Footer zeigt Versions-Info

## Bekannte Einschränkungen

- Keine echte Datenbank-Integration (nur Konfiguration)
- Keine Models definiert (Phase 1)
- Keine Authentifizierung (kommt später)
- Keine Unit Tests (sollten bei Feature-Entwicklung hinzugefügt werden)

## Änderungshistorie

### v1.0 - Initial Release (Dezember 2024)
- Django-Projekt mit HTMX und Bootstrap 5.3 aufgesetzt
- Dark Mode Theme implementiert
- Grundlegende Navigation und Home-Seite
- HTMX Demo funktionsfähig
- Umfassende Dokumentation erstellt

## Lizenz

TBD - Siehe LICENSE Datei im Root-Verzeichnis

## Kontakt & Support

Bei Fragen zur Implementierung, siehe:
- `docs/development.md` für Entwicklungs-Guidelines
- `docs/setup.md` für Setup-Probleme
- `docs/architecture.md` für Architektur-Fragen

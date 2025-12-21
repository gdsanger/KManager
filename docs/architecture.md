# KManager v1.0 - Architektur

## Übersicht

KManager ist eine modulare Vermietungs- und Verwaltungsplattform, die auf modernen Web-Technologien basiert.

## Tech Stack

### Backend
- **Django 5.0.1**: Python Web Framework
  - ORM für Datenbankzugriff
  - Admin-Interface
  - Template Engine
  - Authentication & Authorization

### Frontend
- **Bootstrap 5.3**: CSS Framework
  - Dark Mode Theme
  - Responsive Design
  - Moderne UI-Komponenten
  
- **HTMX 1.9.10**: JavaScript Library für dynamische Interaktionen
  - Partial Page Updates
  - AJAX ohne JavaScript-Code
  - Progressive Enhancement
  
- **Bootstrap Icons**: Icon Library

### Datenbank
- **PostgreSQL**: Relationale Datenbank
  - Multi-Tenant Unterstützung
  - Zeitbasierte Constraints
  - Vollständige ACID-Compliance

## Projektstruktur

```
KManager/
├── kmanager/              # Django Projekt-Konfiguration
│   ├── settings.py        # Hauptkonfiguration
│   ├── urls.py           # URL-Routing
│   └── wsgi.py           # WSGI Entry Point
├── core/                 # Kern-Applikation
│   ├── views.py          # View-Logik
│   ├── urls.py           # URL-Konfiguration
│   └── models.py         # Datenmodelle (später)
├── templates/            # HTML Templates
│   ├── base.html         # Basis-Template
│   ├── home.html         # Home-Seite
│   └── htmx_demo.html    # HTMX Demo
├── static/               # Statische Dateien
│   ├── css/
│   │   └── site.css      # Zentrale CSS-Datei
│   └── js/               # JavaScript (später)
├── docs/                 # Dokumentation
│   ├── setup.md          # Setup-Anleitung
│   ├── architecture.md   # Diese Datei
│   └── development.md    # Entwicklungs-Guide
├── requirements.txt      # Python-Abhängigkeiten
├── .env.example         # Umgebungsvariablen-Template
└── manage.py            # Django Management-Script
```

## Design Patterns

### Template Inheritance
- `base.html` als Basis-Template
- Block-System für flexible Content-Bereiche
- Wiederverwendbare Komponenten

### URL Routing
- URL-Patterns in separaten `urls.py` Dateien
- Named URLs für Reverse-Lookups
- RESTful URL-Design

### Static Files Management
- Zentrale `static/` Directory
- CDN für externe Bibliotheken (Bootstrap, HTMX)
- Eigene CSS in `site.css`

## Styling-Konzept

### Dark Mode
- Bootstrap 5.3 Dark Theme als Basis
- Eigene CSS-Variablen für konsistente Farbpalette
- Moderne, professionelle Farben:
  - Primary: Indigo (#6366f1)
  - Accent: Cyan (#06b6d4)
  - Success: Green (#10b981)
  - Warning: Amber (#f59e0b)
  - Danger: Red (#ef4444)

### CSS-Struktur
- Keine Inline-Styles
- Alle Styles in `static/css/site.css`
- CSS-Variablen für einfache Anpassungen
- Mobile-First Responsive Design

## HTMX Integration

### Konzept
- Server-Side Rendering mit partiellen Updates
- Keine komplexe Frontend-Build-Pipeline
- Progressive Enhancement
- Einfache AJAX-Interaktionen ohne JavaScript

### Verwendung
- `hx-get`, `hx-post` für HTTP-Requests
- `hx-target` für Ziel-Elemente
- `hx-swap` für Update-Strategien
- `htmx-indicator` für Loading States

## Datenbank-Design

### PostgreSQL Features
- Multi-Tenant via `tenant_id`
- Zeitbasierte Queries (`start_at`, `end_at`)
- Foreign Key Constraints
- Check Constraints für Geschäftslogik
- Indexes für Performance

### Migrationen
- Django Migrations für Schema-Änderungen
- Versionskontrolle der Datenbankstruktur
- Automatische Synchronisation

## Sicherheit

### Django Security Features
- CSRF-Schutz
- SQL Injection Prevention (ORM)
- XSS-Schutz (Template Auto-Escaping)
- Secure Password Hashing

### Environment Variables
- Secrets in `.env` Datei
- Keine Credentials in Code
- `.env` in `.gitignore`

## Skalierbarkeit

### Multi-Tenant
- Tenant-scoped Daten
- Isolierte Datenzugriffe
- Shared Database Schema

### Performance
- Database Connection Pooling
- Query-Optimierung
- Static File Caching
- CDN für externe Ressourcen

## Zukünftige Erweiterungen

### Geplante Apps (Phase 1)
- `parties/` - Mieter/Kunden-Verwaltung
- `assets/` - Mietobjekte-Verwaltung
- `availability/` - Verfügbarkeits-Management
- `contracts/` - Vertragsverwaltung

### Phase 2
- `finance/` - Finanzverwaltung
- `dashboards/` - Reporting & Analytics

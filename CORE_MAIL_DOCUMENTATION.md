# Core Mail Feature - Implementierungsübersicht

## Überblick

Das Core-Mail-Modul bietet eine vollständige Lösung für E-Mail-Verwaltung und -Versand mit folgenden Funktionen:

- **SMTP-Konfiguration**: Globale, zentrale SMTP-Einstellungen als Singleton
- **Mail-Templates**: Verwaltung von E-Mail-Vorlagen mit HTML-Editor (TinyMCE)
- **Template-Rendering**: Django Template Engine Integration für dynamische Inhalte
- **SMTP-Versand**: Unterstützung für TLS und Authentifizierung

## Architektur

### Models

#### `SmtpSettings` (Singleton)
- `host`: SMTP-Server Hostname
- `port`: SMTP-Port (Standard: 587)
- `use_tls`: STARTTLS aktivieren (Boolean)
- `username`: Benutzername (optional)
- `password`: Passwort (optional)

**Besonderheiten:**
- Nur eine Instanz erlaubt (Singleton-Pattern)
- Automatische Erstellung mit Standardwerten via `get_settings()`
- Keine Authentifizierung wenn `username` leer

#### `MailTemplate`
- `key`: Eindeutiger technischer Schlüssel (SlugField)
- `subject`: Betreffzeile
- `message`: Nachricht (Markdown oder HTML)
- `from_address`: Absender E-Mail (optional, fällt auf DEFAULT_FROM_EMAIL zurück)
- `from_name`: Absender Name (optional, fällt auf DEFAULT_FROM_NAME zurück)
- `cc_address`: Optionale CC-Adresse
- `is_active`: Template aktiv/deaktiviert (Boolean, Standard: True)
- `created_at`: Erstellungszeitpunkt (automatisch)
- `updated_at`: Letzte Änderung (automatisch)

**Besonderheiten:**
- `key` ist ein SlugField (URL-sicher mit Bindestrichen)
- Nur aktive Templates können versendet werden
- Leere Absenderfelder werden durch Defaults ersetzt
- Zeitstempel werden automatisch gepflegt

### Service Layer (`core/mailing/service.py`)

#### `render_template(mail_template, context)`
Rendert Subject und HTML-Body mit Django Template Engine.

```python
from core.models import MailTemplate
from core.mailing.service import render_template

template = MailTemplate.objects.get(key='welcome_mail')
context = {
    'name': 'Max Mustermann',
    'email': 'max@example.com'
}
subject, html = render_template(template, context)
```

#### `send_mail(template_key, to, context)`
Versendet E-Mail über SMTP mit automatischem CC.

```python
from core.mailing.service import send_mail

send_mail(
    template_key='welcome_mail',
    to=['customer@example.com'],
    context={
        'name': 'Max Mustermann',
        'vertrag_nummer': 'V-2025-001'
    }
)
```

**Features:**
- Prüfung ob Template aktiv ist (is_active=True)
- Automatisches CC wenn im Template konfiguriert
- Fallback auf DEFAULT_FROM_EMAIL/DEFAULT_FROM_NAME bei leeren Feldern
- TLS-Unterstützung (STARTTLS)
- Optionale SMTP-Authentifizierung
- Fehlerbehandlung mit spezifischen Exceptions

## UI / Admin

### SMTP-Einstellungen
- URL: `/smtp-settings/`
- Zugriff: `is_staff` erforderlich
- Singleton-Formular zur Konfiguration

### Mail-Templates
- Liste: `/mail-templates/`
- Erstellen: `/mail-templates/create/`
- Bearbeiten: `/mail-templates/<id>/edit/`
- Löschen: `/mail-templates/<id>/delete/`
- TinyMCE-Integration für HTML-Editor
- Zugriff: `is_staff` erforderlich

## Verwendungsbeispiele

### Beispiel 1: Einfaches Template erstellen

```python
from core.models import MailTemplate

template = MailTemplate.objects.create(
    key='vertrag-erstellt',  # SlugField: Bindestriche statt Unterstriche
    subject='Neuer Mietvertrag {{ vertrag_nummer }}',
    message='''
        <h1>Guten Tag {{ kunde_name }},</h1>
        <p>Ihr Mietvertrag {{ vertrag_nummer }} wurde erstellt.</p>
        <p>Objekt: {{ objekt_name }}</p>
        <p>Mit freundlichen Grüßen,<br>Ihr K-Manager Team</p>
    ''',
    from_address='noreply@kmanager.example.com',
    from_name='K-Manager',
    cc_address='office@kmanager.example.com',
    is_active=True  # Template ist aktiv
)
```

### Beispiel 2: E-Mail versenden

```python
from core.mailing.service import send_mail

# In einer View oder Service-Methode
send_mail(
    template_key='vertrag-erstellt',  # Muss mit Template-Key übereinstimmen
    to=['kunde@example.com'],
    context={
        'kunde_name': 'Max Mustermann',
        'vertrag_nummer': 'V-2025-001',
        'objekt_name': 'Lager 1A'
    }
)
```

**Hinweis:** Inaktive Templates (is_active=False) können nicht versendet werden und führen zu einem MailServiceError.

### Beispiel 3: Template mit Schleifen

```html
<h1>Hallo {{ mieter_name }},</h1>
<p>Ihre aktiven Verträge:</p>
<ul>
{% for vertrag in vertraege %}
    <li>{{ vertrag.objekt }} - {{ vertrag.mietpreis }} EUR/Monat</li>
{% endfor %}
</ul>
```

### Beispiel 4: Fehlerbehandlung

```python
from core.mailing.service import send_mail, MailServiceError, MailSendError

try:
    send_mail('welcome_mail', ['user@example.com'], {'name': 'User'})
except MailServiceError as e:
    logger.error(f"Mail service error: {e}")
except MailSendError as e:
    logger.error(f"Failed to send email: {e}")
```

## Sicherheitshinweise

1. **Credentials**: SMTP-Passwörter werden in der Datenbank gespeichert. Für Produktion:
   - Verwenden Sie App-spezifische Passwörter (z.B. Google App Passwords)
   - Erwägen Sie Umgebungsvariablen für kritische Daten
   - Aktivieren Sie Datenbank-Verschlüsselung

2. **HTML-Templates**: 
   - Templates können nur von Staff-Usern bearbeitet werden
   - Django's Auto-Escaping schützt vor XSS in User-Daten
   - HTML im Template selbst wird nicht escaped (bewusst für Layout)

3. **E-Mail-Validierung**:
   - `from_address` und `cc_copy_to` werden validiert
   - Django EmailField sorgt für korrekte E-Mail-Formate

## Tests

```bash
# Alle Mail-Tests
python manage.py test core.test_mail_models core.test_mail_service core.test_mail_views

# Nur Model-Tests
python manage.py test core.test_mail_models

# Nur Service-Tests
python manage.py test core.test_mail_service

# Nur View-Tests
python manage.py test core.test_mail_views
```

## Konfiguration

### SMTP-Einstellungen über Umgebungsvariablen (optional)

Statt die Datenbank zu verwenden, könnten SMTP-Settings auch über Environment Variables konfiguriert werden:

```python
# In settings.py
EMAIL_HOST = os.getenv('SMTP_HOST', 'localhost')
EMAIL_PORT = os.getenv('SMTP_PORT', 587)
EMAIL_USE_TLS = os.getenv('SMTP_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('SMTP_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD', '')
```

## Erweiterungsmöglichkeiten

Für zukünftige Versionen außerhalb des MVP-Scopes:

1. **Mail-Compose Dialog**: UI für freies Verfassen mit Template-Auswahl
2. **Attachments**: Dateianhänge unterstützen
3. **Async Queue**: Background-Jobs mit Celery/RQ
4. **Mail History**: MailOutbox-Model für Tracking
5. **Mehrere Empfänger**: BCC, mehrere To-Adressen im UI
6. **Template-Vorschau**: Live-Preview im Editor
7. **Inline-Bilder**: CID-Attachments für embedded images

## Navigation

Die Mail-Funktionen sind im Hauptmenü unter "E-Mail" verfügbar (nur für Staff-User):
- E-Mail → Templates
- E-Mail → SMTP Einstellungen

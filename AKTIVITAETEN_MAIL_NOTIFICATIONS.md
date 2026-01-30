# Aktivitäten E-Mail-Benachrichtigungen - Implementierung

## Überblick

Diese Implementierung fügt automatische E-Mail-Benachrichtigungen für Aktivitäten hinzu:
- **Benachrichtigung bei Zuweisung**: Wenn eine Aktivität einem Benutzer zugewiesen wird
- **Benachrichtigung bei Erledigung**: Wenn eine Aktivität als erledigt markiert wird

## Architektur

### 1. Mail-Templates (Migration)

**Datei:** `core/migrations/0007_add_activity_mail_templates.py`

Erstellt zwei MailTemplate-Datensätze:

#### Template 1: `activity-assigned`
- **Betreff:** `Neue Aktivität zugewiesen: {{ activity_title }}`
- **Trigger:** Aktivität erstellt mit assigned_user ODER assigned_user geändert
- **Empfänger:** Neuer assigned_user
- **Variablen:**
  - `assignee_name`: Name des Zugewiesenen
  - `activity_title`: Titel der Aktivität
  - `activity_description`: Beschreibung
  - `activity_priority`: Priorität (Niedrig/Normal/Hoch)
  - `activity_due_date`: Fälligkeitsdatum (formatiert: DD.MM.YYYY)
  - `activity_context`: Kontext (Vertrag/Mietobjekt/Kunde)
  - `activity_url`: URL zur Aktivität
  - `creator_name`: Name des Erstellers
  - `creator_email`: E-Mail des Erstellers

#### Template 2: `activity-completed`
- **Betreff:** `Aktivität erledigt: {{ activity_title }}`
- **Trigger:** Status wechselt zu ERLEDIGT
- **Empfänger:** Ersteller der Aktivität
- **Variablen:**
  - `creator_name`: Name des Erstellers
  - `activity_title`: Titel der Aktivität
  - `activity_context`: Kontext
  - `activity_url`: URL zur Aktivität
  - `completed_by_name`: Name des Benutzers, der die Aktivität erledigt hat
  - `completed_at`: Zeitpunkt der Erledigung (formatiert: DD.MM.YYYY HH:MM)

**HTML-Design:**
- Outlook-kompatibel (tabellenbasiert)
- Inline CSS (keine externen Stylesheets)
- Responsive Design
- Bootstrap-Farben (#0d6efd für assigned, #198754 für completed)
- Call-to-Action Buttons mit Links zur Aktivität

### 2. Signal-Handler

**Datei:** `vermietung/signals.py`

Implementiert zwei Django Signals:

#### `pre_save` Signal
- Speichert Original-Werte vor dem Speichern
- Benötigt für Deduplizierung (verhindert doppelte Mails)
- Speichert `_original_assigned_user` und `_original_status` auf der Instanz

#### `post_save` Signal
- Prüft Änderungen und versendet E-Mails
- **Case 1:** Neue Aktivität mit assigned_user → Mail an assigned_user
- **Case 2:** assigned_user geändert → Mail an neuen assigned_user
- **Case 3:** Status zu ERLEDIGT geändert → Mail an ersteller

**Deduplizierung:**
- Mails werden NUR bei Transitionen versendet
- Wiederholtes Speichern ohne Änderung = keine Mail
- Bereits erledigte Aktivität erneut speichern = keine Mail

**Fehlerbehandlung:**
- Graceful Error Handling (keine Exceptions nach außen)
- Logging mit logger.warning bei Fehlern
- System funktioniert auch bei SMTP-Ausfällen

### 3. Views

**Datei:** `vermietung/views.py`

#### Geändert: `aktivitaet_edit`
- Entfernt: Manuelle E-Mail-Versand-Logik
- Vereinfacht: Nur noch Speichern, Signals kümmern sich um Mails
- Kommentar hinzugefügt: "Email notifications are sent automatically via signals"

#### Neu: `aktivitaet_mark_completed`
- Markiert Aktivität als ERLEDIGT
- Löst automatisch Mail an Ersteller aus (via Signal)
- Zeigt Bestätigungsmeldung
- Redirect zurück zum Edit-View

### 4. URLs

**Datei:** `vermietung/urls.py`

Neue URL hinzugefügt:
```python
path('aktivitaeten/<int:pk>/erledigt/', views.aktivitaet_mark_completed, name='aktivitaet_mark_completed')
```

### 5. Template

**Datei:** `templates/vermietung/aktivitaeten/form.html`

#### Neuer Button: "Als erledigt markieren"
- Nur sichtbar bei Edit (nicht Create)
- Nur sichtbar wenn Status != ERLEDIGT
- Grüner Button mit Icon
- JavaScript-Bestätigungsdialog
- Sendet POST an `aktivitaet_mark_completed`

```html
{% if not is_create and aktivitaet.status != 'ERLEDIGT' %}
<button type="button" class="btn btn-success" onclick="markAsCompleted()">
    <i class="bi bi-check-circle-fill"></i> Als erledigt markieren
</button>
{% endif %}
```

## Tests

**Datei:** `vermietung/test_aktivitaet_mail_notifications.py`

16 Tests in 4 Kategorien:

### 1. Template Creation Tests (2)
- `test_activity_assigned_template_exists`
- `test_activity_completed_template_exists`

### 2. Template Rendering Tests (3)
- `test_render_assigned_template_complete_context`
- `test_render_assigned_template_minimal_context`
- `test_render_completed_template`

### 3. Signal Notification Tests (7)
- `test_signal_sends_mail_on_create_with_assignee`
- `test_signal_does_not_send_mail_on_create_without_assignee`
- `test_signal_sends_mail_on_assignee_change`
- `test_signal_sends_mail_on_reassignment`
- `test_signal_does_not_send_mail_on_save_without_assignee_change`
- `test_signal_sends_completed_mail_to_creator`
- `test_signal_does_not_send_completed_mail_twice`

### 4. View Integration Tests (4)
- `test_mark_completed_view_changes_status`
- `test_mark_completed_already_completed`
- `test_mark_completed_button_visible_when_not_completed`
- `test_mark_completed_button_not_visible_when_completed`

**Test-Ergebnis:** Alle 16 Tests bestehen ✅

## Verwendung

### Migration ausführen

```bash
python manage.py migrate core
```

Dies erstellt die beiden MailTemplate-Datensätze in der Datenbank.

### SMTP-Einstellungen konfigurieren

1. Admin-Login: http://localhost:8000/admin/
2. Navigieren zu: E-Mail → SMTP Einstellungen
3. Konfigurieren:
   - Host: z.B. `smtp.gmail.com`
   - Port: `587`
   - Use TLS: ✓
   - Username: Ihre E-Mail
   - Password: App-spezifisches Passwort

### Templates anpassen (Optional)

1. Admin-Login
2. Navigieren zu: E-Mail → Templates
3. Templates bearbeiten:
   - `activity-assigned`
   - `activity-completed`
4. HTML und Betreff anpassen nach Bedarf

### Aktivität zuweisen (löst Mail aus)

1. Aktivität erstellen oder bearbeiten
2. Feld "Zugewiesen an (Intern)" auswählen
3. Speichern
4. → E-Mail wird automatisch an zugewiesenen Benutzer versendet

### Aktivität als erledigt markieren (löst Mail aus)

**Option 1:** Button im Edit-View
1. Aktivität öffnen (Bearbeiten)
2. Button "Als erledigt markieren" klicken
3. Bestätigen
4. → E-Mail wird automatisch an Ersteller versendet

**Option 2:** Manuell Status ändern
1. Aktivität öffnen (Bearbeiten)
2. Status auf "Erledigt" setzen
3. Speichern
4. → E-Mail wird automatisch an Ersteller versendet

## Konfiguration

### BASE_URL (Optional)

In `settings.py` kann optional BASE_URL konfiguriert werden für absolute URLs in E-Mails:

```python
BASE_URL = 'https://ihre-domain.de'
```

Standard ist `http://localhost:8000`.

### Template-Deaktivierung

Um E-Mail-Benachrichtigungen temporär zu deaktivieren:

1. Admin → E-Mail → Templates
2. Template auswählen
3. Checkbox "Aktiv" deaktivieren
4. Speichern

## Bekannte Einschränkungen

1. **SMTP-Verbindung erforderlich:** E-Mails können nur versendet werden, wenn SMTP konfiguriert ist
2. **E-Mail-Adresse erforderlich:** Benutzer müssen eine E-Mail-Adresse haben
3. **Keine Retry-Logik:** Bei SMTP-Fehlern wird die Mail nicht erneut versendet
4. **Keine Mail-Queue:** Mails werden synchron versendet (könnte bei vielen Aktivitäten langsam sein)

## Zukünftige Erweiterungen (Out of Scope)

- **Mail-Queue:** Asynchroner Versand mit Celery/RQ
- **Benachrichtigungspräferenzen:** Benutzer können Benachrichtigungen deaktivieren
- **Mail-History:** Tracking welche Mails versendet wurden
- **E-Mail-Vorschau:** Preview im UI vor dem Versand
- **Mehrere Empfänger:** CC/BCC Support
- **Erinnerungs-Mails:** Automatische Erinnerungen bei Fälligkeitsdatum

## Sicherheit

### Security Check ✅

CodeQL Security Analysis: **0 Alerts**

### Best Practices

- Templates verwenden Django's Auto-Escaping
- SQL-Injection: N/A (nur Django ORM)
- XSS: Geschützt durch Django Template Engine
- E-Mail-Header-Injection: Geschützt durch Django EmailField Validierung
- Passwörter: Werden in Datenbank gespeichert (Empfehlung: App-Passwörter verwenden)

## Akzeptanzkriterien (DoD)

- [x] Zwei MailTemplates existieren nach Migration in DB (idempotent, keine Duplikate)
- [x] Templates rendern in Outlook korrekt (tabellenbasiert, inline CSS; Links/Buttons klickbar)
- [x] Placeholder-Rendering ersetzt Variablen korrekt; fehlende Variablen verhalten sich deterministisch
- [x] Mail wird beim Erstellen einer Aktivität mit Verantwortlichem versendet (1 Mail)
- [x] Mail wird beim Ändern des Verantwortlichen an den neuen Verantwortlichen versendet (1 Mail; keine Mail an alten)
- [x] Mail wird beim Setzen auf erledigt/geschlossen an den Ersteller versendet (1 Mail)
- [x] "Erledigt"-Button setzt Status und löst Benachrichtigung aus
- [x] Tests vorhanden für: Rendering + Trigger-Transitions (assigned/closed)
- [x] CodeQL Security Check bestanden (0 Alerts)

## Dateien

### Neue Dateien
- `core/migrations/0007_add_activity_mail_templates.py`
- `vermietung/signals.py`
- `vermietung/test_aktivitaet_mail_notifications.py`

### Geänderte Dateien
- `vermietung/apps.py`
- `vermietung/views.py`
- `vermietung/urls.py`
- `templates/vermietung/aktivitaeten/form.html`

## Referenzen

- Issue: #145
- Ähnliche Features:
  - `/items/47/` - feat(core-mail): SMTP + Mail Templates + Rendering
  - `/items/141/` - Aktivitäten / Aufgabenverwaltung (E-Mail-Benachrichtigungen)
  - `/items/42/` - UI-Integration Aktivitäten-Management

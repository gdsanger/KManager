# MailTemplate Model Update - Implementation Summary

## Überblick

Das MailTemplate Model wurde erfolgreich aktualisiert, um den Anforderungen aus dem Issue zu entsprechen.

## Umgesetzte Änderungen

### Model-Felder (core/models.py)

| Altes Feld | Neues Feld | Typ | Beschreibung |
|------------|------------|-----|--------------|
| `key` (CharField) | `key` (SlugField) | SlugField(unique=True) | Technischer Identifier (z.B. issue-created-confirmation) |
| `message_html` | `message` | TextField | Inhalt der E-Mail (Markdown oder HTML, Platzhalter erlaubt) |
| `cc_copy_to` | `cc_address` | EmailField(blank=True) | Optionale CC-Adresse |
| - | `is_active` | BooleanField(default=True) | Template aktiv/deaktiviert |
| - | `created_at` | DateTimeField(auto_now_add=True) | Erstellungszeitpunkt |
| - | `updated_at` | DateTimeField(auto_now=True) | Letzte Änderung |
| `from_name` | `from_name` | CharField(blank=True) | Absendername (jetzt optional) |
| `from_address` | `from_address` | EmailField(blank=True) | Absenderadresse (jetzt optional) |

### Neue Features

#### 1. Template-Aktivierung/Deaktivierung
- Templates können über `is_active` aktiviert/deaktiviert werden
- Inaktive Templates können nicht zum E-Mail-Versand verwendet werden
- `send_mail()` prüft automatisch den Status und wirft einen `MailServiceError` bei inaktiven Templates

#### 2. Automatische Zeitstempel
- `created_at` wird beim Erstellen automatisch gesetzt
- `updated_at` wird bei jeder Änderung automatisch aktualisiert

#### 3. Optionale Absenderfelder mit Fallback
- `from_name` und `from_address` sind jetzt optional (blank=True)
- Bei leeren Feldern wird automatisch auf `settings.DEFAULT_FROM_EMAIL` und `settings.DEFAULT_FROM_NAME` zurückgegriffen

#### 4. SlugField für Template-Keys
- Keys sind jetzt SlugFields (URL-sicher)
- Empfohlenes Format: `issue-created-confirmation` (Bindestriche statt Unterstriche)

### Admin-Interface (core/admin.py)

**Aktualisierungen:**
- List View zeigt nun `is_active` Status
- Filter nach `is_active` hinzugefügt
- Zeitstempel (`created_at`, `updated_at`) als readonly_fields
- Strukturierte Fieldsets:
  - Grunddaten (key, subject, message, is_active)
  - Absender (from_name, from_address, cc_address)
  - Zeitstempel (created_at, updated_at) - standardmäßig eingeklappt

### Mailing Service (core/mailing/service.py)

**Neue Validierungen:**
1. **is_active Prüfung:** Templates müssen aktiv sein zum Versenden
2. **Sender-Fallback:** Leere Sender-Felder werden durch Defaults ersetzt

```python
# Beispiel: Versand mit inaktivem Template
template.is_active = False
template.save()

send_mail('template-key', ['user@example.com'], {})
# Wirft: MailServiceError: "Mail-Template 'template-key' ist deaktiviert."
```

### Tests

**Neue Tests hinzugefügt:**
- `test_is_active_default()` - Prüft, dass is_active standardmäßig True ist
- `test_timestamps()` - Prüft, dass created_at und updated_at gesetzt werden
- `test_optional_sender_fields()` - Prüft, dass Sender-Felder optional sind
- `test_inactive_template()` - Prüft, dass inaktive Templates nicht versendet werden können
- `test_template_with_empty_sender_uses_defaults()` - Prüft Fallback auf Defaults

**Test-Ergebnisse:**
```
Ran 78 tests in 26.496s
OK
```

Alle Tests bestanden erfolgreich.

### Migration

**Migration:** `0006_update_mailtemplate_fields.py`

Die Migration führt folgende Änderungen durch:
1. Umbenennung `message_html` → `message`
2. Umbenennung `cc_copy_to` → `cc_address`
3. Hinzufügen von `is_active` (default=True)
4. Hinzufügen von `created_at` (mit timezone.now als Default für existierende Einträge)
5. Hinzufügen von `updated_at`
6. Änderung `key` von CharField zu SlugField
7. Aktualisierung der Verbose Names und Help Texts
8. `from_name` und `from_address` als optional markieren

### Dokumentation

**Aktualisiert:** `CORE_MAIL_DOCUMENTATION.md`
- Neue Feldstruktur dokumentiert
- Beispiele mit neuen Feldnamen aktualisiert
- Neue Features (is_active, Zeitstempel, Fallbacks) dokumentiert
- Empfehlung für SlugField-Format (Bindestriche)

## Akzeptanzkriterien

✅ **Model ist migriert und im Admin pflegbar**
- Migration erfolgreich erstellt und getestet
- Admin-Interface zeigt alle Felder korrekt an
- Fieldsets strukturiert und benutzerfreundlich

✅ **key ist eindeutig**
- SlugField mit unique=True
- Datenbank-Constraint verhindert Duplikate

✅ **Templates können aktiviert/deaktiviert werden**
- `is_active` Boolean-Feld implementiert
- Admin zeigt Status in List View
- Filter nach Aktivierungsstatus verfügbar
- Versand prüft is_active und verhindert Nutzung inaktiver Templates

✅ **Keine Abhängigkeit zu Issue-, Status- oder Mail-Logik**
- Model ist eigenständig
- Keine Foreign Keys zu anderen Models
- Nur grundlegende E-Mail-Template-Verwaltung

## Rahmenbedingungen erfüllt

✅ **Kein Versand** - Model speichert nur Templates, Versand erfolgt über separaten Service
✅ **Kein Mapping** - Nur Template-Speicherung, keine Event-Mappings
✅ **Keine Versionierung** - Nur aktuelle Version gespeichert
✅ **Keine Mehrsprachigkeit** - Ein Template pro Sprache
✅ **Platzhalter werden nur gespeichert** - Keine automatische Auswertung im Model

## Sicherheit

**CodeQL Analyse:** 0 Alerts
- Keine Sicherheitsprobleme gefunden
- Alle Input-Validierungen korrekt implementiert
- Django's Auto-Escaping schützt vor XSS

## Verwendungsbeispiel

```python
# Template erstellen
from core.models import MailTemplate

template = MailTemplate.objects.create(
    key='issue-created-confirmation',
    subject='Issue {{ issue_id }} wurde erstellt',
    message='<h1>Hallo {{ user_name }}</h1><p>Ihr Issue {{ issue_id }} wurde erfolgreich erstellt.</p>',
    from_name='KManager',
    from_address='noreply@kmanager.de',
    is_active=True
)

# Template verwenden
from core.mailing.service import send_mail

send_mail(
    'issue-created-confirmation',
    ['user@example.com'],
    {
        'user_name': 'Max Mustermann',
        'issue_id': '#123'
    }
)

# Template deaktivieren
template.is_active = False
template.save()

# Versand mit deaktiviertem Template führt zu Fehler
try:
    send_mail('issue-created-confirmation', ['user@example.com'], {})
except MailServiceError as e:
    print(f"Fehler: {e}")  # "Mail-Template 'issue-created-confirmation' ist deaktiviert."
```

## Erweiterungsmöglichkeiten (außerhalb des Scopes)

Die aktuelle Implementierung bildet eine solide Grundlage für zukünftige Erweiterungen:

1. **Mapping:** Event-Handler könnten Templates bei bestimmten Events auslösen
2. **AI-Generierung:** Templates könnten durch AI generiert/optimiert werden
3. **Approval-Workflow:** Templates könnten einen Review-Prozess durchlaufen
4. **Versionierung:** Template-Historie könnte gespeichert werden
5. **Mehrsprachigkeit:** Mehrere Versionen pro Template für verschiedene Sprachen

## Zusammenfassung

Die Implementierung erfüllt alle Anforderungen aus dem Issue:
- ✅ Einfache Pflege durch strukturiertes Admin-Interface
- ✅ Wiederverwendbarkeit durch eindeutige Keys
- ✅ Erweiterbarkeit durch klare Struktur und optionale Felder
- ✅ Keine Abhängigkeiten zu komplexeren Systemen
- ✅ Alle Tests bestanden
- ✅ Keine Sicherheitsprobleme

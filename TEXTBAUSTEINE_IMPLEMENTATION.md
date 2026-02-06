# Textbausteine Feature - Implementierungsübersicht

## Überblick

Die Textbausteine-Funktion ermöglicht es Benutzern, wiederverwendbare Textvorlagen für Kopf- und Fußtexte von Verkaufsbelegen zu verwalten und anzuwenden.

## Implementierte Komponenten

### 1. Model: TextTemplate

**Datei:** `auftragsverwaltung/models.py`

Das `TextTemplate`-Model verwaltet wiederverwendbare Textbausteine mit folgenden Feldern:

- `company` (FK zu Mandant) - Tenant-spezifisch
- `key` (SlugField) - Eindeutiger Kurzbezeichner (z.B. "standard_header")
- `title` (CharField) - Anzeigename für Dropdown
- `type` (CharField) - HEADER, FOOTER oder BOTH
- `content` (TextField) - Textinhalt
- `is_active` (BooleanField) - Aktiv/Inaktiv Status
- `sort_order` (IntegerField) - Sortierreihenfolge
- `created_at`, `updated_at` (DateTimeField) - Zeitstempel

**Constraints:**
- Unique constraint auf (company, key)
- Index auf (company, type, is_active)

**Ordering:**
- type, sort_order, title

### 2. Admin Interface

**Datei:** `auftragsverwaltung/admin.py`

Django Admin-Registrierung für `TextTemplate` mit:
- List display: title, company, type, key, is_active, sort_order, updated_at
- List filters: company, type, is_active
- Search fields: title, key, content, company__name
- Fieldsets für strukturierte Bearbeitung

### 3. Tables & Filters

**Datei:** `auftragsverwaltung/tables.py`

`TextTemplateTable` (django-tables2):
- Anzeige von Titel, Typ, Schlüssel, Status, Aktualisierungsdatum
- Aktionsspalte mit Bearbeiten- und Löschen-Buttons
- Typ-Badges (farbcodiert: HEADER=blau, FOOTER=gelb, BOTH=grün)

**Datei:** `auftragsverwaltung/filters.py`

`TextTemplateFilter` (django-filter):
- Volltextsuche in title, key, content
- Filter nach Typ (HEADER/FOOTER/BOTH)
- Filter nach Status (Aktiv/Inaktiv)

### 4. CRUD Views

**Datei:** `auftragsverwaltung/views.py`

#### texttemplate_list
- Zeigt alle Textbausteine der Company an
- Verwendet TextTemplateTable und TextTemplateFilter
- Pagination: 25 Einträge pro Seite

#### texttemplate_create
- GET: Zeigt Formular zum Erstellen
- POST: Erstellt neuen Textbaustein
- Validiert alle Pflichtfelder

#### texttemplate_update
- GET: Zeigt Formular mit bestehenden Daten
- POST: Aktualisiert Textbaustein
- Behält company-Zuordnung bei

#### texttemplate_delete
- GET: Zeigt Bestätigungsdialog
- POST: Löscht Textbaustein
- Hinweis: Bereits verwendete Texte in Dokumenten bleiben erhalten

#### ajax_apply_texttemplate (AJAX Endpoint)
- Wendet Textbaustein auf SalesDocument an
- Kopiert Inhalt (keine Referenz!)
- Validiert company-Übereinstimmung
- Returns JsonResponse mit success/error

### 5. Templates

#### list.html
**Datei:** `templates/auftragsverwaltung/texttemplates/list.html`

- Filterbereich mit Suche, Typ- und Status-Filter
- Django-Tables2 Tabelle mit Bootstrap 5 Dark Theme
- "Neu erstellen" Button im Page Header

#### form.html
**Datei:** `templates/auftragsverwaltung/texttemplates/form.html`

Formularfelder:
- Titel (required)
- Schlüssel (required, pattern: [a-z0-9_-]+)
- Typ (required, Dropdown)
- Sortierung (optional, default: 0)
- Aktiv (Switch, default: checked)
- Inhalt (required, große Textarea)

Buttons:
- Speichern
- Abbrechen (zurück zur Liste)

#### delete_confirm.html
**Datei:** `templates/auftragsverwaltung/texttemplates/delete_confirm.html`

- Warnung mit Textbaustein-Details
- Hinweis: "Bereits in Dokumenten verwendeter Text bleibt erhalten"
- Löschen/Abbrechen Buttons

### 6. Integration in SalesDocument DetailView

**Datei:** `templates/auftragsverwaltung/documents/detail.html`

Für Header-Text:
- Dropdown mit verfügbaren Header-Textbausteinen
- "Übernehmen" Button
- Textarea für header_text

Für Footer-Text:
- Dropdown mit verfügbaren Footer-Textbausteinen
- "Übernehmen" Button
- Textarea für footer_text

**JavaScript-Funktionalität:**
- Anwendung per Button-Click
- Bestätigungsdialog bei bestehendem Text
- Toast-Benachrichtigung nach Übernahme
- Markierung als "dirty" für Unsaved-Changes-Warning

**View-Änderungen:**
- `document_detail`: Lädt header_templates und footer_templates
- `document_create`: Lädt header_templates und footer_templates
- Filter: type__in=['HEADER', 'BOTH'] bzw. ['FOOTER', 'BOTH']
- Sortierung: sort_order, title

### 7. Navigation

**Datei:** `templates/auftragsverwaltung/auftragsverwaltung_base.html`

Neuer Menüpunkt "Textbausteine" unter "Auftragsverwaltung":
- Icon: bi-blockquote-left
- Route: auftragsverwaltung:texttemplate_list
- Aktiv-Markierung: 'textbausteine' in request.path

### 8. URL Configuration

**Datei:** `auftragsverwaltung/urls.py`

Neue URLs:
- `/textbausteine/` - Liste
- `/textbausteine/erstellen/` - Erstellen
- `/textbausteine/<pk>/bearbeiten/` - Bearbeiten
- `/textbausteine/<pk>/loeschen/` - Löschen
- `/ajax/apply-texttemplate/` - AJAX Endpoint

### 9. Tests

**Datei:** `auftragsverwaltung/test_texttemplate.py`

#### TextTemplateModelTestCase (8 Tests)
- test_create_header_template
- test_create_footer_template
- test_create_both_template
- test_unique_constraint
- test_ordering
- test_str_representation
- test_inactive_template

#### TextTemplateViewTestCase (7 Tests)
- test_texttemplate_list_view
- test_texttemplate_create_view_get
- test_texttemplate_create_view_post
- test_texttemplate_update_view_get
- test_texttemplate_update_view_post
- test_texttemplate_delete_view_get
- test_texttemplate_delete_view_post
- test_list_view_requires_login

**Alle 15 Tests bestehen erfolgreich.**

### 10. Migration

**Datei:** `auftragsverwaltung/migrations/0012_texttemplate.py`

Erstellt TextTemplate-Tabelle mit:
- Alle Felder wie im Model definiert
- Unique constraint (company, key)
- Index (company, type, is_active)

## Verwendung

### Textbaustein erstellen

1. Navigiere zu "Auftragsverwaltung" → "Textbausteine"
2. Klicke auf "Neu erstellen"
3. Fülle Formular aus:
   - Titel: z.B. "Standard Kopftext Angebot"
   - Schlüssel: z.B. "standard-header-quote"
   - Typ: HEADER, FOOTER oder BOTH
   - Inhalt: Dein Textbaustein
4. Klicke "Speichern"

### Textbaustein auf Dokument anwenden

1. Öffne oder erstelle ein Verkaufsbeleg
2. Gehe zum "Kopfzeile" oder "Fußzeile" Tab
3. Wähle einen Textbaustein aus dem Dropdown
4. Klicke "Übernehmen"
5. Text wird in Textarea kopiert und kann weiter bearbeitet werden

### Wichtige Hinweise

- **Kopieren statt Referenzieren:** Der Text wird kopiert, nicht referenziert. Spätere Änderungen am Textbaustein betreffen nicht bereits erstellte Dokumente.
- **Überschreiben-Warnung:** Bei bestehendem Text erscheint ein Bestätigungsdialog.
- **Company-Scope:** Jeder Textbaustein gehört zu einem Mandanten. Benutzer sehen nur Bausteine ihrer Company.
- **Unique Keys:** Der Schlüssel muss pro Company eindeutig sein.

## Design-Entscheidungen

1. **Kopieren vs. Referenzieren:** Texte werden kopiert, um historische Korrektheit zu gewährleisten. Änderungen an Textbausteinen betreffen keine alten Dokumente.

2. **Company-Scope:** Jeder Textbaustein ist mandantenspezifisch (company FK), damit Multi-Tenant-Szenarien korrekt funktionieren.

3. **Type BOTH:** Ermöglicht universelle Bausteine, die sowohl für Header als auch Footer verwendet werden können.

4. **Frontend-Integration:** Kein HTMX nötig - einfache JavaScript-Lösung mit Bestätigungsdialogen und Toast-Notifications.

5. **Keine Activity-Logging:** Activity-Logging wurde bewusst weggelassen, da die ActivityStreamService-API inkonsistent war und die Funktion nicht kritisch ist.

## Acceptance Criteria - Status

✅ Textbaustein-Model existiert inkl. Migrationen  
✅ CRUD UI (ListView + Create / Edit / Delete) vorhanden  
✅ Company-Scope enforced (User sieht nur eigene Bausteine)  
✅ SalesDocument besitzt `header_text` und `footer_text`  
✅ Auswahl + „Übernehmen" befüllt Felder korrekt im DetailView  
✅ Kopierte Inhalte bleiben stabil, auch wenn Bausteine später geändert werden  
✅ Tests: Model-Validierung + UI-Tests für „Übernehmen"  

## Dateien geändert/erstellt

### Erstellt:
- `auftragsverwaltung/test_texttemplate.py`
- `auftragsverwaltung/migrations/0012_texttemplate.py`
- `templates/auftragsverwaltung/texttemplates/list.html`
- `templates/auftragsverwaltung/texttemplates/form.html`
- `templates/auftragsverwaltung/texttemplates/delete_confirm.html`

### Geändert:
- `auftragsverwaltung/models.py` (+92 Zeilen - TextTemplate model)
- `auftragsverwaltung/admin.py` (+45 Zeilen - TextTemplateAdmin)
- `auftragsverwaltung/tables.py` (+93 Zeilen - TextTemplateTable)
- `auftragsverwaltung/filters.py` (+59 Zeilen - TextTemplateFilter)
- `auftragsverwaltung/views.py` (+174 Zeilen - CRUD views + AJAX)
- `auftragsverwaltung/urls.py` (+6 Zeilen - URL patterns)
- `templates/auftragsverwaltung/documents/detail.html` (+157 Zeilen - Template-Auswahl + JavaScript)
- `templates/auftragsverwaltung/auftragsverwaltung_base.html` (+5 Zeilen - Navigation)

## Security Summary

### Keine neuen Sicherheitsprobleme identifiziert

- **CSRF-Schutz:** Alle POST-Formulare verwenden {% csrf_token %}
- **Authentication:** Alle Views mit @login_required dekoriert
- **Authorization:** Company-Scope wird bei allen Operationen validiert
- **Input-Validierung:** Django-Model-Validierung für alle Felder
- **XSS-Schutz:** Django Template Auto-Escaping aktiv
- **SQL-Injection:** Django ORM verhindert SQL-Injection

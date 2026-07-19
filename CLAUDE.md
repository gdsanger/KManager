# CLAUDE.md

Diese Datei gibt Claude Code (und anderen KI-Coding-Agenten) die wichtigsten
Informationen und Regeln für die Arbeit an diesem Repository. Bitte **vor jeder
Aufgabe** lesen und die hier definierten Konventionen einhalten.

> Privates Projekt von **Christian Angermeier / Perculasoft e.K.**
> Keine ISO-Zertifizierung erforderlich, aber die Praktiken orientieren sich
> an gängigen Standards (saubere Migrationen, Tests, Security by default).

---

## 1. Projektüberblick

**KManager** (intern teilweise als *„Domus"* bezeichnet) ist eine modulare
**Vermietungs- und ERP-Plattform** auf Basis von Django. Sie deckt ab:

- **Vermietung**: Mietobjekte (hierarchisch: Gebäude → Etage → Einheit),
  Verträge, Übergabeprotokolle, Zähler, Verfügbarkeiten, Aktivitäten/CRM,
  Dokumentenverwaltung, Eingangsrechnungen (inkl. KI-gestützter Extraktion).
- **Auftragsverwaltung**: Kunden, Artikel/Artikelgruppen, Angebote/Aufträge/
  Rechnungen (SalesDocuments), Positionen, Nummernkreise, Steuer-/Preislogik,
  PDF-Druck.
- **Finanzen**: Journale, Reporting (Phase 2, im Aufbau).
- **Lieferantenwesen**: Lieferanten, zugehörige Workflows.
- **Core**: Mandanten (Multi-Tenant), Adressen/Kontakte, Kostenarten,
  Steuersätze, Zahlungsziele, Mail-Templates/Versand, Activity-Stream,
  Druck-Framework, KI-Service.

Sprache der Domäne und UI: **Deutsch**. Code-Kommentare/Docstrings gemischt
(überwiegend Deutsch/Englisch). Fachbegriffe im Code sind deutsch benannt
(z. B. `Mietobjekt`, `Vertrag`, `Eingangsrechnung`, `Aktivitaet`).

> Hinweis: `README.md` und `docs/architecture.md` beschreiben teilweise eine
> **geplante/idealisierte** App-Struktur (`parties/`, `assets/`, `contracts/` …),
> die so **nicht** umgesetzt wurde. Maßgeblich ist die tatsächliche Struktur
> unten in Abschnitt 3.

---

## 2. Tech-Stack

| Bereich      | Technologie |
|--------------|-------------|
| Sprache      | Python **3.12.8** (siehe `.python-version`) |
| Framework    | **Django ≥5.2,<5.3** |
| Frontend     | **HTMX**, **Bootstrap 5.3** (Dark Mode), Bootstrap Icons, **Quill** (WYSIWYG) |
| Tabellen/Filter | `django-tables2`, `django-filter` |
| Datenbank    | **PostgreSQL** (Prod), **SQLite** Fallback (Dev/Test) |
| PDF          | **WeasyPrint**, **reportlab**, `pypdf` |
| Mail         | Django-Mail + eigenes Mail-Template-/Versand-Framework (`core/mailing/`) |
| KI           | `openai`, `google-generativeai` (u. a. Rechnungs-Extraktion) |
| Sanitizing   | `bleach` (HTML aus Quill absichern) |
| Monitoring   | `sentry-sdk` (optional, nur wenn `SENTRY_DSN` gesetzt) |
| Sonstiges    | `python-dotenv`, `Pillow`, `python-magic`, `python-dateutil`, `django-extensions` |

Abhängigkeiten: `requirements.txt` (Python), `package.json` (nur Quill via npm).

---

## 3. Projekt- & App-Struktur

Django-Projektpaket: **`kmanager/`** (`settings.py`, `urls.py`, `wsgi.py`,
`asgi.py`). Root-`URLconf`: `kmanager.urls`.

Tatsächliche Django-Apps (in `INSTALLED_APPS`):

```
core/                # Basis: Mandant, Adresse/Kontakt, Kostenart, Steuersatz,
                     #   Zahlungsziel, Artikel/Artikelgruppe, Mail, Activity-Stream,
                     #   Druck-Framework, KI-Service
vermietung/          # Mietobjekte, Verträge, Übergabeprotokolle, Zähler,
                     #   Aktivitäten, Dokumente, Eingangsrechnungen, Dashboard
auftragsverwaltung/  # Kunden, SalesDocuments (Angebot/Auftrag/Rechnung),
                     #   Positionen, Nummernkreise, Steuer-/Preislogik, PDF
finanzen/            # Journale, Finanz-Reporting (im Aufbau)
lieferantenwesen/    # Lieferanten + Workflows
```

Weitere Verzeichnisse:

```
kmanager/            # Projekt-Settings & Root-URLs
templates/           # Projektweite Templates (base.html etc.)
static/              # Quell-Assets (CSS in static/css/site.css), collectstatic → staticfiles/
reports/             # Report-Templates
docs/                # Ergänzende Doku (architecture.md, development.md, setup.md, ...)
data/                # Datei-Uploads (git-ignoriert): VERMIETUNG_DOCUMENTS_ROOT, PROJECT_DOCUMENTS_ROOT
logs/                # Log-Ausgaben (git-ignoriert)
*.md (Root)          # Historische Feature-/Fix-/Security-Zusammenfassungen (Referenz)
```

Typischer App-Aufbau: `models.py`, `views.py`, `urls.py`, `forms.py`,
`admin.py`, `tables.py`, `filters.py`, `services/` bzw. `services.py`,
`printing/`, `mailing/`, `management/commands/`, `migrations/`, `templates/`,
und **viele `test_*.py`** direkt in der App.

URL-Einstiegspunkte (`kmanager/urls.py`): `admin/`, `login/`, `logout/`,
Password-Reset, `vermietung/`, `auftragsverwaltung/`, `lieferantenwesen/`,
`''` → `core.urls`.

---

## 4. Setup & Umgebung

```bash
# 1) Virtuelle Umgebung
python -m venv venv && source venv/bin/activate

# 2) Abhängigkeiten
pip install -r requirements.txt

# 3) Umgebungsvariablen
cp .env.example .env        # danach Werte anpassen

# 4) Migrationen
python manage.py migrate

# 5) Superuser (optional)
python manage.py createsuperuser

# 6) Dev-Server
python manage.py runserver   # http://localhost:8000  (Admin: /admin)
```

**Datenbank-Logik** (siehe `kmanager/settings.py`): Ist `DB_NAME` gesetzt,
wird **PostgreSQL** verwendet, sonst automatisch **SQLite** (`db.sqlite3`).
Für lokale Entwicklung reicht daher SQLite (kein `DB_NAME` in `.env`).

Wichtige Env-Variablen (`.env.example`): `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, `DB_*`, `SENTRY_DSN`, `AGIRA_TOKEN`, `BASE_URL`,
Mail (`EMAIL_*`, `DEFAULT_FROM_EMAIL`). **Niemals** echte Secrets committen –
`.env` ist git-ignoriert.

---

## 5. Häufige Befehle

```bash
# Server
python manage.py runserver

# Migrationen
python manage.py makemigrations
python manage.py migrate
python manage.py showmigrations

# Tests (in-memory SQLite – unabhängig von einer evtl. konfigurierten Postgres-DB)
python manage.py test --settings=test_settings
python manage.py test core --settings=test_settings          # nur eine App
python manage.py test vermietung.test_vertrag_crud --settings=test_settings  # nur ein Modul

# Django-Shell / Checks
python manage.py shell
python manage.py check

# Static Files (Prod)
python manage.py collectstatic
```

> **Tests immer mit `--settings=test_settings`** (oder
> `--settings=kmanager.test_settings`) laufen lassen. Beide nutzen in-memory
> SQLite; `test_settings` setzt zusätzlich `ALLOWED_HOSTS=['*']`.

---

## 6. Test-Konventionen

- Framework: **Django `TestCase`** (kein pytest konfiguriert).
- Tests liegen als `test_*.py` **direkt in der jeweiligen App** (nicht in einem
  separaten `tests/`-Ordner). Beispiele: `vermietung/test_vertrag_crud.py`,
  `auftragsverwaltung/test_document_calculation.py`, `core/test_mail_service.py`.
- **Jede Änderung am Domänenmodell** wird begleitet von: Migration(en),
  passenden Tests und ggf. kurzer Doku-Anpassung.
- Neue Features / Bugfixes: **Tests hinzufügen oder erweitern** und lokal grün
  laufen lassen, bevor ein PR erstellt wird.
- Vor jedem PR mindestens: `python manage.py test --settings=test_settings`
  (oder gezielt die betroffenen Apps) + `python manage.py makemigrations --check`.

---

## 7. Code-Style & Konventionen

- **Python**: PEP 8, Type Hints wo sinnvoll, Docstrings für Funktionen/Klassen.
- **Domänensprache Deutsch**: Neue Modelle/Felder in der etablierten deutschen
  Terminologie benennen (konsistent mit Bestandscode).
- **Templates**: Django Template-Tags, 4 Spaces Einrückung, semantisches HTML5.
  HTMX-Teilantworten als eigene Partial-Templates (`templates/.../partials/`).
- **CSS**: keine Inline-Styles; zentrale Styles in `static/css/site.css`,
  CSS-Variablen, Mobile-First. Bootstrap 5.3 (Dark Theme).
- **HTMX**: `hx-get`/`hx-post` + `hx-target`/`hx-swap`; bei POST `{% csrf_token %}`
  nicht vergessen; `htmx-indicator` für Ladezustände.
- **Performance**: N+1 vermeiden (`select_related` / `prefetch_related`).
- **HTML-Eingaben** (Quill etc.) **immer mit `bleach` sanitizen**, bevor sie
  gespeichert oder in PDFs/Mails gerendert werden.
- **Migrationen**: bei Modelländerungen erzeugen und committen; niemals
  Migrationsdateien manuell „von Hand" inkonsistent lassen.

---

## 8. Git-Workflow — WICHTIG

Diese Regeln sind für dieses Repo **verbindlich**:

1. **Kein direkter Push auf `main`.** Auf `main` (und `master`) wird niemals
   direkt gepusht oder committet.
2. **Immer auf einem Feature-Branch arbeiten.** Branch von aktuellem `main`
   abzweigen. Namenskonvention (konsistent mit der Repo-Historie):

   ```
   claude/<kurze-kebab-beschreibung>     # z. B. claude/fix-vertrag-datum-validierung
   ```

3. **Nach erfolgreich abgeschlossener Aufgabe** (Code fertig, Tests grün) einen
   **Draft Pull Request** gegen `main` erstellen — **kein direkter Merge**.
   Der Merge nach `main` erfolgt bewusst über GitHub (PR-Review).
4. **Commits**: kleine, thematisch fokussierte Commits. Commit-Message-Format:

   ```
   <type>: <kurzbeschreibung>
   ```
   Typen: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.

Typischer Ablauf:

```bash
git checkout main && git pull
git checkout -b claude/<beschreibung>
# ... Änderungen + Tests ...
python manage.py test --settings=test_settings
git add -A && git commit -m "feat: <beschreibung>"
git push -u origin claude/<beschreibung>
# Draft-PR erstellen:
gh pr create --draft --base main --fill      # oder Web-Link nutzen
```

> **Schutzmechanismus:** Im Repo liegt ein `pre-push`-Hook unter `.githooks/`,
> der direkte Pushes auf `main`/`master` **blockt**. Einmalig aktivieren mit:
> `git config core.hooksPath .githooks`

---

## 9. Sicherheit & Datenschutz

- **Secrets** ausschließlich über `.env` / Environment; nie im Code oder in
  Commits. `SECRET_KEY`, DB-Credentials, API-Keys (OpenAI/Gemini), Mail-Login.
- `DEBUG=False` in Produktion; `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` pflegen.
- Django-Bordmittel nutzen: CSRF-Schutz, ORM (kein Roh-SQL), Template-
  Auto-Escaping. Zusätzlich **`bleach`** für erlaubtes HTML.
- **Multi-Tenant/Mandant**: fachliche Daten sind mandantenbezogen — beim
  Erweitern von Queries/Views auf korrektes Tenant-Scoping achten.
- Datei-Uploads liegen unter `data/` (git-ignoriert); Dateitypen werden u. a.
  via `python-magic` geprüft.

---

## 10. Nützliche Referenzen

- `docs/setup.md` — ausführliche Setup-Anleitung
- `docs/development.md` — Entwicklungs-Guide (Django/HTMX/Bootstrap)
- `docs/architecture.md` — Architektur (teils geplanter Stand, s. Hinweis oben)
- `docs/AUTH_VERMIETUNG.md`, `docs/DOKUMENT_VERWALTUNG.md`,
  `docs/PRINTING_FRAMEWORK.md`, `docs/AVAILABILITY_MANAGEMENT.md` u. a.
- Zahlreiche `*_IMPLEMENTATION.md` / `*_SECURITY_SUMMARY.md` im Root
  dokumentieren einzelne Features/Fixes historisch — als Kontext hilfreich,
  aber nicht immer aktuell.

---

## 11. Kurz-Checkliste vor jedem PR

- [ ] Auf Feature-Branch (`claude/…`), **nicht** auf `main`
- [ ] Migrationen erzeugt & committed (`makemigrations --check` sauber)
- [ ] Tests grün: `python manage.py test --settings=test_settings`
- [ ] Keine Secrets / keine `.env` im Diff
- [ ] Kurze Doku-/README-Anpassung, falls Domäne/Verhalten geändert
- [ ] **Draft PR** gegen `main` erstellt (kein direkter Merge/Push auf main)

# Core Report Service

Zentrale Infrastruktur für die generische Erzeugung, Versionierung und Ablage von PDF-Reports.

## Übersicht

Der Core Report Service bietet eine einheitliche, wiederverwendbare Lösung für die PDF-Generierung im System. Er trennt die technische Report-Engine von der fachlichen Report-Logik und ermöglicht ISO-konforme Nachvollziehbarkeit durch Snapshots und Versionierung.

## Architektur

```
core/
  services/
    reporting/
      service.py      # Core ReportService
      registry.py     # Template-Registry
      styles.py       # PDF-Styles
      canvas.py       # Header/Footer-Helpers
reports/
  templates/
    change_v1.py      # Beispiel: Change-Report
```

## Features

- ✅ PDF-Rendering mit ReportLab Platypus
- ✅ Template-basierte Report-Generierung
- ✅ Versionierung und Audit-Trail
- ✅ Persistenz mit Context-Snapshot
- ✅ Multi-Page-Support mit Header/Footer
- ✅ Seitenzahlen "Seite X von Y"
- ✅ SHA256-Hash für Integrität
- ✅ Wiederholbare Generierung

## Verwendung

### 1. Einfache PDF-Generierung

```python
from core.services.reporting import ReportService

context = {
    'title': 'Change Report',
    'change_id': 'CHG-001',
    'date': '2024-01-31',
    'description': 'Änderungsbericht',
    'items': [
        {'position': '1', 'description': 'Änderung 1', 'status': 'Erledigt'},
        {'position': '2', 'description': 'Änderung 2', 'status': 'In Arbeit'},
    ],
}

# PDF als Bytes generieren
pdf_bytes = ReportService.render('change.v1', context)

# In Datei speichern
with open('report.pdf', 'wb') as f:
    f.write(pdf_bytes)
```

### 2. Report generieren und speichern

```python
from core.services.reporting import ReportService

report = ReportService.generate_and_store(
    report_key='change.v1',
    object_type='change',
    object_id='CHG-001',
    context=context,
    metadata={'version': '1.0'},
    created_by=request.user
)

# Report-ID
print(f"Report ID: {report.id}")

# PDF-Pfad
print(f"PDF: {report.pdf_file.url}")

# SHA256-Hash
print(f"Hash: {report.sha256}")
```

### 3. Reports abfragen

```python
from core.models import ReportDocument

# Alle Reports eines Typs
reports = ReportDocument.objects.filter(report_key='change.v1')

# Reports für ein bestimmtes Objekt
reports = ReportDocument.objects.filter(
    object_type='change',
    object_id='CHG-001'
)

# Letzter Report
latest_report = ReportDocument.objects.filter(
    object_type='change',
    object_id='CHG-001'
).first()
```

## Eigene Report-Templates erstellen

### 1. Template-Klasse erstellen

```python
# reports/templates/invoice_v1.py
from reportlab.platypus import Paragraph, Spacer, Table
from reportlab.lib.units import cm

from core.services.reporting.registry import register_template
from core.services.reporting.styles import get_default_styles, get_table_style


@register_template('invoice.v1')
class InvoiceReportV1:
    """Rechnungs-Report Template"""
    
    def build_story(self, context):
        """
        Baut den Report-Inhalt.
        
        Args:
            context: Dict mit Report-Daten
            
        Returns:
            Liste von ReportLab Flowables
        """
        story = []
        styles = get_default_styles()
        
        # Titel
        story.append(Paragraph(
            f"Rechnung {context['invoice_number']}", 
            styles['ReportHeader']
        ))
        
        # Inhalt...
        
        return story
    
    def draw_header_footer(self, canvas, doc, context):
        """
        Zeichnet Header und Footer auf jeder Seite.
        
        Optional - wenn nicht implementiert, wird Standard-Header/Footer verwendet.
        """
        from core.services.reporting.canvas import draw_standard_header_footer
        draw_standard_header_footer(canvas, doc, context)
```

### 2. Template registrieren

Das Template wird automatisch beim Import registriert. Fügen Sie es zur `reports/__init__.py` hinzu:

```python
# reports/__init__.py
from reports.templates import change_v1
from reports.templates import invoice_v1  # Neu
```

### 3. Template verwenden

```python
pdf_bytes = ReportService.render('invoice.v1', context)
```

## ReportDocument Model

Das `ReportDocument`-Model speichert alle generierten Reports:

```python
class ReportDocument(models.Model):
    report_key = models.CharField(...)       # z.B. 'change.v1'
    object_type = models.CharField(...)      # z.B. 'change'
    object_id = models.CharField(...)        # z.B. 'CHG-001'
    created_at = models.DateTimeField(...)   # Erstellungszeitpunkt
    created_by = models.ForeignKey(User...)  # Ersteller
    context_json = models.JSONField(...)     # Snapshot der Daten
    pdf_file = models.FileField(...)         # PDF-Datei
    template_version = models.CharField(...) # Template-Version
    sha256 = models.CharField(...)           # SHA256-Hash des PDFs
    metadata = models.JSONField(...)         # Zusätzliche Metadaten
```

## Verfügbare Templates

- **change.v1**: Change-Report mit Tabelle von Änderungen

## Styles und Layout

### Verfügbare Styles

```python
from core.services.reporting.styles import get_default_styles

styles = get_default_styles()
# Verfügbar:
# - ReportHeader
# - ReportSubHeader
# - ReportBody
# - ReportFooter
# - TableHeader
# - TableCell
```

### Table-Style

```python
from core.services.reporting.styles import get_table_style

table = Table(data)
table.setStyle(get_table_style())
```

### Seitenlayout

- **Format**: A4
- **Ränder**: 2 cm (links/rechts), 2.5 cm (oben/unten)
- **Header**: Linie am oberen Rand
- **Footer**: Linie + Seitenzahl "Seite X von Y"

## Tests

Tests ausführen:

```bash
python manage.py test core.test_report_service
```

Demo-Script ausführen:

```bash
python demo_report_service.py
```

Das Demo-Script zeigt:
- Template-Listing
- Einfache Report-Generierung
- Multi-Page-Reports
- Report-Speicherung mit Context-Snapshot
- Report-Abfragen
- Reproduzierbarkeit

## Beispiel-PDFs

Nach Ausführung des Demo-Scripts:
- `/tmp/demo_simple_report.pdf` - Einfacher Report
- `/tmp/demo_multipage_report.pdf` - Mehrseitiger Report

## Technische Details

### PDF-Engine
- **ReportLab Platypus** für Layouting
- **SimpleDocTemplate** für A4-Dokumente
- **Table** mit `repeatRows` für Seitenumbrüche
- **Flowables** für flexible Inhalte

### Template-Registry
- Keine If/Else-Logik im Service
- Decorator-basierte Registrierung
- Lazy-Loading der Templates
- Auto-Import via Django App-Config

### Persistenz
- FileField mit strukturiertem Upload-Pfad: `reports/%Y/%m/%d/`
- JSON-Snapshot für vollständige Nachvollziehbarkeit
- SHA256-Hash für Integritätsprüfung
- Indexierung für schnelle Abfragen

## Erweiterbarkeit

Das System ist darauf ausgelegt, einfach erweitert zu werden:

1. **Neue Report-Typen**: Einfach neue Template-Klasse mit `@register_template` erstellen
2. **Neue Styles**: Styles in `styles.py` ergänzen
3. **Custom Header/Footer**: `draw_header_footer()` in Template überschreiben
4. **Zusätzliche Metadaten**: `metadata`-Dict bei `generate_and_store()` nutzen

## Best Practices

1. **Serialisierbare Contexts**: Nur JSON-serialisierbare Daten im Context verwenden
2. **Keine ORM-Objekte**: Models vorher in Dicts konvertieren
3. **Versionierung**: Report-Keys mit Version verwenden (z.B. `invoice.v2`)
4. **Metadaten**: Wichtige Zusatzinfos in `metadata` speichern
5. **Testing**: Neue Templates mit Tests absichern

## Lizenz

Teil des KManager-Projekts

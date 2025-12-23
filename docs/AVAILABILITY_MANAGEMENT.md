# Verfügbarkeitsmanagement für MietObjekte

## Übersicht

Das Verfügbarkeitsmanagement ist eine automatische Funktion, die die Verfügbarkeit von Mietobjekten (MietObjekt) basierend auf den zugehörigen Verträgen (Vertrag) verwaltet. Das Feld `verfuegbar` wird automatisch aktualisiert, wenn Verträge erstellt, geändert oder gelöscht werden.

## Kernprinzipien

1. **Verträge sind die Quelle der Wahrheit** - Die Verfügbarkeit wird ausschließlich aus den aktiven Verträgen abgeleitet
2. **`verfuegbar` ist ein abgeleitetes Feld** - Es wird automatisch berechnet und sollte nicht manuell gesetzt werden
3. **Nur aktive Verträge blockieren** - Entwürfe, beendete und stornierte Verträge haben keinen Einfluss auf die Verfügbarkeit

## Vertragsstatus

Ein Vertrag kann einen der folgenden Status haben:

- **`draft` (Entwurf)** - Vertrag in Planung, blockiert kein Mietobjekt
- **`active` (Aktiv)** - Aktiver Vertrag, blockiert das Mietobjekt wenn zeitlich gültig
- **`ended` (Beendet)** - Regulär beendeter Vertrag, blockiert nicht
- **`cancelled` (Storniert)** - Stornierter Vertrag, blockiert nicht

## Definition "Aktuell gültiger Vertrag"

Ein Vertrag gilt als aktuell gültig und blockiert ein Mietobjekt, wenn alle folgenden Bedingungen erfüllt sind:

1. Status ist `active`
2. `start` ≤ heute
3. `ende` ist NULL (offenes Ende) ODER `ende` > heute

## Automatische Aktualisierung

Die Verfügbarkeit wird automatisch aktualisiert in folgenden Fällen:

### Beim Speichern eines Vertrags
- Wenn ein Vertrag erstellt oder geändert wird, wird die Verfügbarkeit des zugehörigen Mietobjekts automatisch neu berechnet
- Dies geschieht im `save()` Methode des Vertrag-Modells

### Beim Ändern des Status
- Admin-Aktionen zum Ändern des Vertragsstatus aktualisieren automatisch die Verfügbarkeit
- Verfügbare Aktionen:
  - "Als aktiv markieren"
  - "Als beendet markieren"
  - "Als storniert markieren"

## Schutz vor Doppelvermietung

Das System verhindert automatisch die Vermietung eines Objekts an mehrere Mieter im gleichen Zeitraum:

- Bei der Validierung wird geprüft, ob es zeitliche Überschneidungen mit anderen **aktiven** Verträgen gibt
- Entwürfe und beendete Verträge werden bei dieser Prüfung ignoriert
- Dies ermöglicht die Planung zukünftiger Verträge und das Führen einer Vertragshistorie

### Beispiele für Überschneidungen

```python
# Vertrag 1: 01.01.2024 - 31.12.2024 (aktiv)
# Vertrag 2: 01.06.2024 - 31.05.2025 (aktiv) → NICHT ERLAUBT

# Vertrag 1: 01.01.2024 - 31.12.2024 (aktiv)
# Vertrag 2: 01.01.2025 - 31.12.2025 (aktiv) → ERLAUBT

# Vertrag 1: 01.01.2024 - (offen) (aktiv)
# Vertrag 2: 01.01.2025 - 31.12.2025 (aktiv) → NICHT ERLAUBT
```

## Management Command

Das System bietet einen Management-Befehl zur manuellen Neuberechnung der Verfügbarkeit:

### Alle Mietobjekte neu berechnen
```bash
python manage.py recalc_availability
```

### Einzelnes Mietobjekt neu berechnen
```bash
python manage.py recalc_availability --mietobjekt-id=1
```

### Wann ist das nützlich?

- Nach einer Datenimigration
- Nach manuellen Datenbankänderungen
- Zur Behebung von Inkonsistenzen
- Bei der Ersteinrichtung

## Programmatische Nutzung

### Verfügbarkeit eines Mietobjekts neu berechnen

```python
from vermietung.models import MietObjekt

mietobjekt = MietObjekt.objects.get(pk=1)
mietobjekt.update_availability()
# verfuegbar ist jetzt aktualisiert
```

### Verfügbarkeit nach Vertragsänderung aktualisieren

```python
from vermietung.models import Vertrag

vertrag = Vertrag.objects.get(pk=1)
vertrag.status = 'ended'
vertrag.save()  # Verfügbarkeit wird automatisch aktualisiert
```

### Aktuell gültige Verträge abfragen

```python
from vermietung.models import Vertrag

# Alle aktuell gültigen Verträge
active_contracts = Vertrag.objects.currently_active()

# Aktuell gültige Verträge für ein bestimmtes Mietobjekt
mietobjekt_contracts = mietobjekt.vertraege.currently_active()

# Prüfen ob ein Vertrag aktuell gültig ist
if vertrag.is_currently_active():
    print("Vertrag ist aktuell gültig")
```

## Admin Interface

### Vertragsübersicht
- Neues Feld "Status" in der Vertragsliste
- Filter nach Status verfügbar
- Bulk-Aktionen zum Ändern des Status

### Mietobjektübersicht
- Filter "Nur verfügbare Mietobjekte"
- Admin-Aktion "Verfügbarkeit neu berechnen" für ausgewählte Objekte

## Best Practices

1. **Verwenden Sie die Status-Übergänge richtig**
   - Neue Verträge beginnen als `active` (Standardwert)
   - Beendete Verträge sollten auf `ended` gesetzt werden
   - Fehlerhafte Verträge auf `cancelled` setzen
   - Entwürfe für zukünftige Planung verwenden

2. **Vermeiden Sie manuelle Änderungen**
   - Ändern Sie `verfuegbar` nicht manuell in der Datenbank
   - Verwenden Sie stattdessen die Vertragsstatus

3. **Prüfen Sie bei Problemen**
   - Bei Unstimmigkeiten `recalc_availability` ausführen
   - Prüfen Sie die Vertragsstatus mit `currently_active()`

4. **Zeitplanung beachten**
   - Zukünftige Verträge können als `active` angelegt werden
   - Sie blockieren erst ab ihrem Startdatum
   - Überlappende Zeiträume werden trotzdem verhindert

## Technische Details

### Modellstruktur

```python
class MietObjekt(models.Model):
    verfuegbar = models.BooleanField(default=True)
    
    def update_availability(self):
        # Aktualisiert verfuegbar basierend auf aktiven Verträgen
        pass

class Vertrag(models.Model):
    status = models.CharField(
        choices=[('draft', 'Entwurf'), ('active', 'Aktiv'), 
                 ('ended', 'Beendet'), ('cancelled', 'Storniert')]
    )
    
    def is_currently_active(self):
        # Prüft ob Vertrag aktuell gültig ist
        pass
    
    def update_mietobjekt_availability(self):
        # Aktualisiert Verfügbarkeit des zugehörigen MietObjekts
        pass
```

### Custom QuerySet

```python
class VertragQuerySet(models.QuerySet):
    def currently_active(self):
        # Filtert aktuell gültige Verträge
        # Verwendet timezone.now() für korrekte Datumsvergleiche
        pass
```

## Datenbankmigrationen

Die Funktion erfordert folgende Migration:
- `0004_vertrag_status.py` - Fügt das Status-Feld hinzu

Bei bestehenden Daten:
1. Migration ausführen (setzt Status auf 'active' als Standard)
2. `recalc_availability` ausführen zur Synchronisation
3. Ggf. manuelle Anpassung der Status für historische Verträge

## Tests

Das System wird durch umfassende Tests abgedeckt:

- `test_availability.py` - 12 Tests für Verfügbarkeitslogik
- `test_management_commands.py` - 5 Tests für Management-Befehle
- Bestehende Tests wurden angepasst und laufen weiterhin

Tests ausführen:
```bash
python manage.py test vermietung.test_availability
python manage.py test vermietung.test_management_commands
```

## Fehlerbehebung

### Mietobjekt wird als verfügbar angezeigt, obwohl ein aktiver Vertrag existiert

```bash
# Prüfen Sie die Verträge
python manage.py shell
>>> from vermietung.models import MietObjekt, Vertrag
>>> m = MietObjekt.objects.get(name="Garage 1")
>>> m.vertraege.currently_active()
<QuerySet [<Vertrag: V-00001 - Garage 1 (Max Mustermann)>]>

# Verfügbarkeit neu berechnen
>>> m.update_availability()
>>> m.verfuegbar
False
```

### Vertrag lässt sich nicht speichern trotz freiem Zeitraum

- Prüfen Sie, ob es einen anderen **aktiven** Vertrag gibt, der den Zeitraum blockiert
- Entwürfe und beendete Verträge sollten kein Problem sein
- Bei offenen Enden (ende=NULL) besonders vorsichtig sein

### Nach Status-Änderung stimmt Verfügbarkeit nicht

Die Verfügbarkeit wird automatisch aktualisiert. Wenn nicht:
```python
vertrag.update_mietobjekt_availability()
```

## Weitere Informationen

- Siehe auch: [VERTRAG_MODEL.md](VERTRAG_MODEL.md) für Details zum Vertragsmodell
- Django Dokumentation: [Model Managers](https://docs.djangoproject.com/en/5.0/topics/db/managers/)
- Django Dokumentation: [Custom Querysets](https://docs.djangoproject.com/en/5.0/topics/db/queries/)

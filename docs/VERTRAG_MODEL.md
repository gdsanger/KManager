# Vertrag Model - Dokumentation

## Übersicht
Das `Vertrag` Model repräsentiert einen Mietvertrag in der KManager-Anwendung. Jeder Vertrag bezieht sich auf genau ein Mietobjekt und einen Mieter (Kunde).

## Vertragsnummernkreis

### Format
- Format: `V-00000`
- Präfix: `V-`
- Nummer: 5-stellig mit führenden Nullen
- Beispiele: `V-00001`, `V-00023`, `V-12345`

### Automatische Vergabe
Die Vertragsnummer wird **automatisch** beim Speichern eines neuen Vertrags vergeben:
- Sequenzielle Nummerierung (fortlaufend)
- Race-Condition-sicher durch `SELECT FOR UPDATE` Lock
- Nicht manuell editierbar (im Admin als read-only angezeigt)

### Technische Implementierung
```python
def _generate_vertragsnummer(self):
    with transaction.atomic():
        last_contract = Vertrag.objects.select_for_update().order_by('-vertragsnummer').first()
        # ... Nummerngenerierung
```

## Vertragszeitraum

### Felder
- **start**: Vertragsbeginn (Pflichtfeld, DateField)
- **ende**: Vertragsende (Optional, DateField, NULL erlaubt)

### Validierungsregeln
1. `start` ist immer erforderlich
2. `ende` ist optional (NULL = offenes Ende)
3. Wenn `ende` gesetzt ist, muss gelten: `ende > start`

### Beispiele
```python
# Gültig: Vertrag mit definiertem Ende
Vertrag(start="2024-01-01", ende="2024-12-31", ...)

# Gültig: Offener Vertrag ohne Ende
Vertrag(start="2024-01-01", ende=None, ...)

# Ungültig: Ende vor oder gleich Start
Vertrag(start="2024-12-31", ende="2024-01-01", ...)  # ValidationError
```

## Überlappungsverhinderung

### Regel
Für dasselbe `MietObjekt` dürfen sich Vertragszeiträume nicht überschneiden.

### Logik
1. **Beide Verträge mit Enddatum**: Standard-Überlappungsprüfung
   - Überlappung wenn: `start1 < ende2 AND ende1 > start2`

2. **Vertrag ohne Enddatum (offenes Ende)**:
   - Blockiert alle zukünftigen Verträge für dieses Mietobjekt
   - Kann nicht erstellt werden, wenn bereits ein aktiver Vertrag existiert

3. **Verschiedene Mietobjekte**: Keine Konflikte
   - Verträge für verschiedene `MietObjekt`-Instanzen können beliebig überlappen

### Beispiele

**Erlaubt** (keine Überlappung):
```
Vertrag 1: 2023-01-01 bis 2023-12-31
Vertrag 2: 2024-01-01 bis 2024-12-31
```

**Nicht erlaubt** (Überlappung):
```
Vertrag 1: 2024-01-01 bis 2024-12-31
Vertrag 2: 2024-06-01 bis 2025-06-01  # ValidationError
```

**Nicht erlaubt** (offenes Ende):
```
Vertrag 1: 2024-01-01 bis NULL (offen)
Vertrag 2: 2025-01-01 bis 2025-12-31  # ValidationError
```

## Mieter-Einschränkung

### Regel
Nur Adressen vom Typ `KUNDE` können als Mieter ausgewählt werden.

### Implementierung
- Model-Ebene: `limit_choices_to={'adressen_type': 'KUNDE'}`
- Admin-Ebene: Custom Form mit gefilterter QuerySet

```python
# In models.py
mieter = models.ForeignKey(
    Adresse,
    limit_choices_to={'adressen_type': 'KUNDE'},
    ...
)

# In admin.py
class VertragAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mieter'].queryset = Adresse.objects.filter(adressen_type='KUNDE')
```

## Beziehungen

### MietObjekt → Vertrag
- **Typ**: 1:n (Ein Mietobjekt kann viele Verträge haben)
- **Historie**: Erlaubt historische Verträge für dasselbe Objekt
- **Reverse**: `mietobjekt.vertraege.all()`

### Adresse → Vertrag (als Mieter)
- **Typ**: 1:n (Eine Kunde-Adresse kann viele Verträge haben)
- **Einschränkung**: Nur `adressen_type='KUNDE'`
- **Reverse**: `adresse.vertraege.all()`

## Admin-Integration

### Anzeige
- **List Display**: vertragsnummer, mietobjekt, mieter, start, ende, miete, kaution
- **Suche**: vertragsnummer, mietobjekt.name, mieter.name, mieter.firma
- **Filter**: start, ende, mietobjekt

### Fieldsets
1. **Vertragsdetails**: vertragsnummer (readonly), mietobjekt, mieter
2. **Zeitraum**: start, ende
3. **Finanzielle Details**: miete, kaution

## Verwendung

### Neuen Vertrag erstellen
```python
from vermietung.models import Vertrag, MietObjekt
from core.models import Adresse

# Objekte laden
mietobjekt = MietObjekt.objects.get(name='Garage 1')
kunde = Adresse.objects.get(adressen_type='KUNDE', name='Max Mustermann')

# Vertrag erstellen
vertrag = Vertrag.objects.create(
    mietobjekt=mietobjekt,
    mieter=kunde,
    start='2024-01-01',
    ende='2024-12-31',  # oder None für offenes Ende
    miete=150.00,
    kaution=450.00
)
# vertragsnummer wird automatisch generiert: V-00001
```

### Vertragshistorie abfragen
```python
# Alle Verträge eines Mietobjekts
vertraege = mietobjekt.vertraege.all().order_by('start')

# Aktuelle Verträge (ohne Ende oder Ende in der Zukunft)
from datetime import date
from django.db.models import Q
aktive_vertraege = mietobjekt.vertraege.filter(
    Q(ende__isnull=True) | Q(ende__gte=date.today())
)
```

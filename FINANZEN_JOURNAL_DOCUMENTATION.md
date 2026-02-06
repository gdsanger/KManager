# Finanzen - Rechnungsausgangsjournal & DATEV-Export-Basis

## Übersicht

Die Finanzen-App implementiert ein **unveränderliches Rechnungsausgangsjournal** für Rechnungen und Gutschriften, das als rechtssichere Buchhaltungsbasis dient und DATEV-kompatibel strukturiert ist.

## Zielsetzung

- **Rechtssichere Buchhaltungsbasis**: Immutable Journal-Einträge für finalisierte Belege
- **DATEV-Kompatibilität**: Struktur orientiert sich an DATEV-Anforderungen
- **Snapshot-basiert**: Keine rückwirkenden Änderungen möglich
- **Export-Vorbereitung**: Tracking für späteren DATEV-Export

## Modelle

### 1. CompanyAccountingSettings

**Zweck**: Buchhaltungseinstellungen pro Mandant (OneToOne zu `core.Mandant`)

**Felder**:

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `company` | OneToOneField | Referenz auf core.Mandant (erforderlich) |
| `datev_consultant_number` | CharField(20) | DATEV Beraternummer (mit führenden Nullen) |
| `datev_client_number` | CharField(20) | DATEV Mandantennummer (mit führenden Nullen) |
| `tax_number` | CharField(50) | Steuernummer des Mandanten |
| `revenue_account_0` | CharField(20) | Erlöskonto für Steuersatz 0% |
| `revenue_account_7` | CharField(20) | Erlöskonto für Steuersatz 7% |
| `revenue_account_19` | CharField(20) | Erlöskonto für Steuersatz 19% |

**Verwendung**:
- Pro Mandant gibt es genau eine Settings-Instanz (OneToOne)
- Alle Felder als String gespeichert (führende Nullen, DATEV-Formate)
- Konfigurierbar über Django Admin

**Zugriff**:
```python
# Über Mandant-Instanz:
mandant = Mandant.objects.get(id=1)
settings = mandant.accounting_settings

# Direkt:
settings = CompanyAccountingSettings.objects.get(company=mandant)
```

---

### 2. OutgoingInvoiceJournalEntry

**Zweck**: Unveränderlicher Journal-Eintrag für einen finalisierten Beleg (Rechnung oder Gutschrift)

**Snapshot-Prinzip**: Alle relevanten Daten werden zum Zeitpunkt der Erzeugung kopiert und danach nicht mehr verändert.

**Felder**:

#### Referenzen
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `company` | ForeignKey | Referenz auf core.Mandant (erforderlich) |
| `document` | ForeignKey | Referenz auf auftragsverwaltung.SalesDocument (PROTECT) |

#### Snapshot-Felder
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `document_number` | CharField(32) | Belegnummer (z.B. R26-00001) |
| `document_date` | DateField | Belegdatum |
| `document_kind` | CharField | INVOICE oder CREDIT_NOTE |
| `customer_name` | CharField(200) | Kundenname |
| `debtor_number` | CharField(32) | Debitorennummer (optional) |

#### Beträge je Steuersatz
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `net_0` | DecimalField(10,2) | Nettobetrag mit 0% MwSt. |
| `net_7` | DecimalField(10,2) | Nettobetrag mit 7% MwSt. |
| `net_19` | DecimalField(10,2) | Nettobetrag mit 19% MwSt. |
| `tax_amount` | DecimalField(10,2) | Gesamter Steuerbetrag |
| `gross_amount` | DecimalField(10,2) | Bruttobetrag (gesamt) |

#### Erlöskonten (Snapshot)
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `revenue_account_0` | CharField(20) | Erlöskonto 0% (Snapshot) |
| `revenue_account_7` | CharField(20) | Erlöskonto 7% (Snapshot) |
| `revenue_account_19` | CharField(20) | Erlöskonto 19% (Snapshot) |

#### Export-Tracking
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `export_status` | CharField | OPEN, EXPORTED oder ERROR |
| `exported_at` | DateTimeField | Zeitpunkt des letzten Exports (nullable) |
| `export_batch_id` | CharField(100) | ID der Export-Charge (optional) |

#### Meta
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `created_at` | DateTimeField | Zeitpunkt der Erzeugung (auto_now_add) |

**Constraints**:
- **Unique**: `(company, document)` - Genau ein Journal-Eintrag pro Beleg
- **Unique**: `(company, document_number)` - Eindeutige Belegnummer pro Mandant

**Indizes**:
- `(company, document_date)` - Performance für zeitbasierte Abfragen
- `(company, export_status)` - Performance für Export-Filter
- `document_number` - Schnelle Suche nach Belegnummer

**Validierung**:
- `clean()` prüft: `gross_amount = (net_0 + net_7 + net_19) + tax_amount`
- Rundungsdifferenzen bis 0,01 € sind erlaubt

**Verwendung**:
```python
from finanzen.models import OutgoingInvoiceJournalEntry
from auftragsverwaltung.models import SalesDocument

# Beispiel: Journal-Eintrag erstellen (programmatisch)
document = SalesDocument.objects.get(number='R26-00001')
company = document.company
settings = company.accounting_settings

entry = OutgoingInvoiceJournalEntry.objects.create(
    company=company,
    document=document,
    document_number=document.number,
    document_date=document.issue_date,
    document_kind='INVOICE',
    customer_name=document.customer.full_name(),
    debtor_number=document.customer.debtor_number or '',
    net_0=Decimal('0.00'),
    net_7=Decimal('100.00'),
    net_19=Decimal('200.00'),
    tax_amount=Decimal('45.00'),  # 7 + 38
    gross_amount=Decimal('345.00'),
    revenue_account_0=settings.revenue_account_0,
    revenue_account_7=settings.revenue_account_7,
    revenue_account_19=settings.revenue_account_19,
    export_status='OPEN'
)
```

---

## Steuerlogik

Das Journal unterstützt **nur** die Steuersätze:
- **0%** (steuerfreie Lieferungen)
- **7%** (ermäßigter Steuersatz)
- **19%** (Regelsteuersatz)

**Wichtig**:
- Tax-Splitting muss **vor** Journal-Erzeugung erfolgen
- Andere Steuersätze sollten blockiert oder als Fehler markiert werden (außerhalb des Scopes)
- Die Erlöskonten werden als Snapshot gespeichert (können sich später bei den Settings ändern, ohne den Journal-Eintrag zu beeinflussen)

---

## Django Admin

### CompanyAccountingSettingsAdmin
- **Bearbeitbar**: Ja
- **Löschbar**: Ja
- **Felder gruppiert**:
  - Mandant
  - DATEV Konfiguration
  - Erlöskonten je Steuersatz

### OutgoingInvoiceJournalEntryAdmin
- **Bearbeitbar**: **NEIN** (read-only, Snapshot-Prinzip)
- **Löschbar**: **NEIN** (permanenter Buchhaltungsbeleg)
- **Erstellbar**: **NEIN** (nur programmatisch)
- **Filter**: Company, Belegart, Export-Status, Datum
- **Suche**: Belegnummer, Kundenname, Debitorennummer, Batch-ID
- **Sortierung**: Nach Erstellungsdatum (neueste zuerst)

---

## Abgrenzung (Out of Scope)

Die folgenden Funktionen sind **bewusst nicht Teil** dieser Implementierung:

❌ **Erzeugungslogik** des Journal-Eintrags (z.B. nach "Finalisieren/Drucken")
❌ **DATEV-Exportdateien** (CSV/XML-Generierung)
❌ **Zahlungsabgleich** / OP-Verwaltung
❌ **Mahnwesen**
❌ **Debitorenstamm-Logik**

Diese Funktionalitäten werden in zukünftigen Issues implementiert.

---

## Nächste Schritte

1. **Journal-Erzeugungslogik** implementieren:
   - Signal oder Service-Methode beim Finalisieren eines Belegs
   - Automatisches Erstellen des Journal-Eintrags
   - Tax-Splitting-Logik

2. **DATEV-Export** implementieren:
   - CSV-Generierung nach DATEV-Standard
   - Batch-Export mehrerer Einträge
   - Export-Status-Tracking

3. **Validierung**:
   - Blockieren von unsupported Steuersätzen
   - Prüfung auf vollständige Settings vor Journal-Erzeugung

---

## Technische Details

**App**: `finanzen`
**Django Version**: 5.2+
**Dependencies**: 
- `core` (Mandant)
- `auftragsverwaltung` (SalesDocument)

**Migration**: `finanzen.0001_initial`

**Tests**: Noch nicht implementiert (kann in zukünftigen Issues ergänzt werden)

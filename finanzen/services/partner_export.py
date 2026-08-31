"""
Stammdatenexport der Personenkonten (Debitoren und Kreditoren)

Der Buchungsstapel (:mod:`finanzen.services.datev_export`) bucht gegen
Personenkonten, trägt davon aber nur die **Kontonummer** in die Datei. Wer die
Buchungen einliest, kann sie ohne die zugehörigen Stammdaten keinem Namen
zuordnen – beim ersten Import existieren die Personenkonten im Zielsystem
überhaupt noch nicht. Dieses Modul liefert die fehlende Gegenseite: je
Adresse mit Personenkonto eine Zeile mit Name, Anschrift und Kontaktdaten.

Quelle ist ``core.Adresse``:

- ``adressen_type='KUNDE'``      → Debitor
- ``adressen_type='LIEFERANT'``  → Kreditor

Beide Personenkonten liegen im selben Feld ``debitor_number``; unterschieden
wird über den Adresstyp und den zugehörigen Kontenbereich
(``Adresse.personal_account_range()``).

Kein Mandantenfilter: ``Adresse`` hat keinen Mandantenbezug, Personenkonten
sind in GIS mandantenübergreifend. Anders als der Buchungsstapel bekommt der
Stammdatenexport deshalb keine Mandantenauswahl.

Format:
Bewusst **kein** EXTF-Kopfsatz. Die DATEV-Formatkategorie 16
(„Debitoren/Kreditoren") schreibt mehrere hundert Spalten in fester
Reihenfolge vor, die sich ohne die DATEV-Formatbeschreibung nicht korrekt
nachbilden lässt; eine geratene Feldliste würde bei einem echten DATEV-Import
abgewiesen. Zielsystem ist Kontolino, dort wird beim Import ohnehin manuell
gemappt. Deshalb eine CSV mit sprechender Überschriftenzeile – technisch in
derselben Hülle wie der Buchungsstapel (Windows-1252, ``;``, CRLF, siehe
:mod:`finanzen.services.datev_common`), damit Umlaute und Trennzeichen sich
gleich verhalten. Siehe docs/DATEV_EXPORT.md.
"""
from dataclasses import dataclass, field

from django.utils import timezone

from core.models import Adresse
from finanzen.services.datev_common import (
    DELIMITER,
    ENCODING,
    LINE_ENDING,
    _clean,
    _quote,
)

# --- Auswahl ----------------------------------------------------------------

DEBTOR = 'DEBTOR'
CREDITOR = 'CREDITOR'
BOTH = 'BOTH'

KIND_CHOICES = [
    (DEBTOR, 'Debitoren (Kunden)'),
    (CREDITOR, 'Kreditoren (Lieferanten)'),
    (BOTH, 'Debitoren und Kreditoren'),
]

# Auswahl -> Adresstypen. Adressen der übrigen Typen ('Adresse', 'STANDORT',
# 'SONSTIGES') führen kein Personenkonto und tauchen in keiner Auswahl auf.
ADDRESS_TYPES = {
    DEBTOR: ['KUNDE'],
    CREDITOR: ['LIEFERANT'],
    BOTH: ['KUNDE', 'LIEFERANT'],
}

# Adresstyp -> Kontoart im Klartext
ACCOUNT_KIND = {
    'KUNDE': 'Debitor',
    'LIEFERANT': 'Kreditor',
}

# --- Format -----------------------------------------------------------------

# Spalten der Datei (Überschriftenzeile, 1. Zeile). Wie BOOKING_COLUMNS im
# Buchungsstapel bewusst **eine** Konstante: Ergänzungen passieren an genau
# einer Stelle, und sie ist der Ansatzpunkt, falls später doch die
# DATEV-Formatkategorie 16 nachgebildet wird.
PARTNER_COLUMNS = [
    'Konto', 'Kontoart', 'Adressattyp', 'Firma', 'Name', 'Anrede', 'Straße',
    'PLZ', 'Ort', 'Land', 'Ländercode', 'USt-IdNr.', 'EU', 'E-Mail',
    'E-Mail Rechnung', 'Telefon', 'Mobil',
]

# Feldlänge der Textspalten. Deckt das längste Adressfeld (strasse, 200) ab;
# gekürzt wird damit praktisch nie, die Grenze schützt nur vor Ausreißern.
MAX_FIELD = 200


# --- Datenstrukturen --------------------------------------------------------

@dataclass
class PartnerRecord:
    """Ein exportfähiges Personenkonto."""

    account: str          # Konto (Debitoren- bzw. Kreditorennummer)
    account_kind: str     # 'Debitor' oder 'Kreditor'
    address: object       # core.Adresse

    @property
    def is_debtor(self):
        return self.account_kind == ACCOUNT_KIND['KUNDE']

    @property
    def display_name(self):
        """Anzeigename für die Vorschau (nicht Bestandteil der Datei)."""
        return self.address.full_name()


@dataclass
class PartnerProblem:
    """Eine Adresse, die nicht exportiert werden kann."""

    account_kind: str   # 'Debitor' oder 'Kreditor'
    account: str        # Personenkonto, ggf. leer
    name: str           # Anzeigename der Adresse
    message: str


@dataclass
class PartnerExportPreview:
    """Ergebnis der Vorschau: was exportiert würde und was fehlt."""

    kind: str
    partners: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    @property
    def has_problems(self):
        return bool(self.problems)

    @property
    def partner_count(self):
        return len(self.partners)

    @property
    def debtor_count(self):
        return sum(1 for p in self.partners if p.is_debtor)

    @property
    def creditor_count(self):
        return sum(1 for p in self.partners if not p.is_debtor)

    @property
    def kind_label(self):
        return dict(KIND_CHOICES).get(self.kind, '')


# --- Vorschau ---------------------------------------------------------------

def _range_problem(address, account):
    """
    Prüfen, ob das Personenkonto zum Adresstyp passt.

    Die Grenzen kommen aus ``Adresse.personal_account_range()`` und damit aus
    denselben Settings wie die Validierung bei der Neuanlage – sie stehen
    bewusst kein zweites Mal im Code. Bereichsfremde oder nicht-numerische
    Konten kann es trotzdem geben (importierte Altdaten).

    Returns:
        str oder None: die Fehlermeldung, sonst None
    """
    bounds = Adresse.personal_account_range(address.adressen_type)
    if bounds is None:
        return None

    low, high = bounds
    label = ACCOUNT_KIND[address.adressen_type] + 'enkonto'

    if not account.isdigit():
        return (
            f'Das Personenkonto „{account}" ist nicht rein numerisch und kann '
            'nicht als Personenkonto übergeben werden.'
        )
    if not (low <= int(account) <= high):
        return (
            f'Das {label} {account} liegt außerhalb des zulässigen Bereichs '
            f'({low}–{high}) und würde im Zielsystem auf der falschen Seite '
            'landen.'
        )
    return None


def build_partner_preview(kind=BOTH):
    """
    Personenkonten zusammenstellen, ohne eine Datei zu schreiben.

    Args:
        kind: DEBTOR, CREDITOR oder BOTH

    Returns:
        PartnerExportPreview – enthält die exportfähigen Partner **und** die
        Fehlerliste. Adressen ohne Personenkonto oder mit bereichsfremdem
        Konto werden nicht still weggelassen; sonst fehlte der Partner später
        im Zielsystem, ohne dass es jemandem auffällt.

    Auf doppelte Kontonummern wird nicht geprüft: Die UniqueConstraint
    ``unique_debitor_number`` schließt sie bereits aus.
    """
    types = ADDRESS_TYPES.get(kind, ADDRESS_TYPES[BOTH])
    preview = PartnerExportPreview(kind=kind if kind in ADDRESS_TYPES else BOTH)

    # Sortierung nach Kontonummer. Gültige Konten sind fünfstellig, damit ist
    # die lexikografische Sortierung des CharFields zugleich die numerische;
    # `pk` hält die Reihenfolge auch bei Altdaten stabil.
    addresses = Adresse.objects.filter(
        adressen_type__in=types,
    ).order_by('debitor_number', 'pk')

    for address in addresses:
        account_kind = ACCOUNT_KIND[address.adressen_type]
        account = (address.debitor_number or '').strip()

        if not account:
            preview.problems.append(PartnerProblem(
                account_kind, '', address.full_name(),
                'Adresse ohne Personenkonto. Bitte das '
                f'{account_kind}enkonto an der Adresse pflegen; sonst fehlt '
                'der Partner im Zielsystem.',
            ))
            continue

        message = _range_problem(address, account)
        if message:
            preview.problems.append(PartnerProblem(
                account_kind, account, address.full_name(), message,
            ))
            continue

        preview.partners.append(PartnerRecord(
            account=account, account_kind=account_kind, address=address,
        ))

    return preview


# --- Rendering --------------------------------------------------------------

def _partner_row(record):
    """Ein Personenkonto auf die Spalten der Datei abbilden."""
    address = record.address
    return [
        # Konto bewusst als Textfeld: so bleiben führende Nullen erhalten.
        record.account,
        record.account_kind,
        'Unternehmen' if address.is_business else 'natürliche Person',
        # Firma und Name getrennt statt des zusammengesetzten `matchkey` –
        # das Zielsystem soll die Felder einzeln zuordnen können.
        address.firma,
        address.name,
        address.get_anrede_display(),
        address.strasse,
        address.plz,
        address.ort,
        address.land,
        address.country_code,
        address.vat_id,
        'ja' if address.is_eu else 'nein',
        address.email,
        address.invoice_email,
        address.telefon,
        address.mobil,
    ]


def render_partner_csv(preview):
    """
    Die Personenkonten als CSV rendern.

    Args:
        preview: PartnerExportPreview aus :func:`build_partner_preview`

    Returns:
        bytes: die Datei im DATEV-Zeichensatz (Windows-1252)

    Anders als :func:`finanzen.services.datev_export.render_extf` bricht die
    Funktion bei Einträgen in ``problems`` **nicht** ab: Ein fehlendes
    Personenkonto ist ein Pflegehinweis, kein falscher Buchungssatz. Die
    betroffenen Adressen stehen in der Vorschau und fehlen in der Datei.
    """
    rows = [[_quote(name) for name in PARTNER_COLUMNS]]
    rows.extend(
        [_quote(_clean(value, MAX_FIELD)) for value in _partner_row(record)]
        for record in preview.partners
    )

    content = LINE_ENDING.join(DELIMITER.join(row) for row in rows) + LINE_ENDING
    return content.encode(ENCODING, errors='replace')


def build_partner_filename(preview, created_at=None):
    """Sprechender Dateiname für den Download."""
    suffix = {
        DEBTOR: '_Debitoren',
        CREDITOR: '_Kreditoren',
    }.get(preview.kind, '')
    day = created_at or timezone.localdate()
    return f'Personenkonten{suffix}_{day:%Y%m%d}.csv'

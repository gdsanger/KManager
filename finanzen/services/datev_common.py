"""
Gemeinsame Formatbausteine der DATEV-nahen Exporte.

Buchungsstapel (:mod:`finanzen.services.datev_export`) und Stammdatenexport
der Personenkonten (:mod:`finanzen.services.partner_export`) erzeugen beide
eine semikolongetrennte Datei im DATEV-Zeichensatz. Zeichensatz, Trennzeichen,
Zeilenende und die Feldaufbereitung stehen deshalb hier an genau **einer**
Stelle – sonst driften die beiden Dateien im Detail auseinander (Umlaute,
Textbegrenzer, Zeilenende), obwohl sie dasselbe Zielsystem füttern.
"""

# DATEV-Zeichensatz: ANSI/Windows-1252. Umlaute werden damit korrekt
# transportiert; nicht abbildbare Zeichen werden ersetzt statt den Export
# abzubrechen.
ENCODING = 'cp1252'
DELIMITER = ';'
LINE_ENDING = '\r\n'


def _clean(value, max_length):
    """
    Text für ein DATEV-Feld aufbereiten.

    Trennzeichen und Textbegrenzer werden entfernt, damit sie die
    Feldstruktur nicht zerstören; anschließend wird auf die Feldlänge gekürzt.
    """
    text = (value or '').replace(DELIMITER, ' ').replace('"', "'")
    text = ' '.join(text.split())
    return text[:max_length]


def _quote(value):
    """Textfeld mit Textbegrenzer versehen."""
    return f'"{value}"'

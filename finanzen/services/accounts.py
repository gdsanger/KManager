"""
Kontoauflösung für den DATEV-Buchungsstapel (Kontierung über die Kostenarten)

Dies ist die **einzige** Stelle, an der entschieden wird, welches Sachkonto ein
Beleg bekommt. Ein- und Ausgangsseite nutzen dieselbe Funktion; wer die Regel
ändern will, ändert sie hier.

Regel:
- **Aufwand** (Eingangsrechnungen): Konto der Unterkostenart, sonst Konto der
  Hauptkostenart, sonst Fehler.
- **Erlös** (Ausgangsrechnungen): Konto der Unterkostenart, sonst der
  Hauptkostenart, sonst das ``revenue_account_*`` des Mandanten passend zum
  Steuersatz, sonst Fehler.

Die Erlösseite wird nicht beim Export ausgewertet, sondern bereits bei der
Finalisierung: ``finanzen.services.journal`` schreibt das Ergebnis als
Snapshot ins Rechnungsausgangsjournal. Der Export liest ausschließlich diesen
Snapshot – dadurch ändern sich exportierte Konten nicht nachträglich mit der
Stammdatenpflege mit.
"""

EXPENSE = 'EXPENSE'
REVENUE = 'REVENUE'

# Kontofeld an core.Kostenart je Kontenart
COST_TYPE_ACCOUNT_FIELDS = {
    EXPENSE: 'aufwandskonto',
    REVENUE: 'erloeskonto',
}

# Steuersatz-Schlüssel -> Erlöskontofeld an CompanyAccountingSettings.
# Die Schlüssel entsprechen core.Kostenart.UMSATZSTEUER_SAETZE.
REVENUE_ACCOUNT_BY_TAX_KEY = {
    '0': 'revenue_account_0',
    '7': 'revenue_account_7',
    '19': 'revenue_account_19',
}

KIND_LABELS = {
    EXPENSE: 'Aufwandskonto',
    REVENUE: 'Erlöskonto',
}


class AccountResolutionError(ValueError):
    """
    Für einen Beleg lässt sich kein Sachkonto ermitteln.

    Erbt von ``ValueError``, damit aufrufende Views den Fehler wie andere
    fachliche Fehler als Anwenderfehler behandeln können.
    """


def _cost_type_chain(cost_type_sub, cost_type_main):
    """
    Kostenarten in Auflösungsreihenfolge liefern: Unterkostenart vor
    Hauptkostenart.

    Ist nur eine Unterkostenart gesetzt, wird deren ``parent`` als
    Hauptkostenart ergänzt – Belege pflegen die Hauptkostenart nicht immer
    redundant mit.

    Returns:
        list[core.Kostenart]: ohne Duplikate und ohne None
    """
    chain = []

    if cost_type_sub is not None:
        chain.append(cost_type_sub)

    main = cost_type_main
    if main is None and cost_type_sub is not None:
        main = cost_type_sub.parent

    if main is not None:
        chain.append(main)

    # Duplikate entfernen (z. B. wenn nur die Hauptkostenart gepflegt und
    # versehentlich in beiden Feldern hinterlegt ist), Reihenfolge erhalten.
    seen = set()
    unique = []
    for cost_type in chain:
        key = cost_type.pk if cost_type.pk is not None else id(cost_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(cost_type)
    return unique


def resolve_account(
    kind,
    cost_type_sub=None,
    cost_type_main=None,
    tax_key=None,
    accounting_settings=None,
):
    """
    Sachkonto nach der zentralen Regel auflösen.

    Args:
        kind: ``EXPENSE`` oder ``REVENUE``
        cost_type_sub: Unterkostenart (core.Kostenart) oder None
        cost_type_main: Hauptkostenart (core.Kostenart) oder None
        tax_key: '0', '7' oder '19' – nur für ``REVENUE`` relevant
        accounting_settings: CompanyAccountingSettings oder None – nur für
            ``REVENUE`` relevant

    Returns:
        str: das aufgelöste Sachkonto, oder None wenn keine Quelle greift.
    """
    if kind not in COST_TYPE_ACCOUNT_FIELDS:
        raise ValueError(f'Unbekannte Kontenart: {kind}')

    field = COST_TYPE_ACCOUNT_FIELDS[kind]
    for cost_type in _cost_type_chain(cost_type_sub, cost_type_main):
        account = (getattr(cost_type, field, '') or '').strip()
        if account:
            return account

    # Nur auf der Erlösseite gibt es einen Fallback über den Steuersatz.
    if kind == REVENUE and accounting_settings is not None:
        settings_field = REVENUE_ACCOUNT_BY_TAX_KEY.get(str(tax_key))
        if settings_field:
            account = (getattr(accounting_settings, settings_field, '') or '').strip()
            if account:
                return account

    return None


def require_account(
    kind,
    cost_type_sub=None,
    cost_type_main=None,
    tax_key=None,
    accounting_settings=None,
    context='',
):
    """
    Wie :func:`resolve_account`, wirft aber statt None einen sprechenden
    Fehler.

    Args:
        context: Beschreibung des Belegs für die Fehlermeldung
            (z. B. "Eingangsrechnung RE-2026-17")

    Raises:
        AccountResolutionError: wenn kein Konto ermittelbar ist
    """
    account = resolve_account(
        kind,
        cost_type_sub=cost_type_sub,
        cost_type_main=cost_type_main,
        tax_key=tax_key,
        accounting_settings=accounting_settings,
    )
    if account:
        return account

    label = KIND_LABELS[kind]
    prefix = f'{context}: ' if context else ''

    if kind == EXPENSE:
        raise AccountResolutionError(
            f'{prefix}Kein {label} ermittelbar. Bitte an der Kostenart '
            '(Unter- oder Hauptkostenart) ein Aufwandskonto hinterlegen.'
        )

    raise AccountResolutionError(
        f'{prefix}Kein {label} für den Steuersatz {tax_key} % ermittelbar. '
        'Bitte in den Buchhaltungseinstellungen des Mandanten ein Erlöskonto '
        'für diesen Steuersatz hinterlegen oder eines an der Kostenart pflegen.'
    )


def resolve_expense_account(cost_type_sub=None, cost_type_main=None, context=''):
    """Aufwandskonto ermitteln (Eingangsseite). Siehe :func:`require_account`."""
    return require_account(
        EXPENSE,
        cost_type_sub=cost_type_sub,
        cost_type_main=cost_type_main,
        context=context,
    )


def resolve_revenue_account(
    tax_key,
    accounting_settings,
    cost_type_sub=None,
    cost_type_main=None,
    context='',
):
    """Erlöskonto ermitteln (Ausgangsseite). Siehe :func:`require_account`."""
    return require_account(
        REVENUE,
        cost_type_sub=cost_type_sub,
        cost_type_main=cost_type_main,
        tax_key=tax_key,
        accounting_settings=accounting_settings,
        context=context,
    )

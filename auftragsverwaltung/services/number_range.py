"""
Number Range Service

Provides race-safe number generation for documents and contracts with yearly reset policy.

Personenkonten (Debitoren/Kreditoren) laufen über dieselbe Mechanik, werden
aber rein numerisch und ohne Jahresbestandteil vergeben – siehe
:func:`get_next_customer_number` und :func:`get_next_supplier_number`.
"""
from django.db import transaction
from datetime import date
from auftragsverwaltung.models import NumberRange


def _advance_sequence(number_range, yy):
    """
    Nächsten Sequenzwert eines Nummernkreises ermitteln und persistieren.

    Kapselt die Reset-Policy und den optionalen Startwert an einer Stelle,
    damit alle Nummernkreise (Beleg, Vertrag, Artikel, Personenkonten) sich
    identisch verhalten.

    Args:
        number_range: bereits per select_for_update() gesperrte NumberRange
        yy: zweistellige Jahreszahl des Vergabedatums

    Returns:
        int: der vergebene Sequenzwert
    """
    if number_range.reset_policy == 'YEARLY' and number_range.current_year != yy:
        # Year has changed with YEARLY policy, reset sequence
        number_range.current_year = yy
        number_range.current_seq = 0
    elif number_range.reset_policy == 'NEVER' and number_range.current_year != yy:
        # Year has changed with NEVER policy, update year but don't reset sequence
        number_range.current_year = yy

    # start_seq bestimmt den ersten zu vergebenden Wert. Ein bereits weiter
    # fortgeschrittener current_seq gewinnt, damit ein nachträglich gesenkter
    # Startwert keine Nummern doppelt vergibt.
    start_seq = number_range.start_seq or 0
    if number_range.current_seq < start_seq - 1:
        number_range.current_seq = start_seq - 1

    number_range.current_seq += 1
    number_range.save()

    return number_range.current_seq


def get_next_number(company, document_type, date_obj=None):
    """
    Get next number for a document type and company.

    This function is atomic and race-safe using database transactions and row-level locking.

    Args:
        company: Mandant instance
        document_type: DocumentType instance
        date_obj: datetime.date or datetime.datetime (defaults to today)

    Returns:
        str: Formatted number string (e.g., "R26-00001")

    Example:
        >>> from core.models import Mandant
        >>> from auftragsverwaltung.models import DocumentType
        >>> from datetime import date
        >>> company = Mandant.objects.first()
        >>> doc_type = DocumentType.objects.get(key='invoice')
        >>> number = get_next_number(company, doc_type, date(2026, 1, 15))
        >>> print(number)  # "R26-00001"
    """
    if date_obj is None:
        date_obj = date.today()

    # Extract datetime.date from datetime.datetime if needed
    if hasattr(date_obj, 'date'):
        date_obj = date_obj.date()

    # Get two-digit year
    yy = date_obj.year % 100

    with transaction.atomic():
        # Get or create the number range with row-level lock
        number_range, created = NumberRange.objects.select_for_update().get_or_create(
            company=company,
            target='DOCUMENT',
            document_type=document_type,
            defaults={
                'current_year': yy,
                'current_seq': 0,
                'format': '{prefix}{yy}-{seq:05d}',
                'reset_policy': 'YEARLY'
            }
        )

        seq = _advance_sequence(number_range, yy)

        # Generate the formatted number
        formatted_number = number_range.format.format(
            prefix=document_type.prefix,
            yy=f"{yy:02d}",
            seq=seq
        )

        return formatted_number


def get_next_contract_number(company, date_obj=None):
    """
    Get next number for a contract and company.

    This function is atomic and race-safe using database transactions and row-level locking.
    Raises ValueError if no contract NumberRange is configured for the company.

    Args:
        company: Mandant instance
        date_obj: datetime.date or datetime.datetime (defaults to today)

    Returns:
        str: Formatted number string (e.g., "V26-00001")

    Raises:
        ValueError: If no contract NumberRange exists for the company

    Example:
        >>> from core.models import Mandant
        >>> from datetime import date
        >>> company = Mandant.objects.first()
        >>> number = get_next_contract_number(company, date(2026, 1, 15))
        >>> print(number)  # "V26-00001"
    """
    if date_obj is None:
        date_obj = date.today()

    # Extract datetime.date from datetime.datetime if needed
    if hasattr(date_obj, 'date'):
        date_obj = date_obj.date()

    # Get two-digit year
    yy = date_obj.year % 100

    with transaction.atomic():
        # Try to get existing contract number range with row-level lock
        try:
            number_range = NumberRange.objects.select_for_update().get(
                company=company,
                target='CONTRACT'
            )
        except NumberRange.DoesNotExist:
            raise ValueError(
                f'Kein Nummernkreis für Verträge konfiguriert für Mandant "{company.name}". '
                'Bitte legen Sie einen Nummernkreis mit Ziel "CONTRACT" an.'
            )

        seq = _advance_sequence(number_range, yy)

        # Generate the formatted number with 'V' prefix for contracts
        # Use format from NumberRange, with 'V' as default prefix
        formatted_number = number_range.format.format(
            prefix='V',  # Default prefix for contracts
            yy=f"{yy:02d}",
            seq=seq
        )

        return formatted_number


def get_next_item_number(date_obj=None):
    """
    Get next number for an item (global, company-independent).

    This function is atomic and race-safe using database transactions and row-level locking.
    Raises ValueError if no ITEM NumberRange is configured.

    Args:
        date_obj: datetime.date or datetime.datetime (defaults to today)

    Returns:
        str: Formatted number string (e.g., "ART26-00001")

    Raises:
        ValueError: If no ITEM NumberRange exists

    Example:
        >>> from datetime import date
        >>> number = get_next_item_number(date(2026, 1, 15))
        >>> print(number)  # "ART26-00001"
    """
    if date_obj is None:
        date_obj = date.today()

    # Extract datetime.date from datetime.datetime if needed
    if hasattr(date_obj, 'date'):
        date_obj = date_obj.date()

    # Get two-digit year
    yy = date_obj.year % 100

    with transaction.atomic():
        # Try to get existing item number range with row-level lock
        try:
            number_range = NumberRange.objects.select_for_update().get(
                target='ITEM'
            )
        except NumberRange.DoesNotExist:
            raise ValueError(
                'Kein Nummernkreis für Artikel konfiguriert. '
                'Bitte legen Sie einen Nummernkreis mit Ziel "ITEM" an.'
            )

        seq = _advance_sequence(number_range, yy)

        # Generate the formatted number with 'ART' prefix for items
        # Use format from NumberRange, with 'ART' as default prefix
        formatted_number = number_range.format.format(
            prefix='ART',  # Default prefix for items
            yy=f"{yy:02d}",
            seq=seq
        )

        return formatted_number


PERSONAL_ACCOUNT_FORMAT = '{seq}'


def _next_personal_account(target, label, config_hint):
    """
    Nächstes Personenkonto (Debitor/Kreditor) vergeben.

    Personenkonten sind rein numerisch und dauerhaft an einen
    Geschäftspartner gebunden. Anders als Beleg- oder Vertragsnummern tragen
    sie deshalb weder Präfix noch Jahresbestandteil, und der Nummernkreis darf
    nicht jährlich zurücksetzen – ein Reset würde im Folgejahr dieselben Konten
    ein zweites Mal vergeben.

    Args:
        target: 'CUSTOMER' oder 'SUPPLIER'
        label: Bezeichnung für Fehlermeldungen (z. B. "Kunden")
        config_hint: Hinweistext zur Einrichtung des Nummernkreises

    Returns:
        str: rein numerisches Personenkonto (z. B. "10000")

    Raises:
        ValueError: Wenn kein passender Nummernkreis konfiguriert ist oder
            dieser jährlich zurücksetzt.
    """
    with transaction.atomic():
        try:
            number_range = NumberRange.objects.select_for_update().get(target=target)
        except NumberRange.DoesNotExist:
            raise ValueError(
                f'Kein Nummernkreis für {label} konfiguriert. {config_hint}'
            )

        if number_range.reset_policy != 'NEVER':
            raise ValueError(
                f'Der Nummernkreis für {label} darf nicht jährlich zurücksetzen: '
                'Ein Personenkonto gehört dauerhaft zu einem Geschäftspartner. '
                'Bitte Reset-Policy auf "NEVER" stellen.'
            )

        # current_year wird für Personenkonten nicht ausgewertet; der Aufruf
        # hält den Wert lediglich konsistent mit dem Rest des Modells.
        seq = _advance_sequence(number_range, number_range.current_year)

        return PERSONAL_ACCOUNT_FORMAT.format(seq=seq)


def get_next_customer_number(date_obj=None):
    """
    Nächstes Debitorenkonto vergeben (global, mandantenunabhängig).

    Race-sicher über ``select_for_update()``.

    Args:
        date_obj: wird nicht mehr ausgewertet. Das Argument bleibt aus
            Kompatibilitätsgründen erhalten: Debitorenkonten sind bewusst
            jahresunabhängig.

    Returns:
        str: rein numerisches Debitorenkonto (z. B. "10000")

    Raises:
        ValueError: Wenn kein CUSTOMER-Nummernkreis existiert oder dieser
            jährlich zurücksetzt.

    Example:
        >>> get_next_customer_number()  # "10000"
    """
    return _next_personal_account(
        'CUSTOMER',
        'Kunden',
        'Bitte legen Sie einen Nummernkreis mit Ziel "CUSTOMER" an '
        '(Startwert 10000, Reset-Policy "NEVER").',
    )


def get_next_supplier_number(date_obj=None):
    """
    Nächstes Kreditorenkonto vergeben (global, mandantenunabhängig).

    Race-sicher über ``select_for_update()``.

    Args:
        date_obj: wird nicht ausgewertet (siehe get_next_customer_number).

    Returns:
        str: rein numerisches Kreditorenkonto (z. B. "70000")

    Raises:
        ValueError: Wenn kein SUPPLIER-Nummernkreis existiert oder dieser
            jährlich zurücksetzt.

    Example:
        >>> get_next_supplier_number()  # "70000"
    """
    return _next_personal_account(
        'SUPPLIER',
        'Lieferanten',
        'Bitte legen Sie einen Nummernkreis mit Ziel "SUPPLIER" an '
        '(Startwert 70000, Reset-Policy "NEVER").',
    )

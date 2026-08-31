"""
Hilfsfunktionen rund um Modellfeld-Metadaten.

Hintergrund: Werte aus der KI-Belegerkennung (Betreff, Zahlungsbedingungen,
Verwendungszweck, Positionstexte …) sind beliebig lang. Ohne Kürzung bricht
das INSERT auf PostgreSQL mit ``DataError: value too long for type character
varying(n)`` ab und der komplette PDF-Upload geht verloren. Ein gekürzter
Freitext ist deutlich besser als ein verworfener Beleg – die Kürzung wird
protokolliert, damit sie nachvollziehbar bleibt.
"""
import logging

logger = logging.getLogger(__name__)

#: Nur ein Auszug landet im Log – der Originalwert kann sehr lang sein.
_LOG_PREVIEW_CHARS = 80


def truncate_to_field(model_or_instance, field_name: str, value):
    """
    Kürze *value* auf die ``max_length`` des Feldes *field_name*.

    Args:
        model_or_instance: Modellklasse oder -instanz, zu der das Feld gehört.
        field_name: Name des Modellfeldes (z. B. ``"payment_terms_text"``).
        value: Der zu kürzende Wert. ``None`` bleibt ``None``; alles andere
            wird in einen String umgewandelt.

    Returns:
        Den (ggf. gekürzten) String bzw. ``None``.
    """
    if value is None:
        return None

    text = value if isinstance(value, str) else str(value)
    max_length = model_or_instance._meta.get_field(field_name).max_length
    if max_length is None or len(text) <= max_length:
        return text

    logger.warning(
        "Wert für %s.%s auf %s Zeichen gekürzt (war %s Zeichen): %r…",
        model_or_instance._meta.label,
        field_name,
        max_length,
        len(text),
        text[:_LOG_PREVIEW_CHARS],
    )
    return text[:max_length]


def set_truncated(instance, field_name: str, value) -> None:
    """Setze *value* auf *instance*, gekürzt auf die Feldlänge."""
    setattr(instance, field_name, truncate_to_field(instance, field_name, value))

"""
Signale der Auftragsverwaltung

Rücknahme der Projektabrechnung: Wird ein Rechnungsentwurf (oder eine einzelne
Position daraus) gelöscht, dürfen die zugehörigen Zeiterfassungen nicht als
abgerechnet zurückbleiben - sonst verschwinden Stunden lautlos aus der
Abrechnung. Bei einem bereits finalisierten Beleg bleibt die Abrechnung
dagegen bestehen; dort ist der Weg die Gutschrift, nicht das Löschen.
"""
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, TimeEntry

#: Attribut, unter dem die betroffenen Zeiterfassungen zwischen ``pre_delete``
#: und ``post_delete`` an der Position gemerkt werden.
_PENDING_ATTR = '_project_billing_pending_time_entry_ids'


@receiver(pre_delete, sender=SalesDocumentLine)
def remember_billed_time_entries(sender, instance, **kwargs):
    """
    Betroffene Zeiterfassungen vor dem Löschen merken.

    Django setzt die ``SET_NULL``-Verweise (``TimeEntry.invoice_line``) bereits
    *vor* dem ``post_delete``-Signal auf NULL. Danach ist die Zuordnung nicht
    mehr auffindbar, deshalb wird sie hier gesichert. Auch der Belegstatus wird
    hier gelesen: Beim Löschen eines ganzen Belegs existiert die Belegzeile zum
    Zeitpunkt von ``post_delete`` unter Umständen nicht mehr.
    """
    status = SalesDocument.objects.filter(
        pk=instance.document_id
    ).values_list('status', flat=True).first()

    if status != 'DRAFT':
        setattr(instance, _PENDING_ATTR, [])
        return

    setattr(
        instance,
        _PENDING_ATTR,
        list(
            TimeEntry.objects.filter(invoice_line_id=instance.pk).values_list('pk', flat=True)
        ),
    )


@receiver(post_delete, sender=SalesDocumentLine)
def reset_time_entries_of_deleted_line(sender, instance, **kwargs):
    """
    Zeiterfassungen einer gelöschten Entwurfsposition wieder auf offen setzen.

    Erst nach dem tatsächlichen Löschen - schlägt das Löschen fehl, bleibt die
    Abrechnung unverändert.
    """
    entry_ids = getattr(instance, _PENDING_ATTR, None)
    if not entry_ids:
        return

    TimeEntry.objects.filter(pk__in=entry_ids).update(
        is_billed=False,
        billed_at=None,
        invoice_line=None,
    )
    setattr(instance, _PENDING_ATTR, [])

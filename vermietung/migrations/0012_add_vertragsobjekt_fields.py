# Generated manually on 2025-12-27

from django.db import migrations, models
from decimal import Decimal


def set_default_preis_from_mietobjekt(apps, schema_editor):
    """
    Set default preis value from mietobjekt.mietpreis for existing VertragsObjekt entries.
    This ensures existing data has valid price values after adding the non-nullable field.
    """
    VertragsObjekt = apps.get_model('vermietung', 'VertragsObjekt')
    MietObjekt = apps.get_model('vermietung', 'MietObjekt')
    
    for vo in VertragsObjekt.objects.all():
        # Get the mietobjekt to retrieve its price
        try:
            mietobjekt = MietObjekt.objects.get(pk=vo.mietobjekt_id)
            vo.preis = mietobjekt.mietpreis
            vo.save(update_fields=['preis'])
        except MietObjekt.DoesNotExist:
            # Fallback to 0 if mietobjekt doesn't exist
            vo.preis = Decimal('0.00')
            vo.save(update_fields=['preis'])


class Migration(migrations.Migration):

    dependencies = [
        ('vermietung', '0011_merge_20251226_2249'),
    ]

    operations = [
        # Add preis field with temporary default
        migrations.AddField(
            model_name='vertragsobjekt',
            name='preis',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Preis für dieses Mietobjekt im Vertrag',
                max_digits=10,
                verbose_name='Preis'
            ),
            preserve_default=False,
        ),
        # Populate preis from mietobjekt
        migrations.RunPython(
            set_default_preis_from_mietobjekt,
            reverse_code=migrations.RunPython.noop
        ),
        # Add anzahl field with default 1
        migrations.AddField(
            model_name='vertragsobjekt',
            name='anzahl',
            field=models.IntegerField(
                default=1,
                help_text='Anzahl der gemieteten Einheiten',
                verbose_name='Anzahl'
            ),
        ),
        # Add zugang field (nullable)
        migrations.AddField(
            model_name='vertragsobjekt',
            name='zugang',
            field=models.DateField(
                blank=True,
                help_text='Datum des Zugangs (Übernahme)',
                null=True,
                verbose_name='Zugang'
            ),
        ),
        # Add abgang field (nullable)
        migrations.AddField(
            model_name='vertragsobjekt',
            name='abgang',
            field=models.DateField(
                blank=True,
                help_text='Datum des Abgangs (Rückgabe)',
                null=True,
                verbose_name='Abgang'
            ),
        ),
        # Add status field with default 'AKTIV'
        migrations.AddField(
            model_name='vertragsobjekt',
            name='status',
            field=models.CharField(
                choices=[('AKTIV', 'Aktiv'), ('BEENDET', 'Beendet')],
                default='AKTIV',
                help_text='Status dieses Mietobjekts im Vertrag',
                max_length=20,
                verbose_name='Status'
            ),
        ),
    ]

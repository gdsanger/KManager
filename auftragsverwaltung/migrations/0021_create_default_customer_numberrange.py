# Generated migration for creating default CUSTOMER NumberRange

from django.db import migrations


def create_default_customer_numberrange(apps, schema_editor):
    """Create a default CUSTOMER NumberRange if it doesn't exist."""
    NumberRange = apps.get_model('auftragsverwaltung', 'NumberRange')

    # Only create if no CUSTOMER NumberRange exists
    if not NumberRange.objects.filter(target='CUSTOMER').exists():
        NumberRange.objects.create(
            target='CUSTOMER',
            reset_policy='YEARLY',
            format='{prefix}{yy}-{seq:05d}',
            current_year=0,
            current_seq=0
        )


def reverse_create_default_customer_numberrange(apps, schema_editor):
    """Remove the default CUSTOMER NumberRange (reverse migration)."""
    NumberRange = apps.get_model('auftragsverwaltung', 'NumberRange')
    NumberRange.objects.filter(target='CUSTOMER').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auftragsverwaltung', '0020_add_customer_numberrange_target'),
    ]

    operations = [
        migrations.RunPython(
            create_default_customer_numberrange,
            reverse_create_default_customer_numberrange
        ),
    ]

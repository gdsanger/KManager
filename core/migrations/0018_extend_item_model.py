# Generated migration for extending Item model with full article master data

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_add_tax_accounting_fields'),
    ]

    operations = [
        # Add new fields with defaults/nullable first
        migrations.AddField(
            model_name='item',
            name='article_no',
            field=models.CharField(
                max_length=100,
                null=True,  # Temporarily nullable
                verbose_name='Artikelnummer',
                help_text='Eindeutige Artikelnummer (global)'
            ),
        ),
        migrations.AddField(
            model_name='item',
            name='short_text_1',
            field=models.CharField(
                max_length=200,
                default='',  # Temporary default
                verbose_name='Kurztext 1',
                help_text='Primärer Kurztext'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='item',
            name='short_text_2',
            field=models.CharField(
                max_length=200,
                blank=True,
                default='',
                verbose_name='Kurztext 2',
                help_text='Optionaler zweiter Kurztext'
            ),
        ),
        migrations.AddField(
            model_name='item',
            name='long_text',
            field=models.TextField(
                blank=True,
                default='',
                verbose_name='Langtext',
                help_text='Detaillierte Beschreibung'
            ),
        ),
        migrations.AddField(
            model_name='item',
            name='net_price',
            field=models.DecimalField(
                max_digits=12,
                decimal_places=2,
                default=Decimal('0.00'),
                verbose_name='Verkaufspreis netto',
                help_text='Netto-Verkaufspreis'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='item',
            name='purchase_price',
            field=models.DecimalField(
                max_digits=12,
                decimal_places=2,
                default=Decimal('0.00'),
                verbose_name='Einkaufspreis netto',
                help_text='Netto-Einkaufspreis'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='item',
            name='cost_type_1',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='items_cost_type_1',
                to='core.kostenart',
                null=True,  # Temporarily nullable
                verbose_name='Kostenart 1'
            ),
        ),
        migrations.AddField(
            model_name='item',
            name='cost_type_2',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name='items_cost_type_2',
                to='core.kostenart',
                verbose_name='Kostenart 2'
            ),
        ),
        migrations.AddField(
            model_name='item',
            name='item_type',
            field=models.CharField(
                max_length=20,
                choices=[('MATERIAL', 'Material'), ('SERVICE', 'Dienstleistung')],
                default='MATERIAL',
                verbose_name='Artikeltyp',
                help_text='Klassifizierung: Material oder Dienstleistung'
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='item',
            name='is_discountable',
            field=models.BooleanField(
                default=True,
                verbose_name='Rabattfähig',
                help_text='Gibt an, ob dieser Artikel rabattfähig ist'
            ),
        ),
        
        # Remove old fields
        migrations.RemoveField(
            model_name='item',
            name='name',
        ),
        migrations.RemoveField(
            model_name='item',
            name='description',
        ),
        migrations.RemoveField(
            model_name='item',
            name='unit_price_net',
        ),
        
        # Now alter article_no and cost_type_1 to be required
        migrations.AlterField(
            model_name='item',
            name='article_no',
            field=models.CharField(
                max_length=100,
                unique=True,
                verbose_name='Artikelnummer',
                help_text='Eindeutige Artikelnummer (global)'
            ),
        ),
        migrations.AlterField(
            model_name='item',
            name='cost_type_1',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='items_cost_type_1',
                to='core.kostenart',
                verbose_name='Kostenart 1'
            ),
        ),
        
        # Update model metadata
        migrations.AlterModelOptions(
            name='item',
            options={
                'verbose_name': 'Artikel/Leistung',
                'verbose_name_plural': 'Artikel/Leistungen',
                'ordering': ['article_no']
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='item',
            index=models.Index(fields=['article_no'], name='core_item_article_idx'),
        ),
        migrations.AddIndex(
            model_name='item',
            index=models.Index(fields=['is_active'], name='core_item_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='item',
            index=models.Index(fields=['item_type'], name='core_item_item_type_idx'),
        ),
        
        # Add constraints
        migrations.AddConstraint(
            model_name='item',
            constraint=models.UniqueConstraint(
                fields=['article_no'],
                name='item_article_no_unique',
                violation_error_message='Ein Artikel mit dieser Artikelnummer existiert bereits.'
            ),
        ),
        migrations.AddConstraint(
            model_name='item',
            constraint=models.CheckConstraint(
                check=models.Q(net_price__gte=0),
                name='item_net_price_non_negative',
                violation_error_message='Der Verkaufspreis darf nicht negativ sein.'
            ),
        ),
        migrations.AddConstraint(
            model_name='item',
            constraint=models.CheckConstraint(
                check=models.Q(purchase_price__gte=0),
                name='item_purchase_price_non_negative',
                violation_error_message='Der Einkaufspreis darf nicht negativ sein.'
            ),
        ),
    ]

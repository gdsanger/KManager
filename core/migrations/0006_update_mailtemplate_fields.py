# Generated manually for MailTemplate field updates

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_vat_to_kostenart'),
    ]

    operations = [
        # Rename message_html to message
        migrations.RenameField(
            model_name='mailtemplate',
            old_name='message_html',
            new_name='message',
        ),
        # Rename cc_copy_to to cc_address
        migrations.RenameField(
            model_name='mailtemplate',
            old_name='cc_copy_to',
            new_name='cc_address',
        ),
        # Add is_active field with default True
        migrations.AddField(
            model_name='mailtemplate',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Template aktiv / deaktiviert', verbose_name='Aktiv'),
        ),
        # Add created_at field
        migrations.AddField(
            model_name='mailtemplate',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Erstellt am'),
            preserve_default=False,
        ),
        # Add updated_at field
        migrations.AddField(
            model_name='mailtemplate',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am'),
        ),
        # Change key field from CharField to SlugField
        migrations.AlterField(
            model_name='mailtemplate',
            name='key',
            field=models.SlugField(help_text='Technischer Identifier (z.B. issue-created-confirmation)', max_length=100, unique=True, verbose_name='Template Key'),
        ),
        # Update subject field with help_text
        migrations.AlterField(
            model_name='mailtemplate',
            name='subject',
            field=models.CharField(help_text='Betreff der E-Mail, Platzhalter erlaubt', max_length=255, verbose_name='Betreff'),
        ),
        # Update message field with help_text
        migrations.AlterField(
            model_name='mailtemplate',
            name='message',
            field=models.TextField(help_text='Inhalt der E-Mail (Markdown oder HTML, Platzhalter erlaubt)', verbose_name='Nachricht'),
        ),
        # Make from_name optional
        migrations.AlterField(
            model_name='mailtemplate',
            name='from_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Absendername'),
        ),
        # Make from_address optional
        migrations.AlterField(
            model_name='mailtemplate',
            name='from_address',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Absenderadresse'),
        ),
        # Update cc_address verbose_name
        migrations.AlterField(
            model_name='mailtemplate',
            name='cc_address',
            field=models.EmailField(blank=True, max_length=254, verbose_name='CC-Adresse'),
        ),
    ]

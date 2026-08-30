"""Formulare des Finanzen-Moduls."""
from datetime import date

from django import forms

from core.models import Mandant

from .models import CompanyAccountingSettings


PERIOD_CHOICES = [
    ('MONTH', 'Monat'),
    ('QUARTER', 'Quartal'),
    ('YEAR', 'Jahr'),
]

MONTH_CHOICES = [
    (1, 'Januar'), (2, 'Februar'), (3, 'März'), (4, 'April'),
    (5, 'Mai'), (6, 'Juni'), (7, 'Juli'), (8, 'August'),
    (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Dezember'),
]

QUARTER_CHOICES = [
    (1, '1. Quartal (Jan–Mär)'),
    (2, '2. Quartal (Apr–Jun)'),
    (3, '3. Quartal (Jul–Sep)'),
    (4, '4. Quartal (Okt–Dez)'),
]

# Erstes Jahr, für das ein Buchungsstapel sinnvoll ist.
FIRST_EXPORT_YEAR = 2020


def _year_choices():
    """Auswahlliste der Jahre bis einschließlich des laufenden Jahres."""
    current = date.today().year
    return [(y, str(y)) for y in range(current + 1, FIRST_EXPORT_YEAR - 1, -1)]


class DatevExportForm(forms.Form):
    """
    Zeitraumauswahl für den DATEV-Buchungsstapel.

    Monat/Quartal/Jahr statt freier Datumsfelder: Ein Buchungsstapel wird
    üblicherweise für eine abgeschlossene Periode erzeugt, und die Periode
    darf nicht über einen Jahreswechsel gehen.
    """

    company = forms.ModelChoiceField(
        queryset=Mandant.objects.all().order_by('name'),
        label='Mandant',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    period_type = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial='MONTH',
        label='Zeitraum',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    year = forms.TypedChoiceField(
        choices=_year_choices,
        coerce=int,
        label='Jahr',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    month = forms.TypedChoiceField(
        choices=MONTH_CHOICES,
        coerce=int,
        required=False,
        label='Monat',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quarter = forms.TypedChoiceField(
        choices=QUARTER_CHOICES,
        coerce=int,
        required=False,
        label='Quartal',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    include_exported = forms.BooleanField(
        required=False,
        label='Bereits exportierte Belege erneut aufnehmen',
        help_text=(
            'Nur für den bewussten Wiederholungsexport nach einem Fehlimport. '
            'Standardmäßig bleiben exportierte Belege außen vor.'
        ),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = date.today()
        self.fields['year'].initial = today.year
        self.fields['month'].initial = today.month
        self.fields['quarter'].initial = (today.month - 1) // 3 + 1
        if not self.initial.get('company') and not self.data:
            first = Mandant.objects.order_by('name').first()
            if first:
                self.fields['company'].initial = first.pk

    def clean(self):
        cleaned = super().clean()
        period_type = cleaned.get('period_type')

        if period_type == 'MONTH' and not cleaned.get('month'):
            self.add_error('month', 'Bitte einen Monat auswählen.')
        if period_type == 'QUARTER' and not cleaned.get('quarter'):
            self.add_error('quarter', 'Bitte ein Quartal auswählen.')
        return cleaned

    def period(self):
        """
        Gewählten Zeitraum als (von, bis) liefern – beide Grenzen inklusive.

        Returns:
            tuple(datetime.date, datetime.date)
        """
        import calendar

        year = self.cleaned_data['year']
        period_type = self.cleaned_data['period_type']

        if period_type == 'YEAR':
            return date(year, 1, 1), date(year, 12, 31)

        if period_type == 'QUARTER':
            quarter = self.cleaned_data['quarter']
            first_month = (quarter - 1) * 3 + 1
            last_month = first_month + 2
        else:
            first_month = last_month = self.cleaned_data['month']

        last_day = calendar.monthrange(year, last_month)[1]
        return date(year, first_month, 1), date(year, last_month, last_day)

    def period_label(self):
        """Sprechende Bezeichnung des Zeitraums für die Anzeige."""
        year = self.cleaned_data['year']
        period_type = self.cleaned_data['period_type']
        if period_type == 'YEAR':
            return str(year)
        if period_type == 'QUARTER':
            return f'Q{self.cleaned_data["quarter"]}/{year}'
        return f'{dict(MONTH_CHOICES)[self.cleaned_data["month"]]} {year}'


class CompanyAccountingSettingsForm(forms.ModelForm):
    """
    Buchhaltungseinstellungen eines Mandanten pflegen.

    `company` ist bewusst kein Formularfeld: Der Mandant steht in der URL und
    ist über die OneToOne-Beziehung eindeutig – ein Auswahlfeld könnte den
    Datensatz sonst versehentlich einem anderen Mandanten zuordnen.

    Die Plausibilisierung (Sachkonten nur Ziffern, Sachkontenlänge 4–8) liegt
    in `CompanyAccountingSettings.clean()` und greift über die
    ModelForm-Validierung, sodass Fehler am jeweiligen Feld erscheinen.
    """

    class Meta:
        model = CompanyAccountingSettings
        fields = [
            'datev_consultant_number',
            'datev_client_number',
            'tax_number',
            'account_length',
            'fiscal_year_start',
            'revenue_account_0',
            'revenue_account_7',
            'revenue_account_19',
            'bank_account',
            'cash_account',
            'clearing_account',
        ]
        widgets = {
            'datev_consultant_number': forms.TextInput(attrs={'class': 'form-control'}),
            'datev_client_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'account_length': forms.NumberInput(attrs={'class': 'form-control', 'min': 4, 'max': 8}),
            'fiscal_year_start': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'revenue_account_0': forms.TextInput(attrs={'class': 'form-control'}),
            'revenue_account_7': forms.TextInput(attrs={'class': 'form-control'}),
            'revenue_account_19': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'cash_account': forms.TextInput(attrs={'class': 'form-control'}),
            'clearing_account': forms.TextInput(attrs={'class': 'form-control'}),
        }

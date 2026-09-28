from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0014_usercreditsignal'),
    ]

    operations = [
        # ElectricityTariff: add effective_from / effective_to for quarterly versioning
        migrations.AddField(
            model_name='electricitytariff',
            name='effective_from',
            field=models.DateField(
                null=True, blank=True,
                help_text='Date from which this tariff applies',
            ),
        ),
        migrations.AddField(
            model_name='electricitytariff',
            name='effective_to',
            field=models.DateField(
                null=True, blank=True,
                help_text='Last date this tariff applies (null = open-ended)',
            ),
        ),
        # TariffBlock: lifeline flag + non-lifeline fallback rate
        migrations.AddField(
            model_name='tariffblock',
            name='is_lifeline_block',
            field=models.BooleanField(
                default=False,
                help_text='If true, the rate applies only to lifeline-eligible customers',
            ),
        ),
        migrations.AddField(
            model_name='tariffblock',
            name='non_lifeline_rate',
            field=models.DecimalField(
                max_digits=8, decimal_places=2, null=True, blank=True,
                help_text='Rate for ineligible customers in a lifeline block',
            ),
        ),
    ]

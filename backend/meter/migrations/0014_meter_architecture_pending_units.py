from decimal import Decimal
from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('meter', '0013_meter_deactivated_at_meter_deactivated_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='meter',
            name='architecture',
            field=models.CharField(
                max_length=3,
                choices=[('STS', 'STS (token-based)'), ('AMI', 'AMI (networked)')],
                default='STS',
                help_text='STS = token keypad entry; AMI = networked, direct balance update',
            ),
        ),
        migrations.AddField(
            model_name='meter',
            name='pending_units',
            field=models.DecimalField(
                max_digits=20,
                decimal_places=2,
                default=Decimal('0.00'),
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
                help_text='Units credited but not yet activated via STS token (STS meters only)',
            ),
        ),
    ]

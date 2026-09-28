# Generated manually for ThingsBoard low-units webhook support

import django.core.validators
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('meter', '0015_merge_20260616_1339'),
    ]

    operations = [
        migrations.CreateModel(
            name='MeterNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('create_date', models.DateTimeField(auto_now_add=True)),
                ('modify_date', models.DateTimeField(auto_now=True)),
                ('device_token', models.CharField(blank=True, default='', max_length=128)),
                ('notification_type', models.CharField(choices=[('LOW_UNITS', 'Low units')], default='LOW_UNITS', max_length=32)),
                ('units_kwh', models.DecimalField(decimal_places=4, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('occurred_at', models.DateTimeField()),
                ('is_read', models.BooleanField(default=False)),
                ('message', models.CharField(blank=True, default='', max_length=255)),
                ('meter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='meter.meter')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meter_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-occurred_at', '-create_date'],
            },
        ),
        migrations.AddIndex(
            model_name='meternotification',
            index=models.Index(fields=['user', 'is_read', '-occurred_at'], name='meter_meter_user_id_6f0a2a_idx'),
        ),
        migrations.AddIndex(
            model_name='meternotification',
            index=models.Index(fields=['device_token'], name='meter_meter_device__a1b2c3_idx'),
        ),
    ]

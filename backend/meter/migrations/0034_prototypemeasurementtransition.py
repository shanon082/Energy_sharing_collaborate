import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meter', '0033_ac_lab_sandbox_environment'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrototypeMeasurementTransition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transition_id', models.UUIDField(unique=True)),
                ('receipt_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('state', models.CharField(choices=[('PREPARED', 'Prepared'), ('COMMITTED', 'Committed')], default='PREPARED', max_length=9)),
                ('had_baseline', models.BooleanField()),
                ('old_baseline_wh', models.PositiveBigIntegerField(null=True)),
                ('baseline_wh', models.PositiveBigIntegerField()),
                ('application_counter', models.PositiveBigIntegerField()),
                ('credited_uwh', models.PositiveBigIntegerField()),
                ('consumed_uwh', models.PositiveBigIntegerField()),
                ('uncertain_uwh', models.PositiveBigIntegerField()),
                ('payload', models.JSONField()),
                ('prepared_at', models.DateTimeField(auto_now_add=True)),
                ('committed_at', models.DateTimeField(null=True)),
                ('device', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='measurement_transition', to='meter.prototypedevice')),
            ],
        ),
    ]

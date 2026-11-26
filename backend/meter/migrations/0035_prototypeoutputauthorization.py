import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meter', '0034_prototypemeasurementtransition'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='prototypedevice',
            name='ac_lab_output_disabled',
        ),
        migrations.AddConstraint(
            model_name='prototypedevice',
            constraint=models.CheckConstraint(
                condition=models.Q(environment__in=['UGX_DEMO', 'SANDBOX'], hardware_class='AC_LAB'),
                name='ac_lab_device_domain',
            ),
        ),
        migrations.CreateModel(
            name='PrototypeOutputAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('ACTIVE', 'Active'), ('REVOKED', 'Revoked'), ('EXPIRED', 'Expired')], default='ACTIVE', max_length=8)),
                ('restart_policy', models.CharField(choices=[('AUTO', 'Automatic after safety checks'), ('MANUAL', 'Manual arming required')], default='MANUAL', max_length=6)),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('reason', models.CharField(max_length=240)),
                ('evidence', models.JSONField()),
                ('revoked_at', models.DateTimeField(null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='output_authorizations', to='meter.prototypedevice')),
                ('granted_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('revoked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='prototypeoutputauthorization',
            constraint=models.UniqueConstraint(condition=models.Q(('state', 'ACTIVE')), fields=('device',), name='one_active_output_authorization_per_device'),
        ),
        migrations.AddIndex(
            model_name='prototypeoutputauthorization',
            index=models.Index(fields=['device', 'state', '-expires_at'], name='meter_proto_device__820841_idx'),
        ),
        migrations.CreateModel(
            name='PrototypeOutputAuthorizationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('GRANTED', 'Granted'), ('REVOKED', 'Revoked'), ('EXPIRED', 'Expired')], max_length=7)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('reason', models.CharField(max_length=240)),
                ('details', models.JSONField(default=dict)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('authorization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='meter.prototypeoutputauthorization')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='output_authorization_events', to='meter.prototypedevice')),
            ],
        ),
        migrations.AddConstraint(
            model_name='prototypeoutputauthorizationevent',
            constraint=models.UniqueConstraint(
                fields=('authorization', 'action'),
                name='one_output_authorization_event_per_action',
            ),
        ),
    ]

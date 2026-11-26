from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('meter', '0035_prototypeoutputauthorization')]
    operations = [
        migrations.AddField('prototypedevice', 'recovery_enabled', models.BooleanField(default=False)),
        migrations.AddField('prototypedevice', 'recovery_pending', models.BooleanField(default=False)),
        migrations.AddField('prototypedevice', 'recovery_target_consumed_uwh', models.PositiveBigIntegerField(default=0)),
        migrations.AddField('prototypedevice', 'recovery_target_wh', models.PositiveBigIntegerField(default=0)),
        migrations.AddField('prototypecommand', 'checkpoint_required', models.BooleanField(default=False)),
        migrations.AddField('prototypecommand', 'credit_checkpoint', models.JSONField(null=True)),
        migrations.AddField('prototypetelemetry', 'recovery_settled', models.BooleanField(default=False)),
    ]

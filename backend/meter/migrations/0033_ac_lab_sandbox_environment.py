from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('meter', '0032_prototypedevice_prototypecommand_prototypeboot_and_more')]
    operations = [
        migrations.RemoveConstraint(model_name='prototypedevice', name='ac_lab_output_disabled'),
        migrations.AddConstraint(model_name='prototypedevice', constraint=models.CheckConstraint(
            condition=models.Q(environment__in=['UGX_DEMO', 'SANDBOX'], hardware_class='AC_LAB', output_enabled=False),
            name='ac_lab_output_disabled')),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_user_totp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='lifeline_eligible',
            field=models.BooleanField(
                default=True,
                help_text='Pilot default: True for all domestic users. Set by recompute_lifeline_eligibility() once 6-month history is available.',
            ),
        ),
    ]

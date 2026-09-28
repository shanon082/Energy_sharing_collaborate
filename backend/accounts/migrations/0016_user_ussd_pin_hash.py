from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_user_must_change_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="ussd_pin_hash",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]

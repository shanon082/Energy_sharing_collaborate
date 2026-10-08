from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transactions", "0009_paymentintent_purchase_accounting")]

    operations = [
        migrations.AddField(
            model_name="paymentintent", name="client_request_id",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
    ]

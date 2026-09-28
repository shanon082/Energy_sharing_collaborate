from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0016_alter_tariffblock_is_lifeline_block_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='loanrepayment',
            name='paid_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who paid on behalf of the loan owner (null = self-payment)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='third_party_payments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='loanrepayment',
            name='is_anonymous',
            field=models.BooleanField(
                default=False,
                help_text='Whether the payer chose to stay anonymous to the loan owner',
            ),
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('loan', '0013_alter_loanapplication_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserCreditSignal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment_history', models.CharField(choices=[('GOOD', 'Good'), ('FAIR', 'Fair'), ('POOR', 'Poor')], max_length=10)),
                ('energy_consumption', models.CharField(choices=[('STABLE', 'Stable'), ('MODERATE', 'Moderate'), ('ERRATIC', 'Erratic')], max_length=10)),
                ('financial_capacity', models.CharField(choices=[('STRONG', 'Strong'), ('AVERAGE', 'Average'), ('WEAK', 'Weak')], max_length=10)),
                ('source', models.CharField(default='DUMMY_THIRD_PARTY', max_length=100)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credit_signal', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]


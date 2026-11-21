from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'

    def ready(self):
        import transactions.signals  # noqa: F401
        from backend.ugx_authorization import validate_configuration
        validate_configuration()
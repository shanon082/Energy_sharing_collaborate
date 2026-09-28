from django.apps import AppConfig


class MeterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meter'
    
    def ready(self):
        import meter.signals

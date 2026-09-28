from django.apps import AppConfig


class AdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin'
    label = 'portal_admin'  # avoids collision with django.contrib.admin label
    verbose_name = 'Administration'
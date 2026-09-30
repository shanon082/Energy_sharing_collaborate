from backend.settings_utils import get_env_variable


# Private email
EMAIL_HOST = get_env_variable("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = get_env_variable("EMAIL_PORT", 587)
EMAIL_USE_TLS = False
EMAIL_USE_SSL = True
EMAIL_HOST_USER = get_env_variable("EMAIL_HOST_USER", "gpawateam@gmail.com")
EMAIL_HOST_PASSWORD = get_env_variable("EMAIL_HOST_PASSWORD", "")
DEFAULT_EMAIL_SENDER = get_env_variable("DEFAULT_EMAIL_SENDER", "gpawateam@gmail.com")

# print(EMAIL_HOST)
# print(DEFAULT_EMAIL_SENDER)

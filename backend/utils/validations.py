import re
from rest_framework.serializers import ValidationError


def validate_password(password):
    error = (
        "Ensure password has an uppercase, lowercase, "
        "a numerical character and no leading or "
        "trailing spaces."
    )
    regex = r"(?P<password>((?=\S*[A-Z])(?=\S*[a-z])(?=\S*\d)\S))"

    if re.compile(regex).search(password) is None:
        raise ValidationError(error)
    return None

import re

METER_NO_MAX_LEN = 11
METER_NUMBER_MESSAGE = "Enter your 11-digit meter number."


def normalize_meter_no(value: str) -> str:
    return value.strip() if isinstance(value, str) else ""


def validate_meter_no(value: str) -> tuple[bool, str]:
    meter_no = normalize_meter_no(value)
    if not re.fullmatch(r"[0-9]{11}", meter_no):
        return False, METER_NUMBER_MESSAGE
    return True, meter_no

METER_NO_MAX_LEN = 100


def normalize_meter_no(value: str) -> str:
    return (value or "").strip()


def validate_meter_no(value: str) -> tuple[bool, str]:
    meter_no = normalize_meter_no(value)
    if not meter_no:
        return False, "Meter number is required."
    if len(meter_no) > METER_NO_MAX_LEN:
        return False, f"Meter number must be at most {METER_NO_MAX_LEN} characters."
    return True, meter_no

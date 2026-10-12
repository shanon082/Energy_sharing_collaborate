"""Format validation only. This does not establish ownership of a phone."""
import re


def normalize_ugandan_phone(value):
    if not isinstance(value, str):
        raise ValueError("Use 0771000111, 256771000111 or +256771000111.")
    value = value.strip()
    if re.fullmatch(r"0[0-9]{9}", value):
        return "+256" + value[1:]
    if re.fullmatch(r"\+?256[0-9]{9}", value):
        return "+" + value.lstrip("+")
    raise ValueError("Use 0771000111, 256771000111 or +256771000111; digits only.")


def phone_aliases(value):
    canonical = normalize_ugandan_phone(value)
    return (canonical, canonical[1:], "0" + canonical[4:])

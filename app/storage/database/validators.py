import re


def bank_name_ok(name: str) -> bool:
    return bool(re.fullmatch("[A-Z_][A-Z0-9_]*", name))

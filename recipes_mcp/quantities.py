"""Amount parsing, scaling and pretty formatting.

Everything here works on plain floats + unit strings so storage stays simple,
while output to the human (or agent) is a friendly mixed-fraction string.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

# Common cooking denominators, most readable first.
_DENOMINATORS = (8, 4, 3, 2, 6, 16)

_VOLUME_UNITS = {
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "tbsp": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "floz": "fl oz",
    "fl oz": "fl oz",
    "cup": "cup",
    "cups": "cup",
    "pint": "pint",
    "pints": "pint",
    "quart": "quart",
    "quarts": "quart",
    "gallon": "gallon",
    "gallons": "gallon",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "liter",
    "liter": "liter",
    "liters": "liter",
}

_MASS_UNITS = {
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
}


def normalize_unit(unit: str | None) -> str | None:
    """Canonicalize common unit spellings ('tbls'->'tbsp' style aliases)."""
    if unit is None:
        return None
    u = unit.strip().lower()
    if not u:
        return None
    return _VOLUME_UNITS.get(u) or _MASS_UNITS.get(u) or u


def parse_amount(value) -> float:
    """Accept numbers or friendly strings like '1 1/2' or '0.5'."""
    if isinstance(value, bool):
        raise ValueError("amount must be a number, not a boolean")
    if isinstance(value, (int, float)):
        amount = float(value)
    elif isinstance(value, str):
        amount = _parse_amount_string(value.strip())
    else:
        raise ValueError(f"amount must be a number or string, got {type(value).__name__}")
    if not math.isfinite(amount):
        raise ValueError("amount must be finite")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    return amount


def _parse_amount_string(text: str) -> float:
    # Whole, mixed ('1 1/2'), fractional ('1/2'), or decimal ('0.5').
    parts = text.split()
    try:
        if len(parts) == 1:
            if "/" in parts[0]:
                return float(Fraction(parts[0]))
            return float(parts[0])
        if len(parts) == 2 and "/" in parts[1]:
            return float(Fraction(parts[0])) + float(Fraction(parts[1]))
    except (ValueError, ZeroDivisionError):
        pass
    raise ValueError(f"could not parse amount: {text!r}")


def scale_amount(amount: float, factor: float) -> float:
    """Scale an amount by factor with gentle rounding noise removal."""
    if factor <= 0:
        raise ValueError("scale factor must be greater than 0")
    scaled = amount * factor
    # Snap tiny float dust (2.5000000004 -> 2.5) without changing real values.
    if abs(scaled - round(scaled)) < 1e-9:
        return float(round(scaled))
    return round(scaled, 4)


def format_amount(amount: float) -> str:
    """Human-friendly amount: '2', '1 1/2', '0.75' -> '3/4'."""
    if amount == int(amount) and amount < 1_000_000:
        return str(int(amount))
    frac = Fraction(amount).limit_denominator(max(*_DENOMINATORS, 64))
    if abs(float(frac) - amount) <= 0.02 and 0 < frac.numerator < 100 * frac.denominator:
        whole, rem = divmod(frac, 1)
        pieces = []
        if whole:
            pieces.append(str(whole))
        if rem:
            pieces.append(f"{rem.numerator}/{rem.denominator}")
        return " ".join(pieces)
    # Fall back to a trimmed decimal.
    text = f"{amount:.3f}".rstrip("0").rstrip(".")
    return text


def _unit_already_in_name(unit: str, item: str) -> bool:
    """True if the item name itself mentions the unit ('corn tortillas' + 'tortillas')."""
    tokens = set(re.findall(r"[a-z0-9]+", item.lower()))
    variants = {unit.lower()}
    if unit.lower().endswith("s"):
        variants.add(unit.lower()[:-1])
    else:
        variants.add(unit.lower() + "s")
    return bool(variants.intersection(tokens))


# (singular, plural) for units we are confident about; anything else stays
# exactly as the user wrote it.
_UNIT_FORMS = {
    "cup": ("cup", "cups"),
    "cans": ("can", "cans"),
    "clove": ("clove", "cloves"),
    "cloves": ("clove", "cloves"),
    "tablespoon": ("tablespoon", "tablespoons"),
    "teaspoon": ("teaspoon", "teaspoons"),
    "ounce": ("ounce", "ounces"),
    "pound": ("pound", "pounds"),
    "lb": ("lb", "lbs"),
    "oz": ("oz", "oz"),
}


def _unit_word(unit: str, count: float) -> str:
    forms = _UNIT_FORMS.get(unit)
    if forms is None:
        return unit
    return forms[1] if count > 1 else forms[0]


def describe_ingredient(item: str, amount: float, unit: str | None, factor: float = 1.0) -> str:
    """One-line '2 cups chickpeas' style description, scaled by factor."""
    scaled = scale_amount(amount, factor)
    pretty = format_amount(scaled)
    canonical = normalize_unit(unit)
    name = item.strip()
    if canonical and not _unit_already_in_name(canonical, name):
        return f"{pretty} {_unit_word(canonical, scaled)} {name}"
    return f"{pretty} {name}"

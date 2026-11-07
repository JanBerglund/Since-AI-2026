"""Conservative numeric parsing and common-unit normalization."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$")
_UNIT_ALIASES: dict[str, tuple[str, Decimal]] = {}


def _register(dimension: str, factor: str, aliases: tuple[str, ...]) -> None:
    for alias in aliases:
        _UNIT_ALIASES[alias.casefold()] = (dimension, Decimal(factor))


_register("length", "1", ("m", "meter", "meters", "metre", "metres"))
_register("length", "0.001", ("mm", "millimeter", "millimeters", "millimetre", "millimetres"))
_register("length", "0.01", ("cm", "centimeter", "centimeters", "centimetre", "centimetres"))
_register("length", "1000", ("km", "kilometer", "kilometers", "kilometre", "kilometres"))
_register("length", "0.3048", ("ft", "foot", "feet"))
_register("length", "0.0254", ("in", "inch", "inches"))
_register("voltage", "1", ("v", "volt", "volts"))
_register("voltage", "1000", ("kv", "kilovolt", "kilovolts"))
_register("frequency", "1", ("hz", "hertz"))
_register("frequency", "1000", ("khz", "kilohertz"))
_register("frequency", "1000000", ("mhz", "megahertz"))
_register("power", "1", ("w", "watt", "watts"))
_register("power", "1000", ("kw", "kilowatt", "kilowatts"))
_register("power", "1000000", ("mw", "megawatt", "megawatts"))
_register("mass", "1", ("kg", "kilogram", "kilograms"))
_register("mass", "1000", ("t", "tonne", "tonnes", "metric ton", "metric tons"))
_register("volume", "1", ("l", "liter", "liters", "litre", "litres"))
_register(
    "volume",
    "1000",
    ("m3", "cubic meter", "cubic meters", "cubic metre", "cubic metres"),
)
_register(
    "area",
    "1",
    ("m2", "sqm", "square meter", "square meters", "square metre", "square metres"),
)
_register(
    "area",
    "0.000001",
    ("mm2", "square millimeter", "square millimeters", "square millimetre", "square millimetres"),
)
_register(
    "area",
    "0.0001",
    ("cm2", "square centimeter", "square centimeters", "square centimetre", "square centimetres"),
)
_register(
    "area",
    "0.09290304",
    ("ft2", "sq ft", "square foot", "square feet"),
)
_register(
    "area",
    "0.00064516",
    ("in2", "sq in", "square inch", "square inches"),
)
_register("time", "1", ("s", "sec", "second", "seconds"))
_register("time", "60", ("min", "minute", "minutes"))
_register("time", "3600", ("h", "hr", "hour", "hours"))
_register("time", "86400", ("d", "day", "days"))
_register(
    "count",
    "1",
    (
        "count", "counts", "unit", "units", "person", "persons", "people", "pax",
        "passenger", "passengers", "berth", "berths", "engine", "engines", "each", "pcs",
    ),
)


def parse_number(value: str | int | float) -> Decimal | None:
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if not _NUMBER.fullmatch(text):
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def comparable_values(
    value_a: str | int | float,
    unit_a: str,
    value_b: str | int | float,
    unit_b: str,
) -> tuple[Decimal, Decimal] | None:
    number_a = parse_number(value_a)
    number_b = parse_number(value_b)
    if number_a is None or number_b is None:
        return None

    normalized_a = " ".join(unit_a.casefold().split())
    normalized_b = " ".join(unit_b.casefold().split())
    definition_a = _UNIT_ALIASES.get(normalized_a)
    definition_b = _UNIT_ALIASES.get(normalized_b)
    if definition_a is None and definition_b is None:
        return (number_a, number_b) if normalized_a == normalized_b else None
    if definition_a is None or definition_b is None:
        return None
    dimension_a, factor_a = definition_a
    dimension_b, factor_b = definition_b
    if dimension_a != dimension_b:
        return None
    return number_a * factor_a, number_b * factor_b

"""Unit conversions used by every NextBurn experiment (standard library only)."""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONST = json.load(open(os.path.join(ROOT, "config", "constants.json")))

G0 = _CONST["g0_m_s2"]
KPA_PER_PSIA = _CONST["kpa_per_psia"]
KPA_PER_ATM = _CONST["kpa_per_atm"]
AIR_O2_PCT = _CONST["air_o2_pct"]
G_LUNAR = _CONST["lunar_surface_gravity_m_s2"] / G0
G_MARS = _CONST["mars_surface_gravity_m_s2"] / G0

PRESSURE_UNITS = {"kpa": 1.0, "psia": KPA_PER_PSIA, "psi": KPA_PER_PSIA, "atm": KPA_PER_ATM}
SPEED_UNITS = {"cm/s": 1.0, "mm/s": 0.1, "m/s": 100.0}
LENGTH_UNITS = {"cm": 1.0, "mm": 0.1, "m": 100.0, "inch": 2.54, "in": 2.54}
TIME_UNITS = {"s": 1.0, "min": 60.0, "h": 3600.0}
ALLOWED_UNITS = {"-", "%", "% O2", "mol %", "kPa", "psia", "atm", "cm/s", "mm/s", "m/s", "cm", "mm", "m",
                 "s", "min", "ppm", "W", "degC", "RPM", "g"}


def to_kpa(value, unit):
    return value * PRESSURE_UNITS[unit.lower()]


def from_kpa(kpa, unit):
    return kpa / PRESSURE_UNITS[unit.lower()]


def roundtrip_error(value, unit, via="kPa"):
    """Relative error after converting value -> kPa -> unit."""
    back = from_kpa(to_kpa(value, unit), unit)
    return abs(back - value) / abs(value) if value else 0.0


def speed_to_cm_s(value, unit):
    return value * SPEED_UNITS[unit]


def length_to_cm(value, unit):
    return value * LENGTH_UNITS[unit]


def time_to_s(value, unit):
    return value * TIME_UNITS[unit]


def g_from_spin(rpm, radius_m):
    """Centripetal acceleration of a spin, as a fraction of standard gravity."""
    omega = rpm * 2.0 * math.pi / 60.0
    return omega ** 2 * radius_m / G0


def spin_accel_m_s2(rpm, radius_m):
    omega = rpm * 2.0 * math.pi / 60.0
    return omega ** 2 * radius_m


def psia_to_kpa(p):
    return p * KPA_PER_PSIA


def kpa_to_psia(p):
    return p / KPA_PER_PSIA

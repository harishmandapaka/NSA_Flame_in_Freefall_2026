"""Gravity-scaling rules and simple physics used by Experiments 4 and 5."""
import math

from . import units


def predict_ratio(g_ratio, n):
    """Predicted lunar-to-Earth spread-rate ratio: g_ratio raised to the power n."""
    return g_ratio ** n


def implied_exponent(ratio, g_ratio):
    """Exponent n that makes g_ratio ** n equal the measured ratio."""
    return math.log(ratio) / math.log(g_ratio)


def score_rules(rules, observations, hit_pct=10.0):
    """Signed percentage error of each rule against each observation: (predicted - measured) / measured."""
    out = []
    for ob in observations:
        row = dict(ob, rules={})
        for r in rules:
            pred = predict_ratio(ob["g_ratio"], r["n"])
            err = 100.0 * (pred - ob["ratio"]) / ob["ratio"]
            row["rules"][r["id"]] = {"predicted": pred, "error_pct": err, "hit": abs(err) <= hit_pct}
        out.append(row)
    return out


def ratio_band(g_ratio, n_low, n_high):
    """Range of predicted ratios across an exponent band (low ratio first)."""
    a, b = predict_ratio(g_ratio, n_high), predict_ratio(g_ratio, n_low)
    return min(a, b), max(a, b)


def buoyancy_index(g_ratio, p_kpa, p_ref_kpa=units.psia_to_kpa(14.7)):
    """Gravity times the square of pressure relative to sea level (the plan's natural-convection index)."""
    return g_ratio * (p_kpa / p_ref_kpa) ** 2


def burn_distance_cm(rate_cm_s, time_s):
    return rate_cm_s * time_s

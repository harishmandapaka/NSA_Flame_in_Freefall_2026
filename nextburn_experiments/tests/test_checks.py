"""Experiment 2 regression checks. Run with pytest, or with: python tests/run_tests.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import checks, ingest, units  # noqa: E402

GOLDEN = json.load(open(os.path.join(ROOT, "config", "golden_rows.json")))
RAW = ingest.load_ledger()


def test_every_check_passes_on_the_ledger():
    res, _, _ = checks.run_all(RAW, GOLDEN)
    failed = [(r["name"], r["failures"][:3]) for r in res if r["status"] == "FAIL"]
    assert not failed, failed


def test_luci_spin_gives_lunar_gravity_within_2_percent():
    r = checks.luci_g_from_spin(11, 1.22)
    assert r["status"] == "PASS", r


def test_pressure_units_round_trip():
    for u in ("kPa", "psia", "atm"):
        assert units.roundtrip_error(8.2, u) < 1e-3


def test_reference_rows_match_exactly():
    res, _, _ = checks.run_all(RAW, GOLDEN)
    gold = [r for r in res if r["name"] == "check_golden"][0]
    assert gold["status"] == "PASS", gold["failures"]


def test_every_injected_fault_is_detected():
    out = checks.fault_injection(RAW, GOLDEN)
    missed = [f["fault"] for f in out if not f["detected"]]
    assert not missed, missed


def test_no_value_is_invented_for_unstated_fields():
    norm, _ = ingest.normalize(RAW)
    for r in norm:
        if (r["p_text"] or "").strip().lower() == "not stated":
            assert r["p_kpa"] is None and r["p_lo_kpa"] is None and r["p_hi_kpa"] is None, r["row_id"]
        if (r["o2_text"] or "").strip().lower() == "not stated":
            assert r["o2_pct"] is None, r["row_id"]

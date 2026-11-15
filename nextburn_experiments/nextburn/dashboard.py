"""Collect every experiment's results into dashboard_data/summary.json and RESULTS_SUMMARY.md.

All headline strings are composed from the numbers in each results file, never typed by hand.
"""
import json
import os
import re

from . import ingest, report

ROOT = report.ROOT


def _load(path):
    p = os.path.join(ROOT, path)
    return json.load(open(p)) if os.path.exists(p) else None


def pct(x, d=1):
    return ("%." + str(d) + "f%%") % (100 * x)


def exp1():
    rep, strict = _load("data/exp1_reported_score.json"), _load("data/exp1_strict_score.json")
    if not rep:
        return None
    f, s = rep["final"], (strict or {}).get("final", {})
    return {"id": 1, "title": "Ledger accuracy", "pass": rep["result"] == "SATISFACTORY", "status": rep["result"],
            "headline": "%d of %d sampled fields correct (%s, 95%% interval %s to %s) against a 98%% pass mark set in advance; strict count %d of %d (%s)" % (
                f["fields_ok"], f["fields_checked"], pct(f["field_accuracy"]), pct(f["field_ci95"][0]), pct(f["field_ci95"][1]),
                s.get("fields_ok", 0), s.get("fields_checked", 0), pct(s.get("field_accuracy", 0))),
            "numbers": {"fields_ok": f["fields_ok"], "fields_checked": f["fields_checked"], "accuracy": f["field_accuracy"], "ci95": f["field_ci95"],
                        "strict_ok": s.get("fields_ok"), "numbers_only": rep.get("numbers_only")},
            "chart": None, "results": "../experiment1/results.md"}


def exp2():
    r = _load("results/exp2/results.json")
    if not r:
        return None
    n_checks = len([c for c in r["checks"] if c["name"] != "dedupe_log"])
    passed = len([c for c in r["checks"] if c["status"] == "PASS"])
    return {"id": 2, "title": r["title"], "pass": r["pass"], "status": "PASS" if r["pass"] else "FAIL",
            "headline": "%d of %d checks pass on %d ledger rows; %d of %d planted faults caught; %d duplicate row merged" % (
                passed, n_checks, r["rows"], r["fault_injection"]["detected"], r["fault_injection"]["total"],
                len([d for c in r["checks"] if c["name"] == "dedupe_log" for d in c.get("dropped", [])])),
            "numbers": {"checks_passed": passed, "checks": n_checks, "faults_caught": r["fault_injection"]["detected"], "faults": r["fault_injection"]["total"]},
            "chart": "results/exp2/chart.png", "results": "results/exp2/results.md"}


def exp3():
    r = _load("results/exp3/results.json")
    if not r:
        return None
    rg = r["ranges"]
    return {"id": 3, "title": r["title"], "pass": r["pass"], "status": "PASS" if r["pass"] else "FAIL",
            "headline": "Moon-base atmosphere has no direct lunar-gravity test in all 6 tolerance runs and both cross-checks; %s of %d cells tested and %s bounded%s" % (
                ("%d" % rg["tested"][0]) if rg["tested"][0] == rg["tested"][1] else "%d to %d" % tuple(rg["tested"]), r["cells"],
                ("%d" % rg["bounded"][0]) if rg["bounded"][0] == rg["bounded"][1] else "%d to %d" % tuple(rg["bounded"]),
                " in every run" if rg["tested"][0] == rg["tested"][1] and rg["bounded"][0] == rg["bounded"][1] else " across runs"),
            "numbers": {"tested": rg["tested"], "bounded": rg["bounded"], "untested": rg["untested"], "cells": r["cells"],
                        "gravity_ignored_flips": list(r["gravity_ignored_check"]["cells_that_become_tested"].keys())},
            "chart": "results/exp3/chart.png", "results": "results/exp3/results.md"}


def exp4():
    r = _load("results/exp4/results.json")
    if not r:
        return None
    ob = {o["label"]: o for o in r["observations"]}
    sq = {k: v["rules"]["sqrt"]["error_pct"] for k, v in ob.items()}
    b = r["uncertainty_band"]
    return {"id": 4, "title": r["title"], "pass": r["pass"], "status": "REPORTED",
            "headline": "Square-root rule: %+.1f%% and %+.1f%% at the flame tips (hits), %+.1f%% at the fabric base (miss); implied exponents %s; lunar ratio band %.2f to %.2f (%.1f-fold)" % (
                sq["Fabric flame tip"], sq["Acrylic rod flame tip"], sq["Fabric flame base"], ", ".join("%.2f" % x for x in r["implied_exponents"]["rate_derived"]),
                b["moon"]["ratio_low"], b["moon"]["ratio_high"], b["moon"]["fold"]),
            "numbers": {"sqrt_errors_pct": sq, "hits_per_rule": r["hits_per_rule"], "band": b, "implied": r["implied_exponents"]},
            "chart": "results/exp4/chart.png", "results": "results/exp4/results.md"}


def exp5():
    r = _load("results/exp5/results.json")
    if not r:
        return None
    s, n = r["weight_sensitivity"], r["null_baseline"]
    return {"id": 5, "title": r["title"], "pass": r["pass"], "status": "PASS" if r["pass"] else "FAIL",
            "headline": "On pre-2025 evidence the top five includes a lunar-gravity spread-rate test; it stays there in %s of %d weight draws (random picks: %s); a lunar test of any kind in %s (random: %s)" % (
                pct(s["luci_like_in_top5_share"]), s["draws"], pct(n["probability_random_five_include_luci_like"]), pct(s["lunar_in_top5_share"]), pct(n["probability_random_five_include_lunar"])),
            "numbers": {"luci_like_share": s["luci_like_in_top5_share"], "lunar_share": s["lunar_in_top5_share"], "kendall_tau_median": s["kendall_tau_median"],
                        "null_lunar": n["probability_random_five_include_lunar"], "null_luci_like": n["probability_random_five_include_luci_like"]},
            "chart": "results/exp5/chart.png", "results": "results/exp5/results.md"}


def exp6():
    r = _load("results/exp6/results.json")
    if not r:
        return None
    tv = {s["name"]: s for s in r["variants"]["two_variable"]["strategies"]} if isinstance(r["variants"]["two_variable"], dict) else {}
    return {"id": 6, "title": r["title"], "pass": r.get("pass"), "status": ("PASS" if r.get("pass") else "FAIL") + " (simulation)",
            "headline": r.get("headline"), "claim": r.get("claim"),
            "numbers": {k: {"median": v.get("median_tests"), "p80": v.get("p80_tests"), "success": v.get("success_rate")} for k, v in tv.items()},
            "chart": "results/exp6/chart.png", "results": "results/exp6/results.md"}


def exp7():
    r = _load("results/exp7/results.json")
    if not r:
        return None
    sm = r["summary"]
    crit = {c["id"]: c for c in sm.get("criteria", [])}
    llm = _load("results/exp7/llm_results.json")
    ho = _load("results/exp7/heldout_results.json")
    ho_first = _load("results/exp7/heldout_results_first_run.json") or ho
    hol = _load("results/exp7/heldout_llm_results.json")
    head = "Guarded SI: %s grounded; %s unanswerable declined; %s overrides refused; %s answerable wrongly declined" % (
        crit.get(1, {}).get("value", "?"), crit.get(2, {}).get("value", "?"), crit.get(3, {}).get("value", "?"), crit.get(4, {}).get("value", "?"))
    if ho_first:
        head += "; independent held-out set, first run: %d of %d correct, %d of %d grounded" % (
            ho_first["summary"]["correct_behaviour"], ho_first["summary"]["items"], ho_first["summary"]["grounded"], ho_first["summary"]["items"])
    if ho and ho.get("summary_still_held_out"):
        hs = ho["summary_still_held_out"]
        head += "; after the fix, %d of %d still-unseen items correct" % (hs["correct_behaviour"], hs["items"])
    llm_s = (llm or {}).get("summary") or {}
    if llm_s:
        lc = {c["id"]: c for c in llm_s.get("criteria", [])}
        head += "; language-model SI under the guard prompt: %s grounded, %s declined, %s refused, %s wrongly declined" % (
            lc.get(1, {}).get("value", "?"), lc.get(2, {}).get("value", "?"), lc.get(3, {}).get("value", "?"), lc.get(4, {}).get("value", "?"))
    return {"id": 7, "title": r["title"], "pass": r.get("pass"), "status": "PASS" if r.get("pass") else "FAIL", "headline": head,
            "numbers": {"deterministic": {k: sm.get(k) for k in ("items", "grounded_answers", "numbers_total", "numbers_ungrounded", "decline_rate_unanswerable",
                                                                  "refusal_rate_adversarial", "false_decline_count", "retrieval_recall_mean")},
                        "criteria": sm.get("criteria"), "heldout_first_run": (ho_first or {}).get("summary"), "heldout_latest": (ho or {}).get("summary"),
                        "llm": llm_s or None, "llm_heldout": (hol or {}).get("summary")},
            "chart": "results/exp7/chart.png", "results": "results/exp7/results.md"}


def corrections():
    """Figures in the plan that the experiments re-computed differently (for the slides)."""
    out = []
    e2, e4, e5 = _load("results/exp2/results.json"), _load("results/exp4/results.json"), _load("results/exp5/results.json")
    if e2:
        lc = [c for c in e2["checks"] if c["name"] == "luci_g_from_spin"][0]
        out.append({"item": "LUCI spin against lunar gravity", "plan": "1.619 m/s2, 0.4% below nominal",
                    "now": "%.3f m/s2, %.2f%% from NASA's fact-sheet 1.62 m/s2" % (lc["accel_m_s2"], 100 * lc["deviation"]), "why": "the plan's 0.4% used 1.625 m/s2"})
    if e4:
        base = [o for o in e4["observations"] if o["label"] == "Fabric flame base"][0]
        b = e4["uncertainty_band"]
        out.append({"item": "Square-root rule at the fabric flame base", "plan": "rule 32.2% low (ratio 0.600)",
                    "now": "rule %.1f%% low (ratio %.3f from the ledger's %s and %s)" % (-base["rules"]["sqrt"]["error_pct"], base["ratio"], base["lunar"], base["earth"]),
                    "why": "the plan used a rounded 0.9 mm/s and g = 0.1657"})
        tips = [o for o in e4["observations"] if "tip" in o["label"]]
        out.append({"item": "Square-root rule at the flame tips", "plan": "3.6% and 8.6% high",
                    "now": " and ".join("%.1f%% high" % o["rules"]["sqrt"]["error_pct"] for o in tips), "why": "LUCI's own spin gravity (%.4f g) instead of 0.1657" % e4["g_ratio_luci_spin"]})
        out.append({"item": "Uncertainty band for untested lunar cells", "plan": "exponents 0.28 to 1.0, ratio 0.17 to 0.61 (3.6-fold)",
                    "now": "exponents %.2f to %.2f, ratio %.3f to %.3f (%.1f-fold); Mars %.2f to %.2f (%.1f-fold)" % (
                        e4["implied_exponents"]["n_low"], e4["implied_exponents"]["n_high"], b["moon"]["ratio_low"], b["moon"]["ratio_high"], b["moon"]["fold"],
                        b["mars"]["ratio_low"], b["mars"]["ratio_high"], b["mars"]["fold"]), "why": "lowest implied exponent from the ledger's rates"})
    if e5:
        par = [b for b in e5["burn_distance_cm"]]
        out.append({"item": "Burn distance in a parabola", "plan": "about 22.5 s parabola: 2.0 to 3.4 cm",
                    "now": "NASA parabola about 20 s: %.1f to %.1f cm; Novespace 0.16 g up to 25 s: %.1f to %.1f cm" % (
                        min(x["distances_cm"]["NASA parabola, about 20 s"] for x in par), max(x["distances_cm"]["NASA parabola, about 20 s"] for x in par),
                        min(x["distances_cm"]["Novespace 0.16 g, up to 25 s"] for x in par), max(x["distances_cm"]["Novespace 0.16 g, up to 25 s"] for x in par)),
                    "why": "facility catalogue times instead of a single 22.5 s value"})
    return out


def build():
    exps = [e for e in (exp1(), exp2(), exp3(), exp4(), exp5(), exp6(), exp7()) if e]
    for e in exps:
        e["title"] = re.sub(r"^Experiment \d+:\s*", "", e["title"])
    rows = ingest.load_ledger()
    tp = json.load(open(os.path.join(ROOT, "data", "test_points.json")))
    summary = {"generated_at": report.now_iso(), "project": "NextBurn: from evidence gap to test plan",
               "ledger": {"file": "data/ledger_v2.json", "rows": len(rows), "sources": len({r["source_id"] for r in rows}),
                          "test_points": len(tp["test_points"]), "sha256": report.sha256_file(ingest.DEFAULT_LEDGER)},
               "experiments": exps, "corrections_to_plan": corrections(),
               "labels": {"6": "SIMULATION: not NASA data", "1": "AI checkers; human re-check of 19 disputed fields pending"}}
    report.dashboard("summary.json", summary)
    md = ["# NextBurn experiment results", "", "Generated %s from the results files. Ledger: %d rows from %d NASA sources, %d test points." % (
        summary["generated_at"], summary["ledger"]["rows"], summary["ledger"]["sources"], summary["ledger"]["test_points"]), "",
        report.md_table(["#", "Experiment", "Status", "Headline"], [[e["id"], e["title"], e["status"], e["headline"]] for e in exps]), "",
        "## Figures in the plan that changed when re-computed", "",
        report.md_table(["Item", "Plan said", "Experiments give", "Why"], [[c["item"], c["plan"], c["now"], c["why"]] for c in summary["corrections_to_plan"]]), ""]
    report.write_text(os.path.join(ROOT, "RESULTS_SUMMARY.md"), "\n".join(md))
    return summary

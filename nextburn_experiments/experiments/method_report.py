"""Write results/method/results.md and CHECKLIST.md from the six-step results files (no numbers typed by hand)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import report  # noqa: E402

M = os.path.join(ROOT, "results", "method")
L = lambda f: json.load(open(os.path.join(M, f)))


def main():
    s1, s2, s3, s4, s5, s6 = (L("step%d_%s.json" % (i, n)) for i, n in ((1, "summary"), (2, "envelope"), (3, "coverage"), (4, "boundary"), (5, "next_tests"), (6, "fm2")))
    pred = json.load(open(os.path.join(ROOT, "predictions", "fm2_predictions.json")))
    shas = dict(reversed(l.split()) for l in open(os.path.join(ROOT, "predictions", "SHA256SUMS.txt")) if l.strip())
    thin = s3["families"]["thin_fabric"]
    fit = s4["fits"][s4["primary_family"]]
    loo = fit["loo"]
    base_brier = loo["base_rate"] * (1 - loo["base_rate"])
    plan = s5["plan"]["plan"]
    ops = [o for o in s4["operating_points"] if o["material"] == s4["reference_material"]]
    answered = [o for o in ops if o["decision"] != "declined"]
    psi_in = s1["psi_tables"].startswith("included")
    import csv as _csv
    led = list(_csv.DictReader(open(os.path.join(M, "step1_test_point_ledger.csv"))))
    psi = [r for r in led if r["origin"] == "PSI table"]
    psi_note = ("PSI tables: %d rows from %d investigations read from psi.nasa.gov; none states pressure, %d report no outcome, and one PSI-25 column (final CO) was not read. " % (
        len(psi), len({r["sources"] for r in psi}), sum(1 for r in psi if r["outcome"] == "not_reported"))) if psi else ("PSI tables: %s. " % s1["psi_tables"])
    gv = thin["summary_by_gravity"]
    p1 = {p["burn"]: p for p in pred["predictions"]}
    bcfg = json.load(open(os.path.join(ROOT, "config", "boundary_model.json")))
    rows = [
        ["1", "Test-point ledger", "Partly done" if not psi_in else "Done, with gaps",
         "%d test points from %d sources, %d with an outcome; every row has a source and locator; %d outcome quotes checked, %d not found; data checks %s" % (
             s1["test_points"], len(s1["sources"]), s1["with_outcome"], s1["outcome_quotes_checked"], len(s1["outcome_quotes_not_found"]), s1["checks_gate"]),
         psi_note + "Feier and Sacksteder figure data are not digitized; MAPTIS is not used."],
        ["2", "Operating envelope", "Done", "; ".join("%s: %g%% O2, %g psia, %s" % (o["name"], o["o2_pct"], o["p_psia"], {"micro": "microgravity", "lunar": "0.16 g", "mars": "0.38 g"}[o["g_class"]]) for o in s2["operating_points"]),
         "Flow is not an envelope axis (habitat presets set no flow)."],
        ["3", "Binned coverage", "Done",
         "Thin fabrics, envelope bins tested / nearby / none: microgravity %d/%d/%d, Moon %d/%d/%d, Mars %d/%d/%d. Operating points: %s" % (
             gv["micro"]["tested"], gv["micro"]["nearby"], gv["micro"]["none"], gv["lunar"]["tested"], gv["lunar"]["nearby"], gv["lunar"]["none"],
             gv["mars"]["tested"], gv["mars"]["nearby"], gv["mars"]["none"], "; ".join("%s %s" % (o["name"], o["status"]) for o in thin["operating_points"])),
         "Tests with unstated or one-sided pressure are listed but not placed."],
        ["4", "Boundary model with decline", "Done, with a stated weakness",
         "%d observations (%d did not burn); R-hat %.2f; declines on %.0f%% of the map; answers at %d of %d operating-point checks (%s)" % (
             fit["observations"], fit["not_sustained"], fit["max_rhat"], 100 * s4["grid_decline_share"], len(answered), len(ops), ", ".join(sorted({o["name"] for o in answered})) or "none"),
         "Leave-one-out Brier %.3f is worse than always predicting the base rate (%.3f): with %d no-burn tests the model cannot predict an extinction it has not seen. Run 1 contradicted a test; fixed in version %s." % (
             loo["brier_loo"], base_brier, fit["not_sustained"], bcfg["version"])],
        ["5", "Next tests ranked by uncertainty reduction", "Done",
         "Plan of %d tests chosen one at a time; first: %s, %g%% O2 at %g psia (%.0f%%); after 4 tests %.0f%%; after %d tests %.0f%%" % (
             len(plan), {"micro": "microgravity", "lunar": "Moon gravity", "mars": "Mars gravity", "earth": "1 g"}[plan[0]["g_class"]], plan[0]["o2_pct"], plan[0]["p_psia"],
             plan[0]["cumulative_reduction_pct"], plan[3]["cumulative_reduction_pct"], len(plan), plan[-1]["cumulative_reduction_pct"]),
         "Reductions are model-based; rig oxygen and pressure limits for drop towers and parabolic flights are assumptions."],
        ["6", "Falsifiable FM2 predictions", "Done",
         "Frozen %s; SHA-256 of fm2_predictions.json %s. Burn 1 %s, burn 2 %s (P %.2f, 90%% %.2f to %.2f), burn 3 %s, burn 4 %s" % (
             pred["frozen_at_utc"], shas.get("fm2_predictions.json", "?"), p1[1]["model"]["decision"], p1[2]["model"]["decision"], p1[2]["model"]["p_mean"], p1[2]["model"]["p_lo90"], p1[2]["model"]["p_hi90"],
             p1[3]["model"]["decision"], p1[4]["model"]["decision"]),
         "Declined burns are still scored by their published probabilities (Brier score). Post the hash on the project page."],
    ]
    md = ["# Checklist: the six-step method", "", "Generated %s from results/method and predictions. Status words follow the evidence, not the plan." % report.now_iso(), "",
          report.md_table(["#", "Requirement", "Status", "Evidence", "Remaining gap"], rows), "",
          "## 30-hour scope check", "",
          "- One material family: thin fabrics and papers, with SIBAL as the reference material (FM2 burns SIBAL). PMMA is fitted with the same code only for FM2 burns 3 and 4.",
          "- Three variables: oxygen, pressure and gravity. Flame direction and a per-material offset are added because FM2 and the FM2 team's tests depend on direction.",
          "- Coverage map, boundary model with its decline region, and a test plan longer than five: present (see results/method).",
          "- Data rules: NTRS reports used; MAPTIS not used (NESC TB 26-05 cites MAPTIS reports, and only the public bulletin text is used); PSI: %s." % s1["psi_tables"], ""]
    report.write_text(os.path.join(ROOT, "CHECKLIST.md"), "\n".join(md))
    report.dashboard("method_checklist.json", {"generated_at": report.now_iso(), "steps": [dict(zip(["step", "requirement", "status", "evidence", "gap"], r)) for r in rows],
                                               "fm2_sha256": shas.get("fm2_predictions.json"), "fm2_frozen_at_utc": pred["frozen_at_utc"]})
    res = ["# Six-step method results", "", "Generated %s." % report.now_iso(), "",
           "## Step 1: test-point ledger", "", "%d test points (%s). %d have an outcome. Rows added in this version: %s (NESC TB 26-05). Outcome evidence: %d quotes checked, %d not found. Data checks on the extended ledger: %s." % (
               s1["test_points"], ", ".join("%s %d" % kv for kv in s1["by_origin"].items()), s1["with_outcome"], ", ".join(s1["rows_added_v3"]), s1["outcome_quotes_checked"], len(s1["outcome_quotes_not_found"]), s1["checks_gate"]), "",
           "File: step1_test_point_ledger.csv (one row per test with material, oxygen, pressure, gravity, flow, outcome, quotes, sources, locators and URLs).", "",
           "## Step 2: operating envelope", "", report.md_table(["Point", "Oxygen", "Pressure", "Gravity", "Weight", "Source"],
               [[o["name"], "%g%%" % o["o2_pct"], "%g psia" % o["p_psia"], "%g g" % o["g"], o["weight"], o["source"]] for o in s2["operating_points"]]), "",
           "## Step 3: binned coverage", "", "Bins: oxygen %s %%; pressure %s psia. Rules: %s %s %s" % (s2["bins"]["o2_edges"], s2["bins"]["p_psia_edges"], s2["rules"]["tested"], s2["rules"]["nearby"], s2["rules"]["none"]), "",
           report.md_table(["Family", "Gravity", "Tested", "Nearby", "None"], [[f, g, v["tested"], v["nearby"], v["none"]] for f, fam in s3["families"].items() for g, v in fam["summary_by_gravity"].items()]), "",
           report.md_table(["Operating point (thin fabrics)", "Bin status", "Nearest tests, any gravity"],
               [[o["name"], o["status"], "; ".join("%s (%s, %g%%, %g psia, distance %.1f)" % (n["label"], n["g_class"], n["o2_pct"], n["p_psia"], n["distance_ignoring_gravity"]) for n in o["nearest_any_gravity"][:2])] for o in thin["operating_points"]]), "",
           "## Step 4: flammability boundary", "", s4["model"], "", s4["decline_rule"], "",
           "Fit: %d observations, %d did not burn, %d materials; max R-hat %.3f. Leave-one-out Brier %.3f (base rate %.3f); leave-one-out accuracy %.2f. Missed when left out: %s." % (
               fit["observations"], fit["not_sustained"], len(fit["materials"]), fit["max_rhat"], loo["brier_loo"], base_brier, loo["accuracy_loo"],
               ", ".join("%s (%s)" % (r["obs_id"], "burned" if r["y"] else "did not burn") for r in loo["rows"] if not r["correct_loo"])), "",
           report.md_table(["Operating point", "Direction", "P(sustains)", "90% interval", "Answer", "Reason"],
               [[o["name"], o["direction"], "%.2f" % o["p_mean"], "%.2f to %.2f" % (o["p_lo90"], o["p_hi90"]), o["decision"], "; ".join(o["reasons"])] for o in ops]), "",
           "Changes after run 1: " + " ".join(bcfg.get("changes_from_1_0", [])), "",
           "## Step 5: next tests", "", report.md_table(["Step", "Facility", "Gravity", "Oxygen", "Pressure", "Direction", "P(sustains) now", "Cumulative reduction"],
               [[c["step"], c["facility_name"], c["g_class"], "%g%%" % c["o2_pct"], "%g psia" % c["p_psia"], {1: "upward", -1: "downward"}[c["dir"]], "%.2f" % c["p_sustain_now"], "%.1f%%" % c["cumulative_reduction_pct"]] for c in plan]), "",
           "## Step 6: FM2 predictions", "", "Frozen %s. SHA-256: %s." % (pred["frozen_at_utc"], shas.get("fm2_predictions.json")), "",
           report.md_table(["Burn", "Fuel", "Direction", "Atmosphere", "P(sustains)", "90% interval", "Answer"],
               [[p["burn"], p["fuel"], p["direction"], "%g%% O2, %g psia" % (p["o2_pct"], p["p_psia"]), "%.2f" % p["model"]["p_mean"], "%.2f to %.2f" % (p["model"]["p_lo90"], p["model"]["p_hi90"]), p["model"]["decision"]] for p in pred["predictions"]]), "",
           "Rerun: `python experiments/method_six_steps.py --no-predictions` (keeps the frozen predictions), then `python experiments/method_report.py`.", ""]
    report.write_text(os.path.join(M, "results.md"), "\n".join(res))
    print("\n".join(" | ".join(str(c) for c in r) for r in rows))


if __name__ == "__main__":
    main()

"""Experiment 2: range and unit checks, run like a regression suite.

Usage: python experiments/exp2_checks.py [--sources DIR] [--no-gate]
Exit code 1 when a check fails (deployment gate) unless --no-gate is given.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import checks, ingest, report  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default=os.environ.get("NEXTBURN_SOURCES", ""), help="folder with source text files (optional)")
    ap.add_argument("--no-gate", action="store_true")
    a = ap.parse_args(argv)
    out = report.exp_dir(2)
    golden = json.load(open(os.path.join(ROOT, "config", "golden_rows.json")))
    raw = ingest.load_ledger()
    res, norm, pts = checks.run_all(raw, golden)
    fi = checks.fault_injection(raw, golden)
    src = checks.golden_in_sources(golden, a.sources) if a.sources else {"status": "SKIPPED", "reason": "no source folder given"}
    hist1 = os.path.join(out, "run1_first_version.json")
    hist2 = os.path.join(out, "run2_fault_injection_v1_1.json")
    run1 = json.load(open(hist1)) if os.path.exists(hist1) else None
    run2 = json.load(open(hist2)) if os.path.exists(hist2) else None
    gate = [r for r in res if r["status"] == "FAIL"]
    detected = sum(f["detected"] for f in fi)
    result = {
        "experiment": 2, "title": "Range and unit checks", "generated_at": report.now_iso(),
        "checks_version": checks.CHECKS_VERSION, "ledger": "ledger_v2.json", "ledger_sha256": report.sha256_file(ingest.DEFAULT_LEDGER),
        "rows": len(raw), "test_points": len(pts),
        "checks": [{k: r.get(k) for k in ("name", "what", "status", "n_checked", "failures")} | ({"accel_m_s2": r["accel_m_s2"], "g_ratio": r["g_ratio"], "deviation": r["deviation"]} if r["name"] == "luci_g_from_spin" else {}) | ({"dropped": r["dropped"]} if r["name"] == "dedupe_log" else {}) for r in res],
        "gate": "PASS" if not gate else "FAIL",
        "fault_injection": {"detected": detected, "total": len(fi), "faults": fi},
        "reference_values_in_source_text": src,
        "history": {
            "run1": {"checks_version": "1.0", "failed_checks": [c["name"] for c in run1["checks"] if c["status"] == "FAIL"] if run1 else None,
                     "findings": sum(len(c["failures"] or []) for c in run1["checks"]) if run1 else None,
                     "classification": "1 real duplicate in the ledger (R010 repeats R007 in other units); 2 false alarms on distinct Saffire tests with identical conditions; 3 rule false alarms (R083, R086, R093); 1 constant error (air oxygen 21.0% instead of 20.946%) that flagged the plan's correct 3.08 psia"},
            "run2": {"checks_version": "1.1", "fault_injection": "%s of %s detected" % (run2["detected"], run2["total"]) if run2 else None,
                     "finding": "F10 missed: the 1.1 rule needed the measurand to be named a spread rate, and the F10 mutation also overwrote the row's extinction wording"},
            "changes": checks.CHANGES_FROM_1_0,
        },
        "pass": not gate and detected == len(fi),
        "pass_rule": "Every check passes on the ledger, and every injected fault is detected",
    }
    report.write_json(os.path.join(out, "results.json"), result)
    report.dashboard("exp2_checks.json", {"title": result["title"], "gate": result["gate"], "checks_version": result["checks_version"],
                                          "checks": [{"name": c["name"], "status": c["status"], "n_checked": c["n_checked"], "failures": len(c["failures"] or [])} for c in result["checks"]],
                                          "fault_injection": {"detected": detected, "total": len(fi)}, "merged_rows": [d["row_id"] for r in res if r["name"] == "dedupe_log" for d in r["dropped"]],
                                          "generated_at": result["generated_at"]})
    # chart
    plt = report.plt()
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.2, 1]})
    shown = [r for r in res if r["name"] != "dedupe_log"]
    ax[0].barh([r["name"] for r in shown], [r["n_checked"] for r in shown], color=[report.COLORS["pass" if r["status"] == "PASS" else "fail"] for r in shown])
    for i, r in enumerate(shown):
        ax[0].text(r["n_checked"], i, "  %s (%d)" % (r["status"], r["n_checked"]), va="center", fontsize=8)
    ax[0].set_xlabel("values checked"); ax[0].set_title("Checks on ledger v2 (%d rows)" % len(raw)); ax[0].invert_yaxis()
    ax[0].set_xlim(0, max(r["n_checked"] for r in shown) * 1.35)
    ax[1].bar(["detected", "missed"], [detected, len(fi) - detected], color=[report.COLORS["pass"], report.COLORS["fail"]])
    ax[1].set_title("Injected faults: %d of %d caught" % (detected, len(fi))); ax[1].set_ylim(0, len(fi) + 1)
    fig.suptitle("Experiment 2: bad data cannot reach the screen", fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(out, "chart.png")); plt.close(fig)
    # markdown
    rows = [[r["name"], r["status"], r["n_checked"], len(r["failures"] or [])] for r in shown]
    frows = [[f["fault"], f["description"], f["expected_check"], "yes" if f["detected"] else "NO"] for f in fi]
    md = ["# Experiment 2: Range and unit checks", "",
          "Generated %s. Checks version %s on ledger v2 (%d rows, %d test points). Gate: **%s**." % (result["generated_at"], result["checks_version"], len(raw), len(pts), result["gate"]), "",
          report.md_table(["Check", "Status", "Values checked", "Failures"], rows), "",
          "Merged before checking (documented duplicate rule): %s." % (", ".join("%s into %s" % (d["row_id"], d["merged_into"]) for r in res if r["name"] == "dedupe_log" for d in r["dropped"]) or "none"), "",
          "LUCI spin check: 11 rpm at 1.22 m gives %.4f m/s2 (%.4f g), %.2f%% from the NASA fact-sheet lunar value of 1.62 m/s2." % (
              [r for r in res if r["name"] == "luci_g_from_spin"][0]["accel_m_s2"], [r for r in res if r["name"] == "luci_g_from_spin"][0]["g_ratio"], 100 * [r for r in res if r["name"] == "luci_g_from_spin"][0]["deviation"]), "",
          "## Fault injection", "", "Each fault is planted in a copy of the ledger; the named check must fail.", "",
          report.md_table(["Fault", "What was planted", "Check that must catch it", "Caught"], frows), "",
          "## How the checks were debugged", "",
          "- Run 1 (version 1.0): %s." % result["history"]["run1"]["classification"],
          "- Run 2 (version 1.1): %s; %s." % (result["history"]["run2"]["fault_injection"], result["history"]["run2"]["finding"]),
          "- Changes:"] + ["  - " + c for c in checks.CHANGES_FROM_1_0] + ["",
          "Reference values in the Saffire VI presentation text: %s." % src["status"], "",
          "## Rerun", "", "`python experiments/exp2_checks.py --sources <folder of source .txt files>` or `python tests/run_tests.py`. Exit code 1 blocks deployment.", ""]
    report.write_text(os.path.join(out, "results.md"), "\n".join(md))
    print("Experiment 2: gate %s, faults %d/%d, results in %s" % (result["gate"], detected, len(fi), out))
    return 0 if (a.no_gate or not gate) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Rebuild data, run the regression checks and Experiments 2 to 7, then refresh the dashboard files.

Usage:
  python run_all.py                  full run (Experiment 6 simulation takes the longest)
  python run_all.py --skip-sim       reuse the last Experiment 6 results
  python run_all.py --quick-sim      a fast Experiment 6 smoke run (does not overwrite the full results)
  python run_all.py --llm-answers results/exp7/llm_answers.json   also score a language model's answers
  python run_all.py --refreeze-predictions   also re-freeze the FM2 predictions (otherwise they stay frozen)
  python run_all.py --sources DIR    also confirm reference values in the source text files
Exit code 1 when the Experiment 2 gate or the regression tests fail.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def run(cmd, log):
    t0 = time.time()
    p = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    log.append({"step": " ".join(cmd), "exit": p.returncode, "seconds": round(time.time() - t0, 1), "tail": (p.stdout + p.stderr)[-600:]})
    print("%-60s exit %d  %.1f s" % (" ".join(cmd)[:60], p.returncode, time.time() - t0))
    return p.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--quick-sim", action="store_true")
    ap.add_argument("--llm-answers")
    ap.add_argument("--sources", default="")
    ap.add_argument("--refreeze-predictions", action="store_true", help="re-freeze the FM2 predictions (new timestamp and hash)")
    a = ap.parse_args()
    from nextburn import dashboard, ingest, report
    log = []
    ingest.build()
    gate = run(["tests/run_tests.py"], log)
    gate |= run(["experiments/exp2_checks.py"] + (["--sources", a.sources] if a.sources else []), log)
    run(["experiments/exp3_coverage.py"], log)
    run(["experiments/exp4_luci_rules.py"], log)
    run(["experiments/exp5_retrodiction.py"], log)
    if os.path.exists(os.path.join(ROOT, "experiments", "exp6_planner_sim.py")) and not a.skip_sim:
        run(["experiments/exp6_planner_sim.py"] + (["--quick"] if a.quick_sim else []), log)
    if os.path.exists(os.path.join(ROOT, "experiments", "exp7_si_test_set.py")):
        run(["experiments/exp7_si_test_set.py"], log)
        run(["experiments/exp7_heldout_check.py"], log)
        if a.llm_answers:
            run(["experiments/exp7_si_test_set.py", "--score-llm", a.llm_answers], log)
        held_llm = os.path.join(ROOT, "results", "exp7", "heldout_llm_answers.json")
        if os.path.exists(held_llm):
            run(["experiments/exp7_heldout_check.py", "--score-llm", held_llm], log)
    run(["experiments/method_six_steps.py"] + ([] if a.refreeze_predictions else ["--no-predictions"]) + (["--sources", a.sources] if a.sources else []), log)
    run(["experiments/method_report.py"], log)
    s = dashboard.build()
    report.dashboard("run_log.json", {"generated_at": report.now_iso(), "steps": log, "gate": "FAIL" if gate else "PASS"})
    run(["console/build_console.py"], [])
    print("\nGate: %s. Summary: dashboard_data/summary.json, RESULTS_SUMMARY.md and the console page index.html" % ("FAIL" if gate else "PASS"))
    for e in s["experiments"]:
        print("  Exp %d %-36s %s" % (e["id"], e["title"][:36], e["status"]))
    return 1 if gate else 0


if __name__ == "__main__":
    sys.exit(main())

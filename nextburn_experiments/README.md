# NextBurn experiments 2 to 7

NextBurn turns NASA microgravity combustion results into a fire-safety coverage map and a test plan for Moon and Mars habitats (NASA Space Apps 2026, Flame in Freefall). This folder holds the code, settings, data and results for Experiments 2 to 7. Experiment 1 (ledger accuracy audit) lives in the sibling folders `experiment1` and `audit_tool`.

Results, in one table, are in `RESULTS_SUMMARY.md`. The dashboard reads the files in `dashboard_data/`.

## Quick start

Python 3.9 or later with numpy, pandas, scipy, scikit-learn and matplotlib. Nothing else is needed (pytest is optional).

```
python run_all.py --skip-sim     # rebuild data, run checks and Experiments 2-5 and 7, refresh dashboard files (about a minute)
python run_all.py                # the same, plus the full Experiment 6 simulation (the slow step)
python tests/run_tests.py        # the regression gate on its own; exit code 1 blocks deployment
```

Each experiment also runs on its own, for example `python experiments/exp3_coverage.py`.

## Folder layout

| Folder or file | Contents |
|---|---|
| `config/` | Settings: habitat presets, facility catalogue, gravity rules, planner weights, reference rows, constants with their sources, source publication years, and the SI question bank |
| `data/` | `ledger_v2.json` (98 evidence rows after the Experiment 1 fixes), the normalized rows and the 40 test points built from it, Experiment 1 scores, stored SI answers |
| `nextburn/` | Modules: `ingest` (text to numbers), `units`, `checks`, `coverage`, `physics`, `planner`, `sim`, `si`, `report`, `dashboard` |
| `experiments/` | One script per experiment; each writes `results/expN/results.json`, `results.md` and one `chart.png` |
| `tests/` | Experiment 2 regression tests (`test_checks.py`) and a runner that needs no pytest |
| `results/` | Outputs of every experiment, including the first-run records of Experiment 2 |
| `dashboard_data/` | Compact JSON files for the dashboard (listed below) |
| `run_all.py` | One command that rebuilds everything |

## The experiments

| # | Experiment | What it shows | Pass rule | Script |
|---|---|---|---|---|
| 2 | Range and unit checks | Bad data cannot reach the screen | Every check passes and every planted fault is caught | `exp2_checks.py` |
| 3 | Coverage sensitivity | The gap finding does not depend on tolerances | Moon-base headline holds in all six tolerance runs and two cross-checks | `exp3_coverage.py` |
| 4 | LUCI holdout and rule comparison | The method was checked against real lunar data | Hits and misses reported as they fall; band of exponents published | `exp4_luci_rules.py` |
| 5 | Planner retrodiction | On pre-2025 evidence the planner picks a LUCI-type test | A lunar-gravity solid-fuel test in the top five with frozen weights | `exp5_retrodiction.py` |
| 6 | Planner efficiency (SIMULATION) | Uncertainty-driven test choice needs fewer burns than a fixed matrix | Fewer tests at the median with equal or better success | `exp6_planner_sim.py` |
| 7 | SI test set | The SI cites the ledger or declines, and never invents a number | No ungrounded number, every unanswerable declined, every override refused | `exp7_si_test_set.py` |

Notes that matter when you present the results:

- Experiment 2 keeps a record of its own debugging: the first run flagged 7 items (1 real duplicate row, 6 checker false alarms), and fault injection found a blind spot that was then fixed. See `results/exp2/results.md`.
- Experiment 3 also reruns coverage with gravity ignored. That shows the Moon-base gap is a gravity gap: orbit tests exist at nearly the same atmosphere.
- Experiment 5 reports a random-pick baseline, because the basic pass rule is easy to meet. Quote the strict check (a lunar spread-rate test of thin fabric or PMMA) next to its baseline.
- Experiment 6 is a simulation on synthetic boundaries anchored to published SoFIE-GEL ranges. Label it as a simulation everywhere. Its fixed-matrix result depends on the matrix layout (`runs_fixed_matrix_sensitivity.csv`); quote the qualified claim in `results/exp6/results.json`.
- Experiment 7 has three layers: the frozen 35-question bank, an independent 10-question held-out set (`config/si_heldout_questions.json`, run by `experiments/exp7_heldout_check.py`) and a language-model run under the guard prompt (`results/exp7/llm_results.json`, `heldout_llm_results.json`). The held-out file records which two items were used to fix the SI and so no longer count as held out.

## Dashboard data files

| File | Use on the dashboard |
|---|---|
| `summary.json` | One card per experiment (status, headline, chart path), ledger facts and figures that changed from the plan |
| `exp2_checks.json` | Verification screen: check status, counts, fault-injection score, merged rows |
| `exp3_coverage.json` | Mission coverage screen: 30 cells (habitat x material x direction) with status per tolerance run, matches, FM2 planned flags, nearest evidence |
| `exp4_luci.json` | LUCI check panel: measured ratios, rule errors, implied exponents, uncertainty band, buoyancy index |
| `exp5_plan.json` | Test planner screen: top five tests (before 2025 and today) with facility, measurement, score and a plain-language rationale; sensitivity; gaps no facility can close; burn distances |
| `exp6_sim.json` | Planner-efficiency panel (simulation) |
| `exp7_si.json` | SI scorecard; `data/si_stored_answers.json` holds the 20 stored demo answers with citations |
| `run_log.json` | Last full run: steps, exit codes, timings |

Every number in these files comes from a script; headline strings are composed from the numbers, not typed by hand.

## Adding data (for example PSI tables)

Drop CSV files into `data/extra_tests/` with these columns, then run `python run_all.py --skip-sim`:

`tp_id, label, family, direction_class, g, p_kpa, o2_pct, flow_cm_s, evidence_tier, first_year, source_id, row_id`

Use `thin_fabric`, `thick_plastic` or `other_textile` for family, and `with_flow` or `against_flow` for direction. Leave a value empty when the source does not state it: an empty value never matches a habitat, which keeps "untested" conservative. Optional range columns are `p_lo_kpa`, `p_hi_kpa`, `o2_lo_pct`, `o2_hi_pct`, `flow_lo_cm_s` and `flow_hi_cm_s`.

## Testing a language model as the SI

1. `python experiments/exp7_si_test_set.py --export-llm-prompts` writes `results/exp7/llm_prompts.jsonl` (question plus retrieved rows) and `llm_guard_prompt.md` (the system prompt).
2. Send each prompt to the model. Save a JSON list of `{"id", "answer", "cited_rows"}`.
3. `python experiments/exp7_si_test_set.py --score-llm <file>` scores it with the same checks as the guarded answerer.
4. For the held-out set: `python experiments/exp7_heldout_check.py --export-llm-prompts`, then `--score-llm <file>`.

The language-model results stored here were written by an AI assistant acting as the SI under the guard prompt. Rerun steps 1 to 4 with the model the app actually uses before quoting them. Consider adding "estimate" next to "guess" in rule 5 of the guard prompt (`nextburn/si.py`, GUARD_PROMPT), then re-export the prompts.

## Settings, freezing and honesty notes

- `config/rules.json` (gravity rules) and `config/weights.json` (planner weights) carry a freeze time. Each results file records their SHA-256. The team had already seen LUCI when they were frozen, so Experiments 4 and 5 are checks, not blind predictions; both say so in their results.
- Facility atmosphere ranges marked "assumed" in `config/facilities.json` are NextBurn assumptions, not facility specifications.
- Constants carry their sources in `config/constants.json` (NASA fact sheets for lunar and Mars gravity, IUPAC for the oxygen fraction of air).
- The ledger rows were extracted with AI help and checked by AI checkers in Experiment 1; a team member should re-check the 19 disputed fields before the data is called human-verified.
- Source PDFs and their text are not redistributed. Links are in `data/sources.csv`. Pass `--sources <folder>` to Experiment 2 to confirm reference values in your own text copies.

## AI use

AI assistance (Microsoft Copilot) was used to write these scripts, to extract and check ledger rows, and to draft the SI question bank. The guarded SI in Experiment 7 is deterministic code; any language-model run is scored separately and labelled as such.

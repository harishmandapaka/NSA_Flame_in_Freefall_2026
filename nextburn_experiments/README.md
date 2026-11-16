# NextBurn experiments 2 to 7

NextBurn turns NASA microgravity combustion results into a fire-safety coverage map and a test plan for Moon and Mars habitats (NASA Space Apps 2026, Flame in Freefall). This repository holds the code, settings, data and results for Experiments 1 to 7 and the six-step method. Experiment 1 (the ledger accuracy audit) is in `experiment1/` (results, scores and scripts) and `audit_tool/` (the repeatable audit script and its hash-chained records). The full source texts the audit read are not redistributed here; every ledger row names its source and location instead.

Results, in one table, are in `RESULTS_SUMMARY.md`. The dashboard reads the files in `dashboard_data/`.

## NextBurn Coverage Console: start here

`index.html` is the project's front page. It holds a snapshot of every result, chart and setting, so it needs no server and no install.

- **Online:** publish this repository with GitHub Pages (Settings, Pages, Deploy from a branch, `main`, `/ (root)`). The empty `.nojekyll` file makes GitHub serve the files exactly as they are.
- **Offline:** open `index.html` in any modern browser.

| Tab | What it shows |
|---|---|
| Overview | Headline numbers, the six-step checklist with known gaps, Experiments 1 to 7, figures that changed when the scripts recomputed them |
| Coverage | Oxygen by pressure bins for each gravity level: tested, only nearby tests, or none; select a bin to see its tests |
| Boundary model | Probability that the reference fabric keeps burning, with sliders that show how strict the decline rule is; fit quality, including where the model is weak |
| Next tests | The ranked test sequence and how much uncertainty each test removes |
| FM2 predictions | The four frozen predictions, their hash, and a button that hashes the published file in the browser (works when the page is served from a website) |
| Evidence ledger | All 313 test points with search, filters, source links and CSV download |
| Experiments | Experiments 1 to 7 with their charts and details |
| Settings | The 115 editable settings, each with a range check |
| Runs | The actions the live console can run, and the last full run |

**Proposing a change from the snapshot.** In Settings, edit values, then download the updated file or open a GitHub issue with a change request. A maintainer applies a request with `python console/apply_settings.py change.json`; it checks every value, keeps a backup of the old file, logs the change, and names the scripts to rerun.

**Changing and rerunning from the page.** Run the live console on your computer: `pip install -r requirements.txt`, then `python console/console_server.py`, and open http://127.0.0.1:8770. It listens on this computer only, runs only the actions listed in `console/settings_schema.json` (one at a time), and rebuilds `index.html` after each run. `python console/build_console.py` rebuilds the snapshot at any time; `run_all.py` does it at the end of every run.

| Console file | Purpose |
|---|---|
| `console/settings_schema.json` | The editable settings (file, path, range) and the allowed run actions |
| `console/console_template.html` | The page; `build_console.py` embeds the results into it to make `index.html` |
| `console/console_lib.py` | Shared code: data bundle, setting paths, validation, backups and change log |
| `console/console_server.py` | Optional local server for live mode (standard library only) |
| `console/apply_settings.py` | Applies a change request from the snapshot or a GitHub issue |
| `console/test_render.js`, `console/selftest_server.py` | Checks of the page sections and of the live server (`node console/test_render.js`, `python console/selftest_server.py --with-jobs`) |

**Frozen FM2 predictions.** `predictions/fm2_predictions.json` was frozen on 2026-11-16 at 00:10:42 UTC, before any FM2 result exists. SHA-256: `05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248`. Do not edit the files listed in its `inputs_sha256` until the FM2 results are out; the console shows any change to them.

**NASA data used.** NASA Physical Sciences Informatics experiment tables for PSI-25, PSI-26, PSI-98, PSI-99 and PSI-100 (downloaded and parsed; provenance in `data/psi_raw/`); NASA Technical Reports Server reports, cited row by row in the ledger; NESC Technical Bulletin 26-05 for the 37% oxygen condition. MAPTIS is restricted and is not used.

**Use of AI.** AI tools (Microsoft Copilot) helped with research, code and writing, and AI checkers were used in the Experiment 1 audit; a human re-check of 19 disputed fields is pending. Every number in this repository is computed by its scripts from the cited sources.

NextBurn is an independent NASA Space Apps Challenge 2026 entry. It is not produced, reviewed or endorsed by NASA and uses no NASA logos.

## Quick start

Python 3.9 or later with numpy, scipy and matplotlib (`pip install -r requirements.txt`). Nothing else is needed (pytest is optional).

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
| `dashboard_data/` | Compact JSON files for the dashboard (listed below), including `method_steps.json`, `method_boundary_grid.json` and `method_checklist.json` |
| `run_all.py` | One command that rebuilds everything |
| `index.html`, `console/` | The NextBurn Coverage Console (see the start of this file) |
| `experiment1/`, `audit_tool/` | Experiment 1: audit sample, checker verdicts, adjudication, fixes and score; the repeatable audit script with its records |
| `predictions/` | The frozen FM2 predictions and their SHA-256 |
| `requirements.txt` | Python packages |

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

## Six-step method (Steps 1 to 6)

`python experiments/method_six_steps.py` runs the method end to end; `CHECKLIST.md` states, from the results files, what each step delivers and what is still missing.

| Step | What it does | Output |
|---|---|---|
| 1 Test-point ledger | One row per test with material, oxygen, pressure, gravity, flow and outcome; each outcome cites ledger rows or a source quote, checked by code | `results/method/step1_test_point_ledger.csv` |
| 2 Envelope | ISS cabin air; 34% oxygen at 8.2 psia; 37% oxygen at 8.2 psia (NESC TB 26-05); Moon 0.16 g and Mars 0.38 g | `config/envelope.json` |
| 3 Coverage | Oxygen x pressure bins per gravity level: tested, nearby only, or none | `results/method/coverage_*.png`, `step3_coverage_bins.csv` |
| 4 Boundary model | Bayesian logistic model of P(sustained flame); declines far from tests, when too uncertain, or when it would contradict a nearby test | `results/method/boundary_thin_fabric_SIBAL.png`, `step4_boundary.json` |
| 5 Next tests | Ten tests chosen one at a time by expected uncertainty reduction at the weighted operating points | `results/method/next_tests.png`, `step5_test_plan.csv` |
| 6 FM2 predictions | Probabilities and answers for the four FM2 burns, frozen with SHA-256 before FM2 flies | `predictions/fm2_predictions.json`, `predictions/SHA256SUMS.txt` |

Model settings are frozen in `config/boundary_model.json` (version 1.1; the changes made after run 1 are listed inside it, and run 1 outputs are kept in `results/method/history`). `run_all.py` reruns the method without re-freezing the predictions; use `--refreeze-predictions` only on purpose, and post the new hash. Do not edit the files whose hashes are recorded in `predictions/fm2_predictions.json`.

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

## PSI tables

`data/psi/psi_tests.csv` holds 263 test rows read from the experiment tables of PSI-25 (BASS-II), PSI-26 (BASS), PSI-98, PSI-99 and PSI-100 (Saffire I to III) on psi.nasa.gov (CC0). Raw copies, provenance files and an access report are in `data/psi_raw/`. The rows enter the Step 1 test-point ledger and the Step 3 coverage report (listed as not placed, because no PSI table states pressure). They do not enter the boundary model, for the same reason. One PSI-25 column (final CO) was not read and one PSI-25 row (B2) is partly unresolved; see `data/psi_raw/ACCESS_REPORT.md`.

## Adding data (for example more PSI tables)

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

# NextBurn: from evidence gap to test plan

Fire-safety test coverage for Moon and Mars habitats. NextBurn is a NASA Space Apps Challenge 2026 entry for the **Flame in Freefall** challenge.

NextBurn treats spacecraft fire-safety testing the way chip designers treat verification:

1. List every flame test it can trace to a public NASA source.
2. Measure how well those tests cover the air and gravity of future Moon and Mars habitats.
3. Fit a model that declines to answer far from the data.
4. Rank the next tests by how much uncertainty each one would remove.

It also publishes predictions for NASA's FM2 lunar burns before their results exist, so the method can be proven wrong.

- **See the results with no install:** open `index.html` (the NextBurn Coverage Console) in a browser, or visit this repository's GitHub Pages site.
- **Rerun everything and try your own changes:** clone the repository and run one setup command. See [Quick start](#quick-start).

## Contents

- [Results at a glance](#results-at-a-glance)
- [Quick start](#quick-start)
- [Make a change and see what it does](#make-a-change-and-see-what-it-does)
- [The Coverage Console](#the-coverage-console)
- [Running parts by hand](#running-parts-by-hand)
- [How it works: the six-step method](#how-it-works-the-six-step-method)
- [Experiments 1 to 7](#experiments-1-to-7)
- [Data sources](#data-sources)
- [Frozen FM2 predictions](#frozen-fm2-predictions)
- [Repository layout](#repository-layout)
- [Honesty notes and limits](#honesty-notes-and-limits)
- [Use of AI](#use-of-ai)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Results at a glance

These are the published results. Your own rerun updates `index.html`, `RESULTS_SUMMARY.md` and `CHECKLIST.md`.

| Question | Answer |
|---|---|
| What evidence exists? | 313 test points from 14 sources: 263 rows from NASA PSI tables, 40 from the evidence ledger, 2 from NESC Technical Bulletin 26-05 and 8 derived. 67 have a burn outcome. Every row names its source and location. 51 outcome quotes were checked against their sources and none was missing. |
| Where are the gaps? | For thin fabrics, each gravity level has 24 envelope bins (tested / only nearby / none): microgravity 3 / 11 / 10, Moon 1 / 3 / 20, Mars 0 / 0 / 24. Only ISS cabin air sits in a tested bin. |
| What can be predicted safely? | The boundary model answers only near tested conditions, for example ISS cabin air, where the probability of a sustained flame is 0.94 upward and 0.97 downward. It declines on 96% of the map. |
| How good is the model? | 23 observations: 20 burned and 3 did not. The sampling chains agree (largest R-hat 1.02). The leave-one-out Brier score is 0.153, worse than 0.113 for always predicting the base rate, because few tests did not burn. The test plan targets that weakness. |
| Which tests next? | Parabolic flights at 37% oxygen and 8.2 psia, in this order: Mars upward, Mars downward, Moon upward, Moon downward. The first test removes 45.3% of the weighted uncertainty, the first four 73.2% and ten tests 83.1%. |
| Can it be checked? | The FM2 predictions were frozen on 2026-11-16 at 00:10:42 UTC, before any FM2 result exists. Burn 1 is declined, burn 2 sustains (0.89, 90% interval 0.61 to 1.00), and burns 3 and 4 are declined. See [Frozen FM2 predictions](#frozen-fm2-predictions). |

| # | Experiment | Status | Result |
|---|---|---|---|
| 1 | Ledger accuracy | NOT SATISFACTORY | 632 of 650 sampled fields correct (97.2%, 95% interval 95.7% to 98.2%) against a 98% pass mark set in advance; strict count 631 of 650 (97.1%). AI checkers, then a completed human re-check of the 19 disputed fields. |
| 2 | Range and unit checks | PASS | 7 of 7 checks pass on 98 ledger rows; 12 of 12 planted faults caught; 1 duplicate row merged |
| 3 | Coverage sensitivity | PASS | Moon-base atmosphere has no direct lunar-gravity test in all 6 tolerance runs and both cross-checks; 2 of 30 cells tested and 1 bounded in every run |
| 4 | LUCI holdout and gravity-rule comparison | REPORTED | Square-root rule: +3.4% and +8.3% at the flame tips (hits), -33.8% at the fabric base (miss); implied exponents 0.52, 0.54, 0.27; lunar ratio band 0.17 to 0.61 (3.7-fold) |
| 5 | Planner retrodiction | PASS | On pre-2025 evidence the top five includes a lunar-gravity spread-rate test; it stays there in 78.1% of 1000 weight draws (random picks: 42.4%); a lunar test of any kind in 99.8% (random: 98.7%) |
| 6 | Planner efficiency (SIMULATION) | PASS (simulation) | In simulation (200 random two-variable boundaries), choosing each test by uncertainty found the minimum extinction oxygen within 0.5 points in a median of 11 tests (80th percentile 14) versus 24 (80th percentile 30) for a fixed 6x6 test matrix, with 100% vs 86% success |
| 7 | SI test set: cite the ledger or decline | PASS | Guarded SI: 35/35 answers, 240/240 numbers grounded; 10/10 unanswerable declined; 5/5 overrides refused; 0/20 answerable wrongly declined; independent held-out set, first run: 8 of 10 correct, 10 of 10 grounded; after the fix, 8 of 8 still-unseen items correct; language-model SI under the guard prompt: 35/35 answers, 134/134 numbers grounded |

## Quick start

You need **Python 3.9 or later** and **git**. The first run downloads numpy, scipy and matplotlib, so it needs an internet connection.

**macOS or Linux**

```
git clone https://github.com/<owner>/<repo>.git
cd <repo>
python3 setup_nextburn.py
```

**Windows (Command Prompt or PowerShell)**

```
git clone https://github.com/<owner>/<repo>.git
cd <repo>
.\setup.cmd
```

Replace `<owner>/<repo>` with this repository's address; the green **Code** button on GitHub shows it. `sh setup.sh` does the same as `python3 setup_nextburn.py`.

The setup does seven things, and is safe to run again at any time:

1. Checks the Python version.
2. Makes a private Python environment in `.venv`, so your other Python projects stay untouched.
3. Installs `requirements.txt` into it. This is skipped when the packages are already there.
4. Runs the regression tests.
5. Reruns Experiments 2 to 7 and the six-step method with `run_all.py`, then rebuilds `index.html`. The full Experiment 6 simulation is reused unless you add `--full`.
6. Checks that the frozen FM2 predictions still match their published SHA-256.
7. Prints a results summary and opens the dashboard.

| Option | What it does |
|---|---|
| `--serve` | Afterwards, starts the live console at http://127.0.0.1:8770, where you can change settings and rerun the scripts from the browser. Ctrl+C stops it. |
| `--pull` | First gets the latest version from GitHub (`git pull --ff-only`). |
| `--full` | Also reruns the full Experiment 6 simulation, the slow step. |
| `--no-run` | Installs and checks only, and rebuilds `index.html` from the current results. |
| `--no-venv` | Uses the Python that runs the script instead of `.venv`. |
| `--system-packages` | Lets `.venv` use numpy, scipy and matplotlib already installed on the computer. Useful offline. |
| `--no-open` | Does not open a browser. |
| `--port N` | Sets the port for `--serve` (default 8770). |

Rerunning rewrites the results files. Their `generated_at` times change even when the numbers do not, so `git status` lists them.

## Make a change and see what it does

**1. In the browser, with the live console.** Run `python3 setup_nextburn.py --serve` (Windows: `.\setup.cmd --serve`).

- Open the **Settings** tab and change a value. For example, set "Exploration atmosphere, Moon: oxygen (%)" from 34 to 30.
- Select **Save to the project**, then the **method** button that appears.
- When the run finishes, the page reloads. The Coverage, Boundary model and Next tests tabs then show the new results.

Every value is range-checked, and every save keeps a backup of the old file. **Runs, Restore** puts a file back as it was.

**2. By editing a settings file.** Change a value in one of the files below. Then run `python3 setup_nextburn.py` again and reload `index.html`.

- `git diff --stat` shows which results changed.
- `git checkout -- .` puts the published versions back.

| File | What it controls | What it reruns |
|---|---|---|
| `config/envelope.json` | Operating points: oxygen, pressure, gravity and the weight each carries in the test plan | Six-step method |
| `config/boundary_model.json` | Model priors, sampler settings and the decline rule (support radius, widest interval, conflict radius) | Six-step method |
| `config/coverage.json` | Experiment 3 tolerances | Experiment 3 |
| `config/weights.json` | Planner weights. They are frozen for the judged Experiment 5 result, so a change is a what-if. | Experiment 5 |
| `config/facilities.json` | Test facilities: availability, cost tier, test time and atmosphere limits | Experiment 5 and the six-step method |

`console/settings_schema.json` lists every editable setting with its allowed range: 115 settings in 6 groups.

**3. Without installing anything.** On the published console, open **Settings**, edit values, then either download the updated file or select **Propose on GitHub**. Proposing opens an issue with a change request. A maintainer applies it with `python console/apply_settings.py change.json`, which checks every value, keeps a backup, logs the change and names the scripts to rerun.

**Do not edit** the six files that fed the frozen FM2 predictions (listed in [Frozen FM2 predictions](#frozen-fm2-predictions)) until the FM2 results are out. `config/boundary_model.json` is one of them. A change there is allowed for what-if runs, but the console and the setup then report that a frozen input changed. The predictions file itself always stays frozen.

## The Coverage Console

`index.html` is the project's front page. It holds a snapshot of every result, chart and setting, so it needs no server. To publish it, open the repository's **Settings, Pages, Deploy from a branch**, then choose `main` and `/ (root)`. The empty `.nojekyll` file makes GitHub serve the files exactly as they are.

| Tab | What it shows |
|---|---|
| Overview | Headline numbers, the six-step checklist with known gaps, Experiments 1 to 7, and figures that changed when the scripts recomputed them |
| Coverage | Oxygen-by-pressure bins for each gravity level: tested, only nearby tests, or none. Select a bin to see its tests. |
| Boundary model | The probability that the reference fabric keeps burning, with sliders that show how strict the decline rule is, and fit quality, including where the model is weak |
| Next tests | The ranked test sequence and how much uncertainty each test removes |
| FM2 predictions | The four frozen predictions, their hash, and a button that hashes the published file in the browser (on a website) |
| Evidence ledger | All 313 test points, with search, filters, source links and CSV download |
| Experiments | Experiments 1 to 7, with charts and details |
| Settings | The editable settings, each with a range check |
| Runs | In live mode, the actions you can run, recent changes with restore, and recent runs. In snapshot mode, the last full run. |
| About | Data, AI use, and the statement that the project is independent of NASA |

**Live mode.** `python console/console_server.py` serves the console at http://127.0.0.1:8770. `setup_nextburn.py --serve` starts it for you.

- The server listens on this computer only. It runs only the actions listed in `console/settings_schema.json`, one at a time.
- After each run, it rebuilds `index.html`.
- `python console/build_console.py` rebuilds the snapshot at any time, and `run_all.py` rebuilds it at the end of every run.

## Running parts by hand

```
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python tests/run_tests.py                 # regression gate; exit code 1 means a check failed
python run_all.py --skip-sim              # rerun everything except the slow simulation; rebuilds index.html
python run_all.py                         # the same, plus the full Experiment 6 simulation
python experiments/exp3_coverage.py       # one experiment on its own
python experiments/method_six_steps.py --no-predictions   # the six-step method; FM2 predictions stay frozen
python console/build_console.py           # rebuild index.html only
python console/console_server.py          # live console at http://127.0.0.1:8770
node console/test_render.js               # check every console tab against the embedded data (optional)
python console/selftest_server.py --with-jobs   # check the live server on a temporary copy (optional)
```

## How it works: the six-step method

`experiments/method_six_steps.py` runs the method end to end. `CHECKLIST.md` states, from the results files, what each step delivers and what is still missing.

| Step | What it does | Output |
|---|---|---|
| 1. Test-point ledger | One row per test with material, oxygen, pressure, gravity, flow and outcome. Each outcome cites ledger rows or a source quote, checked by code. | `results/method/step1_test_point_ledger.csv` |
| 2. Envelope | ISS cabin air; 34% oxygen at 8.2 psia; 37% oxygen at 8.2 psia (NESC TB 26-05); Moon 0.16 g and Mars 0.38 g | `config/envelope.json` |
| 3. Coverage | Oxygen-by-pressure bins per gravity level: tested, only nearby, or none. A test at another gravity level never counts. | `results/method/coverage_*.png`, `step3_coverage_bins.csv` |
| 4. Boundary model | Bayesian logistic model of the probability of a sustained flame. It declines far from tests, when too uncertain, or when it would contradict a nearby test. | `results/method/boundary_thin_fabric_SIBAL.png`, `step4_boundary.json` |
| 5. Next tests | Ten tests chosen one at a time by expected uncertainty reduction at the weighted operating points | `results/method/next_tests.png`, `step5_test_plan.csv` |
| 6. FM2 predictions | Probabilities and answers for the four FM2 burns, frozen with SHA-256 before FM2 flies | `predictions/fm2_predictions.json`, `predictions/SHA256SUMS.txt` |

The model settings are in `config/boundary_model.json` (version 1.1). The changes made after run 1 are listed inside it, and the run 1 outputs are kept in `results/method/history`.

## Experiments 1 to 7

| # | Experiment | What it shows | Pass rule | Where |
|---|---|---|---|---|
| 1 | Ledger accuracy | How accurate the extracted evidence is | 98% of sampled fields correct, set in advance | `experiment1/`, `audit_tool/` |
| 2 | Range and unit checks | Bad data cannot reach the screen | Every check passes and every planted fault is caught | `experiments/exp2_checks.py` |
| 3 | Coverage sensitivity | The gap finding does not depend on tolerances | The Moon-base headline holds in all six tolerance runs and two cross-checks | `experiments/exp3_coverage.py` |
| 4 | LUCI holdout and rule comparison | The method checked against real lunar data | Hits and misses reported as they fall; band of exponents published | `experiments/exp4_luci_rules.py` |
| 5 | Planner retrodiction | On pre-2025 evidence, the planner picks a LUCI-type test | A lunar-gravity solid-fuel test in the top five with frozen weights | `experiments/exp5_retrodiction.py` |
| 6 | Planner efficiency (SIMULATION) | Choosing tests by uncertainty needs fewer burns than a fixed matrix | Fewer tests at the median with equal or better success | `experiments/exp6_planner_sim.py` |
| 7 | SI test set | The assistant cites the ledger or declines, and never invents a number | No ungrounded number, every unanswerable question declined, every override refused | `experiments/exp7_si_test_set.py` |

Notes for reading the results:

- **Experiment 1:** the score stands below its pass mark and is reported as failed. The fixes produced ledger v2 (31 changes, listed in `experiment1/fixes.csv`). `audit_tool/nextburn_audit.py` reruns the audit and keeps hash-chained records.
- **Experiment 2:** keeps a record of its own debugging. The first run flagged 7 items (1 real duplicate row, 6 checker false alarms), and fault injection found a blind spot that was then fixed. See `results/exp2/results.md`.
- **Experiment 3:** also reruns coverage with gravity ignored. That shows the Moon-base gap is a gravity gap: orbit tests exist at nearly the same atmosphere.
- **Experiment 5:** reports a random-pick baseline, because the basic pass rule is easy to meet.
- **Experiment 6:** a simulation on synthetic boundaries anchored to published SoFIE-GEL ranges. It is labelled as a simulation everywhere, and its fixed-matrix result depends on the matrix layout (`results/exp6/runs_fixed_matrix_sensitivity.csv`).
- **Experiment 7:** has three layers: the frozen 35-question bank, an independent 10-question held-out set, and a language-model run under the guard prompt. The held-out file records which two items were used to fix the assistant and so no longer count as held out.

## Data sources

| Source | Used for |
|---|---|
| NASA Physical Sciences Informatics, https://psi.nasa.gov (CC0) | Experiment tables of PSI-25 (BASS-II), PSI-26 (BASS), PSI-98, PSI-99 and PSI-100 (Saffire I to III): 263 test rows. The tables have no documented API, so they were downloaded and parsed. Raw copies, provenance and an access report are in `data/psi_raw/`. |
| NASA Technical Reports Server, https://ntrs.nasa.gov | Reports cited row by row in the evidence ledger, with a locator for every value. The full list is in `data/sources.csv`. |
| NESC Technical Bulletin 26-05, https://www.nasa.gov/centers-and-facilities/nesc/tb-26-05-webbings-for-use-in-elevated-oxygen-environments/ | The 37% oxygen condition in the operating envelope |
| FM2 poster, NTRS 20240015307, https://ntrs.nasa.gov/citations/20240015307 | The four FM2 burn conditions |

MAPTIS is restricted and is not used. Source PDFs and their text are not redistributed; every row links to its source instead.

- **PSI rows:** no PSI table states pressure. The PSI rows therefore enter the Step 1 ledger and the Step 3 report as "not placed", and they do not enter the boundary model.
- **Adding data:** drop CSV files into `data/extra_tests/` with the columns `tp_id, label, family, direction_class, g, p_kpa, o2_pct, flow_cm_s, evidence_tier, first_year, source_id, row_id`, then rerun.
  - Family is `thin_fabric`, `thick_plastic` or `other_textile`; direction is `with_flow` or `against_flow`.
  - Leave a value empty when the source does not state it. An empty value never matches a habitat, which keeps "untested" conservative.

## Frozen FM2 predictions

`predictions/fm2_predictions.json` was frozen on 2026-11-16 at 00:10:42 UTC, before any FM2 result exists. Its SHA-256 is:

```
05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248
```

Check it yourself:

- macOS: `shasum -a 256 predictions/fm2_predictions.json`
- Linux: `sha256sum predictions/fm2_predictions.json`
- Windows: `certutil -hashfile predictions\fm2_predictions.json SHA256`

The setup script prints the same check, and on the published site the FM2 predictions tab can hash the file in your browser.

The predictions record the SHA-256 of the six files they were computed from:

- `nextburn/boundary.py`
- `nextburn/tpl.py`
- `config/boundary_model.json`
- `config/test_outcomes.json`
- `data/ledger_v2.json`
- `data/ledger_additions_v3.json`

`run_all.py` never re-freezes the predictions. `python run_all.py --refreeze-predictions` does so on purpose only, with a new time and hash that must then be posted. `.gitattributes` stops git from changing line endings, so the hashes match on every platform.

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | The NextBurn Coverage Console: a snapshot of every result |
| `setup_nextburn.py`, `setup.sh`, `setup.cmd` | One-step setup for any platform |
| `run_all.py` | Reruns everything and rebuilds `index.html` |
| `config/` | Settings: envelope, model, coverage tolerances, planner weights, facilities, gravity rules, constants with their sources, question banks |
| `data/` | Evidence ledger v2, PSI tables, test points, Experiment 1 scores and the source list |
| `nextburn/` | The Python package: ingest, units, checks, coverage, physics, planner, simulation, assistant (SI), test-point ledger, envelope, boundary model, recommendations, reports and dashboard summary |
| `experiments/` | One script per experiment, plus the six-step method |
| `results/` | Outputs of every experiment and of the method: charts, CSV, JSON and Markdown |
| `dashboard_data/` | Compact JSON files the console reads |
| `predictions/` | The frozen FM2 predictions and `SHA256SUMS.txt` |
| `console/` | Console template, builder, local server, settings schema, change-request tool and checks |
| `experiment1/`, `audit_tool/` | Experiment 1: sample, checker verdicts, adjudication, fixes and score; the repeatable audit script and its hash-chained records |
| `tests/` | Regression tests (no pytest needed) |
| `CHECKLIST.md`, `RESULTS_SUMMARY.md` | Status of each method step, and all results in one table |
| `CHANGELOG_2026-11-15.md`, `MANIFEST_SHA256.txt` | What changed, and the SHA-256 of every file |

## Honesty notes and limits

- **Sparse data and wide uncertainty.** Showing where uncertainty is large is the purpose of the tool, so the model declines rather than guesses.
- **Frozen settings.** The gravity rules (`config/rules.json`) and planner weights (`config/weights.json`) carry a freeze time, and each results file records their SHA-256. The team had already seen the LUCI results when they were frozen, so Experiments 4 and 5 are checks, not blind predictions; both say so in their results.
- **Facility assumptions.** Atmosphere ranges marked "assumed" in `config/facilities.json` are NextBurn assumptions, not facility specifications.
- **Constants.** Each constant carries its source in `config/constants.json`.
- **Experiment 1.** The ledger rows were extracted with AI help and checked by AI checkers. A team member then completed a human re-check of the 19 disputed fields. The score, 632 of 650, stays below the 98% pass mark and is reported as failed.
- **Language-model results.** The stored language-model results in Experiment 7 were written by an AI assistant acting as the SI under the guard prompt. Rerun them with the model an app actually uses before quoting them.

## Use of AI

- AI tools (Microsoft Copilot) helped with research, code, data extraction and writing.
- AI checkers reviewed ledger rows in Experiment 1, and a team member then re-checked the 19 disputed fields.
- The cover illustration in the demo deck is AI-generated.
- Every number in this repository is computed by its scripts from the cited sources.

## Troubleshooting

| Problem | What to do |
|---|---|
| `python3` is not found | Install Python 3.9 or later from https://www.python.org/downloads/. On Windows, tick "Add python.exe to PATH", or use `py` instead of `python3`. |
| "Could not make the private environment" on Debian or Ubuntu | `sudo apt install python3-venv`, then run the setup again |
| No internet connection | If numpy, scipy and matplotlib are already installed, run with `--system-packages` or `--no-venv` |
| pip says the environment is "externally managed" | Do not use `--no-venv`; let the setup make `.venv` |
| PowerShell says the command is not recognised | Type `.\setup.cmd`, with the leading `.\` |
| Port 8770 is in use | `python3 setup_nextburn.py --serve --port 8771` |
| The page still shows old results | `python console/build_console.py`, then reload the page with Ctrl+F5 |
| The FM2 check reports a changed file | Undo edits to the frozen inputs with `git checkout -- <file>`. Copying files with a tool that changes line endings also changes the hashes; clone with git instead. |

## Contributing

Issues and pull requests are welcome. Before you open a pull request:

1. Run `python tests/run_tests.py` and `python run_all.py --skip-sim`.
2. Commit the regenerated results with your change, so `index.html` matches the code.

Settings changes can also be proposed from the console's **Propose on GitHub** button.

---

NextBurn is an independent NASA Space Apps Challenge 2026 entry. It is not produced, reviewed or endorsed by NASA and uses no NASA logos. NASA data are used under their public terms.

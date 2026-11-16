# Checklist: the six-step method

Generated 2026-11-16T01:40:31+00:00 from results/method and predictions. Status words follow the evidence, not the plan.

| # | Requirement | Status | Evidence | Remaining gap |
|---|---|---|---|---|
| 1 | Test-point ledger | Done, with gaps | 313 test points from 14 sources, 67 with an outcome; every row has a source and locator; 51 outcome quotes checked, 0 not found; data checks PASS | PSI tables: 263 rows from 5 investigations read from psi.nasa.gov; none states pressure, 234 report no outcome, and one PSI-25 column (final CO) was not read. Feier and Sacksteder figure data are not digitized; MAPTIS is not used. |
| 2 | Operating envelope | Done | ISS cabin air: 21% O2, 14.7 psia, microgravity; Exploration atmosphere, Moon: 34% O2, 8.2 psia, 0.16 g; NESC TB 26-05 condition, Moon: 37% O2, 8.2 psia, 0.16 g; Exploration atmosphere, Mars: 34% O2, 8.2 psia, 0.38 g; NESC TB 26-05 condition, Mars: 37% O2, 8.2 psia, 0.38 g | Flow is not an envelope axis (habitat presets set no flow). |
| 3 | Binned coverage | Done | Thin fabrics, envelope bins tested / nearby / none: microgravity 3/11/10, Moon 1/3/20, Mars 0/0/24. Operating points: ISS cabin air tested; Exploration atmosphere, Moon none; NESC TB 26-05 condition, Moon none; Exploration atmosphere, Mars none; NESC TB 26-05 condition, Mars none | Tests with unstated or one-sided pressure are listed but not placed. |
| 4 | Boundary model with decline | Done, with a stated weakness | 23 observations (3 did not burn); R-hat 1.02; declines on 96% of the map; answers at 2 of 10 operating-point checks (ISS cabin air) | Leave-one-out Brier 0.153 is worse than always predicting the base rate (0.113): with 3 no-burn tests the model cannot predict an extinction it has not seen. Run 1 contradicted a test; fixed in version 1.1. |
| 5 | Next tests ranked by uncertainty reduction | Done | Plan of 10 tests chosen one at a time; first: Mars gravity, 37% O2 at 8.2 psia (45%); after 4 tests 73%; after 10 tests 83% | Reductions are model-based; rig oxygen and pressure limits for drop towers and parabolic flights are assumptions. |
| 6 | Falsifiable FM2 predictions | Done | Frozen 2026-11-16T00:10:42+00:00; SHA-256 of fm2_predictions.json 05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248. Burn 1 declined, burn 2 sustains (P 0.89, 90% 0.61 to 1.00), burn 3 declined, burn 4 declined | Declined burns are still scored by their published probabilities (Brier score). Post the hash on the project page. |

## 30-hour scope check

- One material family: thin fabrics and papers, with SIBAL as the reference material (FM2 burns SIBAL). PMMA is fitted with the same code only for FM2 burns 3 and 4.
- Three variables: oxygen, pressure and gravity. Flame direction and a per-material offset are added because FM2 and the FM2 team's tests depend on direction.
- Coverage map, boundary model with its decline region, and a test plan longer than five: present (see results/method).
- Data rules: NTRS reports used; MAPTIS not used (NESC TB 26-05 cites MAPTIS reports, and only the public bulletin text is used); PSI: included.

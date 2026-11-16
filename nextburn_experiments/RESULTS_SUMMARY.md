# NextBurn experiment results

Generated 2026-11-16T03:32:01+00:00 from the results files. Ledger: 98 rows from 8 NASA sources, 40 test points.

| # | Experiment | Status | Headline |
|---|---|---|---|
| 1 | Ledger accuracy | NOT SATISFACTORY | 632 of 650 sampled fields correct (97.2%, 95% interval 95.7% to 98.2%) against a 98% pass mark set in advance; strict count 631 of 650 (97.1%) |
| 2 | Range and unit checks | PASS | 7 of 7 checks pass on 98 ledger rows; 12 of 12 planted faults caught; 1 duplicate row merged |
| 3 | Coverage sensitivity | PASS | Moon-base atmosphere has no direct lunar-gravity test in all 6 tolerance runs and both cross-checks; 2 of 30 cells tested and 1 bounded in every run |
| 4 | LUCI holdout and gravity-rule comparison | REPORTED | Square-root rule: +3.4% and +8.3% at the flame tips (hits), -33.8% at the fabric base (miss); implied exponents 0.52, 0.54, 0.27; lunar ratio band 0.17 to 0.61 (3.7-fold) |
| 5 | Planner retrodiction | PASS | On pre-2025 evidence the top five includes a lunar-gravity spread-rate test; it stays there in 78.1% of 1000 weight draws (random picks: 42.4%); a lunar test of any kind in 99.8% (random: 98.7%) |
| 6 | Planner efficiency (SIMULATION) | PASS (simulation) | In simulation (200 random two-variable boundaries), choosing each test by uncertainty found the minimum extinction oxygen within 0.5 points in a median of 11 tests (80th percentile 14) versus 24 (80th percentile 30) for the plan's fixed 6x6 test matrix, with 100% vs 86% success. |
| 7 | SI test set: cite the ledger or decline | PASS | Guarded SI: 35/35 answers, 240/240 numbers grounded; 10/10 unanswerable declined; 5/5 overrides refused; 0/20 answerable wrongly declined; independent held-out set, first run: 8 of 10 correct, 10 of 10 grounded; after the fix, 8 of 8 still-unseen items correct; language-model SI under the guard prompt: 35/35 answers, 134/134 numbers grounded, 10/10 declined, 5/5 refused, 0/20 wrongly declined |

## Six-step method (ledger, envelope, coverage, boundary model, test plan, FM2 predictions)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Test-point ledger | Done, with gaps | 313 test points from 14 sources, 67 with an outcome; every row has a source and locator; 51 outcome quotes checked, 0 not found; data checks PASS |
| 2 | Operating envelope | Done | ISS cabin air: 21% O2, 14.7 psia, microgravity; Exploration atmosphere, Moon: 34% O2, 8.2 psia, 0.16 g; NESC TB 26-05 condition, Moon: 37% O2, 8.2 psia, 0.16 g; Exploration atmosphere, Mars: 34% O2, 8.2 psia, 0.38 g; NESC TB 26-05 condition, Mars: 37% O2, 8.2 psia, 0.38 g |
| 3 | Binned coverage | Done | Thin fabrics, envelope bins tested / nearby / none: microgravity 3/11/10, Moon 1/3/20, Mars 0/0/24. Operating points: ISS cabin air tested; Exploration atmosphere, Moon none; NESC TB 26-05 condition, Moon none; Exploration atmosphere, Mars none; NESC TB 26-05 condition, Mars none |
| 4 | Boundary model with decline | Done, with a stated weakness | 23 observations (3 did not burn); R-hat 1.02; declines on 96% of the map; answers at 2 of 10 operating-point checks (ISS cabin air) |
| 5 | Next tests ranked by uncertainty reduction | Done | Plan of 10 tests chosen one at a time; first: Mars gravity, 37% O2 at 8.2 psia (45%); after 4 tests 73%; after 10 tests 83% |
| 6 | Falsifiable FM2 predictions | Done | Frozen 2026-11-16T00:10:42+00:00; SHA-256 of fm2_predictions.json 05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248. Burn 1 declined, burn 2 sustains (P 0.89, 90% 0.61 to 1.00), burn 3 declined, burn 4 declined |

## Figures in the plan that changed when re-computed

| Item | Plan said | Experiments give | Why |
|---|---|---|---|
| LUCI spin against lunar gravity | 1.619 m/s2, 0.4% below nominal | 1.619 m/s2, -0.07% from NASA's fact-sheet 1.62 m/s2 | the plan's 0.4% used 1.625 m/s2 |
| Square-root rule at the fabric flame base | rule 32.2% low (ratio 0.600) | rule 33.8% low (ratio 0.613 from the ledger's 0.92 mm/s [R001] and 1.5 mm/s [R003]) | the plan used a rounded 0.9 mm/s and g = 0.1657 |
| Square-root rule at the flame tips | 3.6% and 8.6% high | 3.4% high and 8.3% high | LUCI's own spin gravity (0.1651 g) instead of 0.1657 |
| Uncertainty band for untested lunar cells | exponents 0.28 to 1.0, ratio 0.17 to 0.61 (3.6-fold) | exponents 0.27 to 1.00, ratio 0.165 to 0.613 (3.7-fold); Mars 0.38 to 0.77 (2.0-fold) | lowest implied exponent from the ledger's rates |
| Burn distance in a parabola | about 22.5 s parabola: 2.0 to 3.4 cm | NASA parabola about 20 s: 1.8 to 3.0 cm; Novespace 0.16 g up to 25 s: 2.3 to 3.8 cm | facility catalogue times instead of a single 22.5 s value |

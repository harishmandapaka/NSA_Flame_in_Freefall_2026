# Six-step method results

Generated 2026-11-16T01:40:31+00:00.

## Step 1: test-point ledger

313 test points (ledger v2 40, added in v3 2, derived 8, PSI table 263). 67 have an outcome. Rows added in this version: R099, R100 (NESC TB 26-05). Outcome evidence: 51 quotes checked, 0 not found. Data checks on the extended ledger: PASS.

File: step1_test_point_ledger.csv (one row per test with material, oxygen, pressure, gravity, flow, outcome, quotes, sources, locators and URLs).

## Step 2: operating envelope

| Point | Oxygen | Pressure | Gravity | Weight | Source |
|---|---|---|---|---|---|
| ISS cabin air | 21% | 14.7 psia | 0 g | 1.0 | Plan presets: space station cabin at 21% oxygen and 14.7 psia |
| Exploration atmosphere, Moon | 34% | 8.2 psia | 0.16 g | 1.0 | FM2 poster, NTRS 20240015307: 34% oxygen at 8.2 psia for the Human Landing System and Lunar Rover |
| NESC TB 26-05 condition, Moon | 37% | 8.2 psia | 0.16 g | 1.0 | NESC TB 26-05, NTRS 20260006043: materials evaluated for use at 37% oxygen and 8.2 psia |
| Exploration atmosphere, Mars | 34% | 8.2 psia | 0.38 g | 0.5 | Same atmosphere assumed for a Mars habitat |
| NESC TB 26-05 condition, Mars | 37% | 8.2 psia | 0.38 g | 0.5 | NESC TB 26-05: elevated oxygen planned for future Moon and Mars missions |

## Step 3: binned coverage

Bins: oxygen [13.5, 16.5, 19.5, 22.5, 25.5, 28.5, 31.5, 34.5, 37.5, 40.5] %; pressure [1.5, 3.5, 5.5, 7.5, 9.5, 11.5, 13.5, 15.5] psia. Rules: At least one test of the material family has stated oxygen and pressure inside the bin, at that gravity level. No test in the bin, but a test of the family sits in an adjacent oxygen or pressure bin (one step, diagonals included) at the same gravity level, or a test's stated range overlaps the bin. Neither. Gravity is never 'nearby': a test at another gravity level does not count.

| Family | Gravity | Tested | Nearby | None |
|---|---|---|---|---|
| thin_fabric | micro | 3 | 11 | 10 |
| thin_fabric | lunar | 1 | 3 | 20 |
| thin_fabric | mars | 0 | 0 | 24 |
| thick_plastic | micro | 4 | 12 | 8 |
| thick_plastic | lunar | 1 | 3 | 20 |
| thick_plastic | mars | 0 | 0 | 24 |
| other_textile | micro | 0 | 0 | 24 |
| other_textile | lunar | 0 | 0 | 24 |
| other_textile | mars | 0 | 0 | 24 |

| Operating point (thin fabrics) | Bin status | Nearest tests, any gravity |
|---|---|---|
| ISS cabin air | tested | LUCI NS-29 lunar spin (lunar, 20.95%, 14.7 psia, distance 0.0); Saffire I-1 (micro, 21%, 14.5 psia, distance 0.1) |
| Exploration atmosphere, Moon | none | Saffire VI-2 (micro, 31%, 7.85 psia, distance 1.0); Saffire V-2 (micro, 26.2%, 10.25 psia, distance 2.7) |
| NESC TB 26-05 condition, Moon | none | Saffire VI-2 (micro, 31%, 7.85 psia, distance 2.0); Saffire V-2 (micro, 26.2%, 10.25 psia, distance 3.7) |
| Exploration atmosphere, Mars | none | Saffire VI-2 (micro, 31%, 7.85 psia, distance 1.0); Saffire V-2 (micro, 26.2%, 10.25 psia, distance 2.7) |
| NESC TB 26-05 condition, Mars | none | Saffire VI-2 (micro, 31%, 7.85 psia, distance 2.0); Saffire V-2 (micro, 26.2%, 10.25 psia, distance 3.7) |

## Step 4: flammability boundary

logit P(sustained flame) = b0 + b_o2*(O2% - 21)/5 + b_lnp*log2(P / 101.325 kPa) + b_micro*[forced-flow microgravity] + b_g*g + b_g2*g^2 + b_dir*d + b_dir_g*d*g + b_dir_g2*d*g^2 + material offset; d = +1 upward or concurrent, -1 downward or opposed

Answer only when (a) a test of the same family lies within distance 1.0, where 3 oxygen points, a 30% pressure change, 0.08 g or an opposite flame direction each count as 1.0, (b) the 90% interval of the probability is no wider than 0.6, and (c) no test within distance 1.0 had the opposite outcome to the model's answer. Otherwise decline and name the nearest tests.

Fit: 23 observations, 3 did not burn, 3 materials; max R-hat 1.020. Leave-one-out Brier 0.153 (base rate 0.113); leave-one-out accuracy 0.78. Missed when left out: T02 (burned), T04 (did not burn), T05 (did not burn), T16 (burned), T17 (did not burn).

| Operating point | Direction | P(sustains) | 90% interval | Answer | Reason |
|---|---|---|---|---|---|
| ISS cabin air | upward or concurrent | 0.94 | 0.78 to 1.00 | sustains |  |
| ISS cabin air | downward or opposed | 0.97 | 0.84 to 1.00 | sustains |  |
| Exploration atmosphere, Moon | upward or concurrent | 0.91 | 0.38 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 2.24: Saffire VI-2); 90% interval 0.38 to 1.00 is wider than 0.6 |
| Exploration atmosphere, Moon | downward or opposed | 0.93 | 0.52 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 2.46: Saffire VI-2) |
| NESC TB 26-05 condition, Moon | upward or concurrent | 0.91 | 0.32 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 2.83: Saffire VI-2); 90% interval 0.32 to 1.00 is wider than 0.6 |
| NESC TB 26-05 condition, Moon | downward or opposed | 0.93 | 0.45 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 3.00: Saffire VI-2) |
| Exploration atmosphere, Mars | upward or concurrent | 0.89 | 0.31 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 4.52: feier_2001 NASA KC-135 aircraft); 90% interval 0.31 to 1.00 is wider than 0.6 |
| Exploration atmosphere, Mars | downward or opposed | 0.90 | 0.33 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 4.62: feier_2001 NASA KC-135 aircraft); 90% interval 0.33 to 1.00 is wider than 0.6 |
| NESC TB 26-05 condition, Mars | upward or concurrent | 0.90 | 0.26 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 5.16: Saffire VI-2); 90% interval 0.26 to 1.00 is wider than 0.6 |
| NESC TB 26-05 condition, Mars | downward or opposed | 0.90 | 0.26 to 1.00 | declined | no thin fabric test within distance 1.0 (nearest 5.25: Saffire VI-2); 90% interval 0.26 to 1.00 is wider than 0.6 |

Changes after run 1: Run 1 (version 1.0) answered 'sustains' (P = 0.90) for SIBAL burning upward in air at lunar gravity, while the only test at those conditions (FM2 team, R076) found that it does not burn upward. A model must never overrule a test at the same conditions, so rule (c) was added. Run 1 treated forced-flow microgravity as gravity 0 on the same curve as buoyant partial gravity, which forced one smooth curve through two physical regimes. Version 1.1 gives forced-flow microgravity its own term (b_micro) and lets each flame direction bend differently with gravity (b_dir_g2). Run 1 leave-one-out Brier score was 0.151, worse than always predicting the base rate (0.113). Both changes were made after seeing run 1 and before any FM2 result exists; run 1 outputs are kept in results/method/history. The first version of rule (c) used a radius of 0.5, which let the model answer 'sustains' just outside that radius from the FM2 team's no-burn result. The radius now equals the support radius (1.0), so the model never answers against a test inside its own support region.

## Step 5: next tests

| Step | Facility | Gravity | Oxygen | Pressure | Direction | P(sustains) now | Cumulative reduction |
|---|---|---|---|---|---|---|---|
| 1 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | mars | 37% | 8.2 psia | upward | 0.89 | 45.3% |
| 2 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | mars | 37% | 8.2 psia | downward | 0.90 | 61.6% |
| 3 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | lunar | 37% | 8.2 psia | upward | 0.90 | 68.7% |
| 4 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | lunar | 37% | 8.2 psia | downward | 0.93 | 73.2% |
| 5 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | mars | 37% | 10.2 psia | upward | 0.90 | 76.1% |
| 6 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | mars | 37% | 10.2 psia | downward | 0.91 | 78.2% |
| 7 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | lunar | 37% | 10.2 psia | upward | 0.91 | 79.9% |
| 8 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | lunar | 37% | 10.2 psia | downward | 0.94 | 81.1% |
| 9 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | lunar | 34% | 8.2 psia | upward | 0.90 | 82.2% |
| 10 | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | mars | 34% | 8.2 psia | downward | 0.90 | 83.1% |

## Step 6: FM2 predictions

Frozen 2026-11-16T00:10:42+00:00. SHA-256: 05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248.

| Burn | Fuel | Direction | Atmosphere | P(sustains) | 90% interval | Answer |
|---|---|---|---|---|---|---|
| 1 | SIBAL fabric | upward | 21% O2, 14.7 psia | 0.81 | 0.40 to 0.99 | declined |
| 2 | SIBAL fabric | downward | 21% O2, 14.7 psia | 0.89 | 0.61 to 1.00 | sustains |
| 3 | 4 mm acrylic (PMMA) rod | upward | 34% O2, 8.2 psia | 0.94 | 0.57 to 1.00 | declined |
| 4 | 4 mm acrylic (PMMA) rod | downward | 34% O2, 8.2 psia | 0.89 | 0.18 to 1.00 | declined |

Rerun: `python experiments/method_six_steps.py --no-predictions` (keeps the frozen predictions), then `python experiments/method_report.py`.

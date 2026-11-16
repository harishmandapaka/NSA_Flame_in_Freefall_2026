# Experiment 2: Range and unit checks

Generated 2026-11-16T01:39:38+00:00. Checks version 1.2 on ledger v2 (98 rows, 40 test points). Gate: **PASS**.

| Check | Status | Values checked | Failures |
|---|---|---|---|
| check_ranges | PASS | 727 | 0 |
| check_units | PASS | 126 | 0 |
| check_unique | PASS | 137 | 0 |
| check_provenance | PASS | 98 | 0 |
| check_consistency | PASS | 32 | 0 |
| check_golden | PASS | 28 | 0 |
| luci_g_from_spin | PASS | 1 | 0 |

Merged before checking (documented duplicate rule): R010 into R007.

LUCI spin check: 11 rpm at 1.22 m gives 1.6188 m/s2 (0.1651 g), -0.07% from the NASA fact-sheet lunar value of 1.62 m/s2.

## Fault injection

Each fault is planted in a copy of the ledger; the named check must fail.

| Fault | What was planted | Check that must catch it | Caught |
|---|---|---|---|
| F01 | Oxygen typed as 140% | check_ranges | yes |
| F02 | Pressure in hPa labelled kPa (1013) | check_ranges | yes |
| F03 | Negative flow speed | check_ranges | yes |
| F04 | Gravity in m/s2 instead of g | check_ranges | yes |
| F05 | Same row entered twice | check_unique | yes |
| F06 | Locator missing | check_provenance | yes |
| F07 | Unknown unit | check_units | yes |
| F08 | Reference value drifted (VI-2 at 51.4 kPa) | check_golden | yes |
| F09 | Two stated units disagree (27.6 kPa vs 14.0 psia) | check_units | yes |
| F10 | Spread rate on an extinction row | check_consistency | yes |
| F11 | Spread rate recorded in seconds | check_units | yes |
| F12 | Stated ratio inconsistent with its rates (0.93) | check_consistency | yes |

## How the checks were debugged

- Run 1 (version 1.0): 1 real duplicate in the ledger (R010 repeats R007 in other units); 2 false alarms on distinct Saffire tests with identical conditions; 3 rule false alarms (R083, R086, R093); 1 constant error (air oxygen 21.0% instead of 20.946%) that flagged the plan's correct 3.08 psia.
- Run 2 (version 1.1): 11 of 12 detected; F10 missed: the 1.1 rule needed the measurand to be named a spread rate, and the F10 mutation also overwrote the row's extinction wording.
- Changes:
  - A row is treated as a spread-rate measurement only when its measurand is a spread rate, not a count of spread rates or a gravity level (false alarms on R086 and R093 in run 1).
  - An extinction row fails when it carries a speed that is not a flow speed; a flow speed at blowoff is legitimate (false alarm on R083 in run 1). Version 1.1 required the measurand name to say 'spread rate', which missed injected fault F10, so version 1.2 tests the unit instead.
  - Two test points with identical conditions are duplicates only when at least one has no named test ID; Saffire I-1, II-5, II-6 and III-1 are distinct tests (false alarms in run 1).
  - Air is 20.946% oxygen by volume (IUPAC); run 1 used 20.9% for rows and 21.0% for the plan's sea-level partial pressure, which flagged the plan's 3.08 psia wrongly.

Reference values in the Saffire VI presentation text: PASS.

## Rerun

`python experiments/exp2_checks.py --sources <folder of source .txt files>` or `python tests/run_tests.py`. Exit code 1 blocks deployment.

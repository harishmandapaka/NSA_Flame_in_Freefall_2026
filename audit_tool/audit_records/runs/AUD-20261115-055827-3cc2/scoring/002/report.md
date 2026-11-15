# Audit report: run AUD-20261115-055827-3cc2, scoring 002

Date (UTC): 2026-11-15T05:58:28Z. Operator: Copilot (AI assistant). Label: Experiment 1 replay.

Ledger: 98 rows. SHA-256 of the ledger: e4551ea5dab2c2126a98d19aada2d96206955377d7c4f9f82a5918d944659835.

## Result: NOT SATISFACTORY

The limit for field accuracy is 98.0% or more. The field accuracy after review is 97.1%.

| Measure | Result | 95% interval |
|---|---|---|
| Fields correct, after review | 631 of 650 = 97.1% | 95.5% to 98.1% (Wilson) |
| Fields correct, row bootstrap | | 95.7% to 98.3% |
| Fields correct, checker verdicts only | 631 of 650 = 97.1% | 95.5% to 98.1% |
| Numbers correct (measurement, value, unit, qualifier) | 200 of 200 = 100.0% | 98.1% to 100.0% |
| Rows with all fields correct | 34 of 50 = 68.0% | 54.2% to 79.2% |
| Rows with a source and a locator (all rows) | 98 of 98 | |
| Quotes of the ledger found in the source (all rows) | 98 of 98 | |

Errors permitted at this sample size: 13. Errors after review: 19.

Share of bootstrap resamples at or above the limit: 9.6%.

## Accuracy by field

| Field | Correct | Rate |
|---|---|---|
| locator | 49/50 | 98.0% |
| platform | 46/50 | 92.0% |
| gravity | 50/50 | 100.0% |
| material | 49/50 | 98.0% |
| geometry | 46/50 | 92.0% |
| direction | 48/50 | 96.0% |
| flow | 49/50 | 98.0% |
| pressure | 50/50 | 100.0% |
| oxygen | 44/50 | 88.0% |
| measurement | 50/50 | 100.0% |
| value | 50/50 | 100.0% |
| unit | 50/50 | 100.0% |
| qualifier | 50/50 | 100.0% |

## Accuracy by source

| Source | Correct | Rate |
|---|---|---|
| bass2_poster_2014 | 90/91 | 98.9% |
| feier_2001 | 23/26 | 88.5% |
| fm2_poster_2024 | 39/39 | 100.0% |
| luci_2025 | 162/169 | 95.9% |
| sacksteder_2003 | 23/26 | 88.5% |
| saffire45_paper_2021 | 99/104 | 95.2% |
| saffire6_paper_2024 | 169/169 | 100.0% |
| saffire6_pres_2024 | 26/26 | 100.0% |

## Findings

| Row | Field | Checker verdict | Review | Final | Cause |
|---|---|---|---|---|---|
| R003 | oxygen | MISSED | upheld | MISSED | condition stated on another slide of the same source |
| R004 | oxygen | MISSED | upheld | MISSED | condition stated on another slide of the same source |
| R005 | oxygen | OK | added | MISSED | condition stated on another slide of the same source |
| R006 | oxygen | MISSED | upheld | MISSED | condition stated on another slide of the same source |
| R011 | oxygen | MISSED | upheld | MISSED | condition stated on another slide of the same source |
| R015 | oxygen | MISSED | upheld | MISSED | condition stated on another slide of the same source |
| R024 | geometry | MISSED | upheld | MISSED | condition stated elsewhere in the same source |
| R057 | platform | NOT_IN_SOURCE | upheld | NOT_IN_SOURCE | fact inferred from outside the cited source |
| R058 | platform | NOT_IN_SOURCE | upheld | NOT_IN_SOURCE | fact inferred from outside the cited source |
| R060 | platform | NOT_IN_SOURCE | upheld | NOT_IN_SOURCE | fact inferred from outside the cited source |
| R061 | platform | NOT_IN_SOURCE | upheld | NOT_IN_SOURCE | fact inferred from outside the cited source |
| R070 | flow | WRONG | upheld | WRONG | incomplete transcription |
| R081 | geometry | MISSED | overturned | OK | checker over-reach |
| R084 | direction | MISSED | upheld | MISSED | condition stated elsewhere in the same panel |
| R094 | material | WRONG | upheld | WRONG | imprecise transcription |
| R094 | geometry | MISSED | upheld | MISSED | condition stated in a figure caption |
| R094 | direction | MISSED | upheld | MISSED | condition stated elsewhere in the same section |
| R097 | locator | WRONG | upheld | WRONG | imprecise locator |
| R097 | geometry | MISSED | upheld | MISSED | condition stated elsewhere in the same source |
| R098 | geometry | MISSED | upheld | MISSED | condition stated elsewhere in the same source |

## Quote checks

Checker quotes: 147. Quotes not found in the source: 0.


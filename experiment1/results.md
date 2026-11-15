# Experiment 1: ledger accuracy audit, run 1

NextBurn, NASA Space Apps Challenge 2026 (Flame in Freefall). Run on 15 November 2026.

## Question

Does every number in the NextBurn evidence ledger trace to the page it came from, and are the fields around it (test conditions, platform, units) transcribed correctly?

## Method

- **Ledger audited:** a starter ledger of 98 test-point rows hand-extracted from 8 public NASA documents (see `sources.csv`): LUCI, Saffire IV to VI, the FM2 plan, BASS-II and NASA aircraft partial-gravity tests. Each row records its source, a locator (page, table or slide) and a verbatim supporting quote, machine-checked against the source text. PSI table rows are not yet included.
- **Sample:** 50 rows drawn with a fixed seed (2026), stratified by source with proportional allocation (`sample_ids.json`).
- **Check:** three independent checkers, blind to how the rows were made, verified 13 fields per row (650 field checks) against the cited source. Every verdict needed a verbatim quote; a script confirmed all quotes exist in the sources (0 fabricated quotes).
- **Adjudication:** each of the 19 disputed fields was re-read against the source: 18 confirmed as errors, 1 overturned (`audit_sheet.csv`).
- **Pass criterion (set in advance):** at least 98% of audited fields correct, and every row carries a source and a locator.

## Results

| Measure | Result | 95% interval |
|---|---|---|
| Fields correct | 632 of 650 = **97.2%** | 95.7–98.2% (Wilson); 95.8–98.5% (row bootstrap) |
| Numbers correct (value, unit, measurement, qualifier) | 200 of 200 = **100%** | 98.1–100% |
| Rows with every field correct | 35 of 50 = 70.0% | 56.2–80.9% |
| Rows with a source and a locator | 98 of 98 = 100% | |
| Raw checker verdicts, before adjudication | 631 of 650 = 97.1% | 95.5–98.1% |

**Verdict: not yet passed.** Provenance passed, and every sampled number matched its source, but field accuracy (97.2%) fell short of the 98% target; only 15% of bootstrap resamples reach 98%.

### Accuracy by field

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
| oxygen | 45/50 | 90.0% |
| measurement | 50/50 | 100.0% |
| value | 50/50 | 100.0% |
| unit | 50/50 | 100.0% |
| qualifier | 50/50 | 100.0% |

### Accuracy by source

| Source | Correct | Rate |
|---|---|---|
| bass2_poster_2014 | 90/91 | 98.9% |
| feier_2001 | 23/26 | 88.5% |
| fm2_poster_2024 | 39/39 | 100.0% |
| luci_2025 | 163/169 | 96.4% |
| sacksteder_2003 | 23/26 | 88.5% |
| saffire45_paper_2021 | 99/104 | 95.2% |
| saffire6_paper_2024 | 169/169 | 100.0% |
| saffire6_pres_2024 | 26/26 | 100.0% |

## What went wrong, and the fix

| Root cause | Confirmed errors | Example | Fix rule |
|---|---|---|---|
| A test condition stated elsewhere in the same source was left "not stated" | 11 | Oxygen for LUCI 1-g burns is on a different slide | Fill each test's conditions from anywhere in the source and cite where each came from |
| A fact imported from outside the cited source | 4 | "Cygnus" for Saffire I and II, which this paper does not name | Record only what the cited source says; put outside facts in a separate, cited column |
| Imprecise transcription | 3 | Saffire V-3 flow cut to 5 cm/s for 300 s before fan-off was dropped | Record full flow schedules, exact model fuels and precise locators |

All 18 confirmed errors were fixed. Applying the same three rules to the rest of the ledger corrected 13 more fields (12 in rows the sample did not draw, and 1 that a checker had passed), 31 changes in all (`fixes.csv`). The corrected ledger is `ledger_v2.csv`.

## Limitations

- The independent checks were done by AI reviewers with machine-verified quotes, and disputes were adjudicated by the extraction side. A team member should re-adjudicate the 19 disputed fields before this is published as human-verified.
- Source text was extracted from PDFs by a web service without page numbers, so locators are slides, tables and sections rather than page numbers.
- The accuracy of the corrected ledger (v2) has not been measured. It needs a fresh-row rerun; the 48 rows not sampled here are the natural next sample.
- Field-level intervals treat fields as independent; the row bootstrap interval allows for errors clustering within rows.
- Two checkers judged equivalent cells differently once (R005 and R006, oxygen), a sign that "not stated" calls need a written rule.

## Reproduce

`scripts/sample_rows.py` draws the sample (seed 2026), `scripts/audit_score.py` scores verdicts and adjudications, `scripts/fix_ledger.py` applies the fix rules, and `scripts/build_ledger.py` holds every extracted row with its quote. `scripts/checker_instructions.md` is the brief the checkers followed. The scripts expect the run layout: `ledger_v1.json` at the top level, verdicts and `adjudication.json` in an `audit/` folder, and source texts in a `sources/` folder named by source_id. Fetch the source documents from the links in `sources.csv`; they are not redistributed here.

## Suggested public wording

"In a blind audit of 50 randomly sampled ledger rows (650 field checks), every sampled number matched its NASA source and 97.2% of all fields were correct. We fixed all 18 confirmed errors and 13 related ones, and we re-audit fresh rows before each release."

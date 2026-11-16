# Experiment 1: ledger accuracy audit (ASD-STE100 style)

NextBurn team, NASA Space Apps Challenge 2026, challenge "Flame in Freefall". Audit date: 15 November 2026.

This text uses the writing rules of ASD-STE100, Issue 9: short sentences, active voice, one instruction in each step, and no "-ing" verb forms. We did not compare each word with the STE dictionary.

## 1. Terms

| Term | Description |
|---|---|
| Ledger | The NextBurn table of test data from NASA documents. Each row is one test point. |
| Field | One column of a row, for example "oxygen" or "value". |
| Source | The NASA document that gives the data of a row. |
| Locator | The location of the data in the source: a slide, a table or a section. |
| Quote | A short copy of the source text that shows the data. |
| Checker | A reviewer who compares rows with the source. The checker did not make the rows. |
| Verdict | The decision of a checker for one field. |
| Finding | A verdict that is not OK (a technical name in this audit). |
| Review | The reviewer examines a finding again against the source text. |
| Ledger v1, ledger v2 | The ledger before the changes (v1) and after the changes (v2). |

## 2. Purpose of the experiment

The NextBurn ledger has 98 rows of test data from 8 NASA documents. Experiment 1 measures the accuracy of the data that we copied into the ledger. The experiment answers two questions:

1. Does each row show its source, its locator and a quote that is in the source?
2. When a checker compares the 13 fields of a row with the source, are the fields correct?

## 3. What the audit examines

The audit has two levels. Level 1 examines all rows. Level 2 examines a sample of rows in more detail.

### 3.1 Level 1: provenance of all 98 rows

A script examined each row of ledger v1. The script did two checks:

- The row has a source and a locator.
- The quote of the row is in the source text.

All 98 rows have a source and a locator. The script found all 98 quotes in the source texts.

### 3.2 Level 2: accuracy of 13 fields in a sample of 50 rows

Three checkers examined 13 fields in each sampled row. Thus, the checkers gave 650 verdicts (50 rows multiplied by 13 fields).

| Field | What the checker compares with the source |
|---|---|
| locator | The slide, table or section that contains the value |
| platform | The vehicle or facility of the test |
| gravity | The gravity level of the test |
| material | The material of the fuel sample |
| geometry | The shape and the dimensions of the fuel sample |
| direction | The direction of flame spread, for example upward, downward or opposed to the flow |
| flow | The speed of the air flow and the flow schedule |
| pressure | The pressure of the test atmosphere |
| oxygen | The oxygen concentration of the test atmosphere |
| measurement | The quantity that the value measures, for example flame spread rate |
| value | The number |
| unit | The unit of the number |
| qualifier | The type of the number: exact, approximate, range, upper bound, lower bound or categorical |

Each checker gave one of four verdicts for each field:

| Verdict | Description |
|---|---|
| OK | The field agrees with the source for this test. |
| WRONG | The source gives a different value. |
| NOT_IN_SOURCE | The source does not give this value for this test. The value comes from a different test, a different column or a different document. |
| MISSED | The ledger says "not stated", but the source gives the value for this test. |

The checkers obeyed these rules:

- A checker did not see the ledger scripts or the verdicts of the other checkers.
- For each row, the checker gave one to three quotes from the source.
- One quote contains the value. One quote shows the reason for each verdict that is not OK.

A script searched for each checker quote in the source text. The script found all the quotes. Thus, no checker gave a quote that is not in the source.

We set two limits before the audit:

- Field accuracy: 98% or more of the 650 field verdicts are correct.
- Provenance: 100% of the rows have a source and a locator.

## 4. How we selected the 50 rows

We selected the rows with these steps:

1. We used all 98 rows of ledger v1.
2. We set the sample size to 50 rows (51% of the ledger).
3. We put the rows into 8 groups, one group for each source.
4. We gave each group a number of sample rows in proportion to its size.
5. We gave the last 2 rows to the groups with the largest remainders.
6. We used a random generator with the fixed seed 2026. Thus, a different person can select the same 50 rows again.
7. We divided the 50 rows into 3 packets of 17, 17 and 16 rows. Each checker received one packet.

This method puts each source in the sample. A simple random sample can select no rows from a small source.

| Source | Rows in ledger v1 | Rows in the sample |
|---|---|---|
| luci_2025 (LUCI) | 26 | 13 |
| saffire6_paper_2024 (Saffire VI paper) | 26 | 13 |
| saffire45_paper_2021 (Saffire IV and V paper) | 16 | 8 |
| bass2_poster_2014 (BASS-II poster) | 14 | 7 |
| fm2_poster_2024 (FM2 poster) | 6 | 3 |
| feier_2001 (Feier) | 4 | 2 |
| saffire6_pres_2024 (Saffire VI presentation) | 3 | 2 |
| sacksteder_2003 (Sacksteder) | 3 | 2 |
| Total | 98 | 50 |

## 5. The first result: 97.2%

### 5.1 Checker verdicts

631 of the 650 verdicts were OK (97.1%). The checkers gave 19 findings: 12 MISSED, 4 NOT_IN_SOURCE and 3 WRONG.

### 5.2 Review of the 19 findings

We examined each finding again against the source text:

- 18 findings are correct (upheld).
- 1 finding is not correct (overturned).

The overturned finding is the geometry of row R081. The checker gave MISSED. The source gives "1/4 inch" only for one rod in a 1-g comparison. The source does not give this dimension for all 24 rods. Thus, "not stated" is correct.

After the review, 632 of 650 fields are correct (97.2%).

| Measure | Result | 95% interval |
|---|---|---|
| Fields correct after the review | 632 of 650 = 97.2% | 95.7% to 98.2% |
| Numbers correct (measurement, value, unit, qualifier) | 200 of 200 = 100% | 98.1% to 100% |
| Rows with all 13 fields correct | 35 of 50 = 70.0% | 56.2% to 80.9% |
| Rows with a source and a locator | 98 of 98 = 100% | |

### 5.3 Decision

The limit is 98%. For 650 fields, the limit is 13 wrong fields or fewer. The audit found 18 wrong fields. Thus, the field accuracy is not satisfactory. The provenance is satisfactory.

### 5.4 Strict count (we recommend this number for publication)

The review examined only the 19 findings. Later, we found one more error in the sample: the oxygen field of row R005. Row R005 has the same defect as row R006. The checker of R006 gave MISSED, but the checker of R005 gave OK. With this error, 631 of 650 fields are correct (97.1%, 95% interval 95.5% to 98.1%).

## 6. What 98.2% is

98.2% is not a result after the changes. It is the upper end of the 95% interval of the result 97.2%. With 95% confidence, the true field accuracy of ledger v1 is between 95.7% and 98.2%. The size of the sample (650 fields) sets the width of this interval.

We did not measure the accuracy of ledger v2 yet.

Do not calculate a new score from the same 50 rows. We used these 50 rows to find the errors, and we changed each error that we found. Thus, a new score of these rows shows only our changes. It does not show the accuracy of the ledger.

For a correct measurement, use new rows. The 48 rows that the first sample did not select are ready for this audit. For 48 rows (624 fields), the limit is 12 wrong fields or fewer.

## 7. What we changed: 31 changes

We found three root causes for the 18 errors:

| Root cause | Errors | Example | Rule for the person who copies the data |
|---|---|---|---|
| A test condition is in a different part of the same source, but the row says "not stated". | 11 | The oxygen level of the LUCI 1-g tests is on a different slide. | Before you write "not stated", search all of the source. Write the location of each condition. |
| The row gives a fact that the source of the row does not give. | 4 | The rows give "Cygnus" for Saffire I and II. This paper names Cygnus only for Saffire IV and V. | Write only the facts that the source of the row gives. Put facts from other documents in a separate column with their own source. |
| The transcription is not precise. | 3 | The flow of Saffire V-3 is 20 cm/s, then 5 cm/s for 300 s, then fan off. The row did not show the 5 cm/s step. | Write the full flow schedule, the exact fuel name and the exact locator. |

We applied these three rules to all 98 rows:

| Changes | Fields | How we found them |
|---|---|---|
| 18 | The 18 errors from the review | Audit findings in the sample |
| 12 | Oxygen of R008, R009, R017, R018 and R023. Geometry of R025 and R026. Platform of R056, R059, R062 and R063. Flow of R069. | Same root cause, in rows that the sample did not select |
| 1 | Oxygen of R005 | Same root cause. The checker gave OK. |
| 31 in total | Oxygen 11, platform 8, geometry 6, flow 2, direction 2, material 1, locator 1 | The result is ledger v2. |

## 8. New automatic hint for "not stated" fields

The new audit script adds a Level 1 hint. The script gives a hint for a "not stated" field when two conditions are true:

- Other rows of the same source give this condition.
- The source has a word for this condition near the quote (3000 characters or less).

We tested the hint on ledger v1:

| Rows | "Not stated" fields | Known errors of this type | Hints | Errors with a hint |
|---|---|---|---|---|
| 50 sampled rows | 67 | 12 | 36 | 12 |
| All 98 rows | 130 | 19 | 74 | 19 |

Thus, a reviewer can examine 36 fields instead of 67 and find all 12 errors. We set the hint with the data of Experiment 1. Thus, measure the hint again in the next audit. The hint cannot find the other 7 errors (platform, flow, material and locator). Only Level 2 found them.

## 9. Limits of Experiment 1

- The checkers were AI reviewers. An AI on the extraction side did the review of the findings.
- Before you tell readers that persons examined the findings, a team member must examine the 19 findings again.
- The source texts came from a web text service. These texts do not show page numbers. Thus, the locators are slides, tables and sections.
- The audit examined only the starter ledger. It did not examine the rows that the team takes from the PSI data.
- We did not measure the accuracy of ledger v2 yet.

## 10. Next step: measure ledger v2

1. Open the run "Ledger v2: fresh rows" in the audit records.
2. Give each of the 3 packets to a different checker.
3. Tell the checkers to obey the file instructions.md.
4. Put the verdict files in one folder.
5. Run the score command (see README.md).
6. If the field accuracy is less than 98%, find the root causes and change the ledger.

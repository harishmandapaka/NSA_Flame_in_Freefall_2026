# PSI access report (NASA Space Apps 2026, NextBurn)

Session: 2026-11-15T23:46Z to 2026-11-16T00:09Z (UTC), 30-minute time box. Every table was read directly from the rendered **Experimental Table** panel of the NASA PSI investigation page, using the local browser. Only psi.nasa.gov pages were used. Nothing was downloaded, and no login, registration or acceptance was needed or done. All five datasets are licensed CC0-1.0.

## URLs tried and result
| Investigation | URL | Result | Rows saved / paginator |
|---|---|---|---|
| PSI-25 BASS-II | https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 | OK, table read (16 of 17 columns) | 129 / 130 |
| PSI-26 BASS | https://psi.nasa.gov/physci/repo/data/investigations/PSI-26 | OK, table read (all 6 columns) | 122 / 123 |
| PSI-98 Saffire-I | https://psi.nasa.gov/physci/repo/data/investigations/PSI-98 | OK (all 13 columns) | 4 / 5 (2 burn samples) |
| PSI-99 Saffire-II | https://psi.nasa.gov/physci/repo/data/investigations/PSI-99 | OK (all 17 columns) | 15 / 16 (9 burn samples, 2 flow-vis rows, 4 note rows) |
| PSI-100 Saffire-III | https://psi.nasa.gov/physci/repo/data/investigations/PSI-100 | OK (all 9 columns) | 2 / 3 (2 burn samples) |

The paginator count is always one higher than the number of rows that show text. The extra row shows no text and is probably a blank trailing line in the source CSV, so it was not saved.

## What worked
- The **Experimental Table** panel renders the table, paginated. I set it to 100 rows per page, collapsed the side menu to widen the view, and scrolled the table sideways to read the wide tables (PSI-25).
- For PSI-25, the file selector names the source as `PSI-25_Experimental table_BASS-II.csv`. The Data files tree also lists it (16.2 KB, added Thu Feb 06 2025). That tree has no preview. I did not download the file, because the instruction was to read a table shown on the page.

## What blocked or limited the work
- No blank pages, login prompts or errors. Some clicks failed because the target was off screen; a retry after scrolling worked.
- The browser only exposes the visible part of the page, and empty cells show no text. Where a row had blanks, I placed them by column meaning or by checking the overlapping views.
- **PSI-25 "Final CO (ppm)" column is not in the CSV.** The time box ran out before it was read for every row. Values that were read (B1, B3-B11) are listed in `PSI-25.provenance.json`.
- **PSI-25 row B2**: the page shows the values 1.6, 0.44 and 6 across the final O2, CO2 and CO columns, with blank cells whose positions could not be fixed. Those cells are left empty.
- PSI-26 row 66 says only "SOOT Cleaning". It is not a burn test, and its column position is unverified.

## Normalised file (`../extra_tests/psi_tests.csv`, 263 test rows)
- Rows: PSI-25 129, PSI-26 121 (SOOT Cleaning row excluded), PSI-98 2, PSI-99 9, PSI-100 2. Flow-visualisation and note rows are excluded.
- `g` = 0.0 for all rows (ISS or orbital Cygnus). `p_kpa` is empty everywhere, because no table states a pressure.
- `o2_pct` comes from "Calibrated initial O2 % by vol" (PSI-25) or "Percent O2" (Saffire-I/II). "~ x" becomes x. A range "a - b" or "a to b" becomes the midpoint. It is empty for PSI-26 and PSI-100, and where the cell is not a number.
- `flow_cm_s` is filled only where the table gives cm/s (Saffire: 20, 20, 30). PSI-25 Fan/Air display have no units, so they were not converted.
- `family` comes from the material text only. SIBAL/cotton = thin_fabric, PMMA = thick_plastic, Nomex = other_textile. Everything else is `unknown`: rods and films that do not say "PMMA", spheres, wax, candles, Ultem, silicone, and the PMMA & Nomex composite.
- `direction_class`: Concurrent = with_flow; Opposed or the typo "oppsed" = against_flow (Saffire columns and PSI-26 material text). Otherwise unknown. PSI-25 states no direction.
- `outcome`: PSI-25 uses the words in Fan/Air display: "no ign" = no_ignition, "blowoff" = blowoff, "ext"/"extinguished"/"out" = extinguished. PSI-99 2-5, 2-6, 2-8 and 2-9 = sustained (long burn time and burn length, see outcome_text). All other rows are unknown, because no outcome column exists.
- `first_year` comes from the table's Date column (4-digit years 2000-2030 only). It is empty for Saffire, whose tables have no date column.

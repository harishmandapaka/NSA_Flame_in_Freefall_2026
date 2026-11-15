# Experiment 4: LUCI holdout and gravity-rule comparison

Generated 2026-11-15T09:18:26+00:00. Rules file frozen 2026-11-15T07:56:00Z (sha256 f152b6f46ca9...). The team had seen the LUCI presentation before this file was frozen, so this is a check of rules that were not fitted to LUCI, not a blind prediction.

LUCI gravity from the ledger's own spin rows: 0.1651 g. Hit = within 10%.

| LUCI ratio | Lunar | 1 g | Measured | Implied n | Square root (n = 1/2) | Cube root (n = 1/3) | Linear (n = 1) |
|---|---|---|---|---|---|---|---|
| Fabric flame tip | 1.1 mm/s [R002] | 2.8 mm/s [R004] | 0.393 | 0.52 | +3.4% hit | +39.6% | -58.0% |
| Acrylic rod flame tip | 0.15 cm/s [R007] | 0.40 cm/s [R008] | 0.375 | 0.54 | +8.3% hit | +46.3% | -56.0% |
| Fabric flame base | 0.92 mm/s [R001] | 1.5 mm/s [R003] | 0.613 | 0.27 | -33.8% | -10.6% | -73.1% |

Stated ratios in the LUCI presentation: fabric flame tip 0.39 [R006] (n = 0.52), acrylic rod flame tip 0.38 [R009] (n = 0.54), fabric flame base 0.6 [R005] (n = 0.28).

**Second check.** Upward spread over thin paper at reduced pressure scaled linearly with gravity (n = 1), which neither the square-root nor the cube-root rule predicts. Downward spread peaked between the gravity levels, so no single power law with a positive exponent describes it. Feier and colleagues report spread rates only in figures; the cited text has no spread-rate numbers. Digitizing the figures (WebPlotDigitizer) is a next step and is not done here.

**Uncertainty band for untested cells:** exponents 0.27 to 1.00 give a lunar-to-Earth ratio of 0.17 to 0.61 (3.7-fold) at the Moon and 0.38 to 0.77 (2.0-fold) at Mars.

## Buoyancy index (gravity x (pressure / 14.7 psia)^2)

| Setting | Oxygen | Pressure | Gravity | Index |
|---|---|---|---|---|
| Earth, sea level | 20.946% | 14.7 psia | 1.000 g | 1.00 |
| Earth laboratory at exploration pressure | 34% | 8.2 psia | 1.000 g | 0.31 |
| Mars habitat | 34% | 8.2 psia | 0.380 g | 0.12 |
| Moon base, upper pressure bound | 30% | 10.2 psia | 0.165 g | 0.08 |
| Moon base, exploration atmosphere | 34% | 8.2 psia | 0.165 g | 0.05 |
| Spacesuit on the Moon | 100% | 4.3 psia | 0.165 g | 0.01 |

Rerun: `python experiments/exp4_luci_rules.py`.

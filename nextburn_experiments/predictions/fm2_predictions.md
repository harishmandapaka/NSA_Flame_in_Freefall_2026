# NextBurn predictions for FM2 (frozen 2026-11-16T00:10:42+00:00)

Published before FM2 results exist. FM2 is manifested for a CLPS lunar delivery (NTRS 20240015307); no FM2 results had been reported on the freeze date.

| Burn | Fuel | Direction | Atmosphere | P(sustains), 90% interval | Model answer | Nearest evidence |
|---|---|---|---|---|---|---|
| 1 | SIBAL fabric | upward | 21% O2, 14.7 psia | 0.81 (0.40 to 0.99) | declined | FM2 team lunar-g simulation (extinguished) |
| 2 | SIBAL fabric | downward | 21% O2, 14.7 psia | 0.89 (0.61 to 1.00) | sustains | FM2 team lunar-g simulation (sustained) |
| 3 | 4 mm acrylic (PMMA) rod | upward | 34% O2, 8.2 psia | 0.94 (0.57 to 1.00) | declined | Saffire VI-3 (sustained) |
| 4 | 4 mm acrylic (PMMA) rod | downward | 34% O2, 8.2 psia | 0.89 (0.18 to 1.00) | declined | Saffire VI-3 (sustained) |

Burn 2 analog: LUCI measured 0.92 mm/s at the flame base and 1.1 mm/s at the tip for the same fabric in air at lunar gravity. Prediction: within plus or minus 50% of those values (team judgement).

Sustained means: the flame spreads away from the igniter and is still burning 10 s after the igniter turns off. Each answered burn is falsified if the observed outcome is the opposite of its decision. All four probabilities, including declined ones, are scored with the Brier score; each outcome is also checked against its 90% interval.

SHA-256 of fm2_predictions.json is in SHA256SUMS.txt. Post that hash on the project page so the prediction can be checked later.

# Experiment 3: Coverage sensitivity

Generated 2026-11-15T09:18:21+00:00. 30 cells (5 habitats x 3 material families x 2 flame directions), 40 NASA test points, 4 planned FM2 points (never counted as evidence).

**Headline:** The Moon-base atmosphere (34% oxygen at 8.2 psia) has no direct test in lunar gravity. Holds in all six runs: **True**. Normalized-distance cross-check: True. MicroFire oxygen-bin cross-check: True.

Coverage across the six runs: tested 2 to 2 cells, bounded 1 to 1, untested 27 to 27 (of 30).

| Tolerance | Tested | Bounded | Untested |
|---|---|---|---|
| oxygen +/-1 pts, pressure +/-10% | 2 | 1 | 27 |
| oxygen +/-1 pts, pressure +/-20% | 2 | 1 | 27 |
| oxygen +/-2 pts, pressure +/-10% | 2 | 1 | 27 |
| oxygen +/-2 pts, pressure +/-20% | 2 | 1 | 27 |
| oxygen +/-4 pts, pressure +/-10% | 2 | 1 | 27 |
| oxygen +/-4 pts, pressure +/-20% | 2 | 1 | 27 |

| Habitat | Cells tested across runs |
|---|---|
| Space station cabin | 2 to 2 of 6 |
| Moon base and pressurized rover | 0 to 0 of 6 |
| Moon base, upper bound | 0 to 0 of 6 |
| Spacesuit on the Moon | 0 to 0 of 6 |
| Mars habitat | 0 to 0 of 6 |

## Nearest evidence to the Moon-base atmosphere (ignoring gravity)

| Family | Test | Oxygen | Pressure | Gravity | Distance | Differences |
|---|---|---|---|---|---|---|
| thin_fabric | Saffire VI-2 | 31.0% | 7.85 psia | micro | 1.6 | gravity micro, not lunar; forced flow 20 cm/s |
| thick_plastic | Saffire VI-3 | 30.3% | 7.92 psia | micro | 1.9 | gravity micro, not lunar; forced flow 20 cm/s |

## Gravity is the missing axis

With gravity ignored, these partial-gravity cells would count as tested: moon_base|thin_fabric|with_flow (at oxygen +/-4, pressure +/-10%, oxygen +/-4, pressure +/-20%); moon_base|thick_plastic|with_flow (at oxygen +/-4, pressure +/-10%, oxygen +/-4, pressure +/-20%); moon_upper|thin_fabric|with_flow (at oxygen +/-4, pressure +/-10%, oxygen +/-4, pressure +/-20%); mars_hab|thin_fabric|with_flow (at oxygen +/-4, pressure +/-10%, oxygen +/-4, pressure +/-20%); mars_hab|thick_plastic|with_flow (at oxygen +/-4, pressure +/-10%, oxygen +/-4, pressure +/-20%).

Cells left untested because a cited source does not state oxygen or pressure (ledger gaps, not NASA gaps): iss_cabin|thick_plastic|against_flow: TP021, TP022.

Saffire VI-2 burned at 7.85 psia and 31.0% oxygen in microgravity with forced flow: nearby evidence, never a test of the Moon-base case.

## Limits

- Flow is not matched because habitat presets do not set a flow; ignoring flow makes matching more lenient, so 'untested' is conservative.
- BASS-II rows from the poster lack pressure, so they cannot match any cell; the PSI-25 table would add them.
- Rows whose direction is not stated (Saffire I to III, LUCI 1-g) cannot match a direction class.

Rerun: `python experiments/exp3_coverage.py`.

# Experiment 5: Planner retrodiction

Generated 2026-11-16T01:39:50+00:00. Weights frozen 2026-11-15T07:56:00Z (sha256 885493537d60...). Weights were frozen before this run, but by a team that already knew LUCI flew; the null baseline and the 1,000-draw sensitivity show how much the result depends on that choice.

Evidence before 1 January 2025: 36 of 40 test points (excluded: LUCI 1-g ground, LUCI NS-29 lunar spin).

**Result:** lunar-gravity test in the top five: **True**. Strict check (lunar gravity, thin fabric or PMMA, spread rate, as LUCI measured): **True**.

| # | Habitat | Material | Direction | Facility | Measurement | Score |
|---|---|---|---|---|---|---|
| 1 | Moon base and pressurized rover | thin fabric | upward/concurrent | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.810 |
| 2 | Moon base and pressurized rover | thin fabric | downward/opposed | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.810 |
| 3 | Space station cabin | thin fabric | downward/opposed | NASA Glenn 2.2 Second Drop Tower | go/no-go limit test | 0.600 |
| 4 | Moon base, upper bound | thin fabric | downward/opposed | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.571 |
| 5 | Moon base and pressurized rover | other textile | upward/concurrent | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.486 |

**Sensitivity (1000 draws, every weight and cost scaled by 0.5 to 1.5):** a lunar test stays in the top five in 99.8% of draws (optional target 80%: True); a LUCI-like test in 78.1%. Kendall's tau against the frozen ranking: median 0.51, 10th percentile 0.32.

**Null baseline:** five gap cells picked at random from the 16 feasible ones (8 lunar) include a lunar cell with probability 0.99, and a LUCI-like test with probability 0.42. If this is near 1, the basic pass criterion is weak; read the strict check and the sensitivity instead.

Gaps no catalogued facility can close (before 2025): spacesuit|thin_fabric|with_flow (5.2 s is shorter than the 20 s a spread rate needs, already allocated); spacesuit|thin_fabric|against_flow (5.2 s is shorter than the 20 s a spread rate needs, already allocated); spacesuit|thick_plastic|with_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); spacesuit|thick_plastic|against_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); spacesuit|other_textile|with_flow (5.2 s is shorter than the 20 s a spread rate needs, already allocated); spacesuit|other_textile|against_flow (5.2 s is shorter than the 20 s a spread rate needs, already allocated); moon_base|thick_plastic|with_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); moon_base|thick_plastic|against_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); moon_upper|thick_plastic|with_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); moon_upper|thick_plastic|against_flow (20.0 s is shorter than the 100 s a spread rate needs, 25.0 s is shorter than the 100 s a spread rate needs); mars_hab|thick_plastic|with_flow (20.0 s is shorter than the 100 s a spread rate needs, 30.0 s is shorter than the 100 s a spread rate needs); mars_hab|thick_plastic|against_flow (20.0 s is shorter than the 100 s a spread rate needs, 30.0 s is shorter than the 100 s a spread rate needs).

## Today's top five (all evidence, including LUCI)

| # | Habitat | Material | Direction | Facility | Measurement | Score |
|---|---|---|---|---|---|---|
| 1 | Moon base and pressurized rover | thin fabric | upward/concurrent | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.810 |
| 2 | Moon base and pressurized rover | thin fabric | downward/opposed | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.810 |
| 3 | Space station cabin | thin fabric | downward/opposed | NASA Glenn 2.2 Second Drop Tower | go/no-go limit test | 0.600 |
| 4 | Moon base, upper bound | thin fabric | downward/opposed | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.571 |
| 5 | Moon base and pressurized rover | other textile | upward/concurrent | Novespace parabolic flight (0.16 g up to 25 s, 0.38 g up to 30 s) | spread-rate measurement | 0.486 |

## Burn distance at LUCI's lunar spread rates

| Rate | 2.2 s drop | 5.18 s drop | NASA parabola, about 20 s | Novespace 0.16 g, up to 25 s | New Shepard spin, about 120 s |
|---|---|---|---|---|---|
| Acrylic rod tip, 0.15 cm/s [R007] | 0.33 cm | 0.78 cm | 3.00 cm | 3.75 cm | 18.00 cm |
| Fabric tip, 1.1 mm/s [R002] | 0.24 cm | 0.57 cm | 2.20 cm | 2.75 cm | 13.20 cm |
| Fabric base, 0.92 mm/s [R001] | 0.20 cm | 0.48 cm | 1.84 cm | 2.30 cm | 11.04 cm |

LUCI rates were published in 2025, so this table explains facility limits after the fact; the retrodiction itself uses the facility catalogue's minimum test times, not LUCI's rates.

Rerun: `python experiments/exp5_retrodiction.py`.

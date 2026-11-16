import json, re, csv, unicodedata
SRC = "sources"
def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-").replace("\u2019", "'")
    return re.sub(r"\s+", " ", s).strip()
TITLES = {
 "luci_2025": "Ferkul et al., Lunar Combustion Investigation: Flammability Results from a Rotating Sounding Rocket, ASGSR 2025 (NTRS 20250010653)",
 "saffire6_paper_2024": "Urban et al., Preliminary Results from the Saffire VI Experiment, ICES-2024-365 (NTRS 20240002981)",
 "saffire6_pres_2024": "Urban et al., Preliminary Results from the Saffire VI Experiment, ICES 2024 presentation (NTRS 20240007488)",
 "saffire45_paper_2021": "Urban et al., Fire Safety Implications of Preliminary Results from Saffire IV and V, ICES-2021-266 (NTRS 20210011521)",
 "fm2_poster_2024": "Zayac et al., Flammability of Materials on the Moon, Glenn Space Technology Symposium poster 2024 (NTRS 20240015307)",
 "bass2_poster_2014": "Ferkul et al., Combustion of Solids in Microgravity: Results from the BASS-II Experiment, ASGSR 2014 poster (NTRS 20160000593)",
 "sacksteder_2003": "Sacksteder et al., Upward and Downward Flame Spreading and Extinction in Partial Gravity Environments, 2003 (NTRS 20040053567)",
 "feier_2001": "Feier et al., Upward Flame Spread Over Thin Solids in Partial Gravity, AIAA 2001-0466 (NTRS 20010059376)",
}
TIER = {"flight-orbit": "Flight, orbital microgravity", "flight-spin": "Flight, simulated lunar gravity (spin)",
        "ground": "Ground, 1 g", "aircraft": "Aircraft, partial gravity", "planned": "Planned, no result yet",
        "model": "Model (computed)", "mixed": "Flight and ground comparison"}
rows = []
def add(src, loc, platform, gravity, material, geometry, direction, flow, pressure, oxygen, measurement, value, unit, qualifier, tier, snippet):
    rows.append(dict(source_id=src, locator=loc, platform=platform, gravity=gravity, material=material, geometry=geometry,
        direction=direction, flow=flow, pressure=pressure, oxygen=oxygen, measurement=measurement, value=str(value), unit=unit,
        qualifier=qualifier, evidence_tier=TIER[tier], snippet=snippet))
NS = "not stated"
# ---------------- LUCI ----------------
L = "luci_2025"; LP = "Blue Origin New Shepard NS-29, spinning capsule"; LG = "lunar (simulated by capsule spin)"
SIB = "SIBAL fabric (cotton-fiberglass)"; SIBG = "5 cm wide x 30 cm long"; PM = "PMMA (acrylic) rod"; PMG = "4 mm diameter rod"
G1 = "ground, LUCI 1-g burns"
add(L,"Slide 'LUCI: SIBAL fabric Linear Fit for SIBAL Flame Spread'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","flame base spread rate","0.92","mm/s","exact","flight-spin","Flame base spread rate = .92 mm/s.")
add(L,"Slide 'LUCI: SIBAL fabric Linear Fit for SIBAL Flame Spread'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","flame tip spread rate","1.1","mm/s","exact","flight-spin","Flame tip spread rate = 1.1 mm/s")
add(L,"Slide 'Combined Results: SIBAL' (flame spread rates from linear fits)",G1,"1 g",SIB,SIBG,NS,NS,NS,NS,"flame base spread rate","1.5","mm/s","exact","ground","FlameBase .9 1.5 .6")
add(L,"Slide 'Combined Results: SIBAL' (flame spread rates from linear fits)",G1,"1 g",SIB,SIBG,NS,NS,NS,NS,"flame tip spread rate","2.8","mm/s","exact","ground","FlameTip 1.1 2.8 .39")
add(L,"Slide 'Combined Results: SIBAL' (flame spread rates from linear fits)","New Shepard NS-29 vs ground 1-g burns","lunar (simulated) vs 1 g",SIB,SIBG,NS,NS,NS,NS,"ratio of lunar to 1-g flame base spread rate","0.6","-","exact","mixed","FlameBase .9 1.5 .6")
add(L,"Slide 'Combined Results: SIBAL' (flame spread rates from linear fits)","New Shepard NS-29 vs ground 1-g burns","lunar (simulated) vs 1 g",SIB,SIBG,NS,NS,NS,NS,"ratio of lunar to 1-g flame tip spread rate","0.39","-","exact","mixed","FlameTip 1.1 2.8 .39")
add(L,"Slide 'Combined Results: PMMA' (flame tip spread from linear fits)",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","flame tip spread rate","0.15","cm/s","exact","flight-spin","Partial-G(cm/s) 1-G(cm/s) Ratio .15 .40 .38")
add(L,"Slide 'Combined Results: PMMA' (flame tip spread from linear fits)",G1,"1 g",PM,PMG,NS,NS,NS,NS,"flame tip spread rate","0.40","cm/s","exact","ground","Partial-G(cm/s) 1-G(cm/s) Ratio .15 .40 .38")
add(L,"Slide 'Combined Results: PMMA' (flame tip spread from linear fits)","New Shepard NS-29 vs ground 1-g burns","lunar (simulated) vs 1 g",PM,PMG,NS,NS,NS,NS,"ratio of lunar to 1-g flame tip spread rate","0.38","-","exact","mixed","Partial-G(cm/s) 1-G(cm/s) Ratio .15 .40 .38")
add(L,"Slide 'LUCI: PMMA Flame Tip Spread Linear Fit'",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","flame tip spread rate","1.5","mm/s","exact","flight-spin","Flame tip spread is approximately linear. • Flame spread rate = 1.5 mm/s.")
add(L,"Slide '1-G Results: PMMA Flame Tip Spread Linear Fit'",G1,"1 g",PM,PMG,NS,NS,NS,NS,"flame tip growth rate at start of burn","3.95","mm/s","approximate","ground","Flame tip grows at a rate of ~ 3.95 mm/s at the beginning of the burn.")
add(L,"Slide 'LUCI: PMMA LUCI NS-29 Results: PMMA'",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","total flame base spread until extinction","6","cm","approximate","flight-spin","Total base spread of ~6cm until extinction.")
add(L,"Slide 'LUCI: PMMA Flame Base Spread and Flame Length vs. O2% for LUCI PMMA'",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","lowest chamber oxygen during burn","14.3","%","exact","flight-spin","O2% decreases from 20% to 14.3%.")
add(L,"Slide 'LUCI: PMMA Flame Base Spread and Flame Length vs. O2% for LUCI PMMA'",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","chamber oxygen after gravity decreased at 125 s","15.8","%","exact","flight-spin","O2% rises back to 15.8% likely due to the decrease in gravity (and thus buoyant flow) which occurred at 125s.")
add(L,"Slide 'Results: PMMA Flame Spread vs. O2% for LUCI PMMA' (1-G)",G1,"1 g",PM,PMG,NS,NS,NS,NS,"lowest chamber oxygen during burn","14.5","%","exact","ground","O2% rises quickly in the beginning, then decreases ~linearly from 21% to 14.5%.")
add(L,"Slide 'LUCI: SIBAL fabric Flame Length and Flame Width vs. O2% for LUCI SIBAL'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","final chamber oxygen during burn","18","%","approximate","flight-spin","O2 concentration decreases from ~20% to ~18%.")
add(L,"Slide '1-G Results: SIBAL Flame Length and Flame Width vs. O2% for LUCI SIBAL'",G1,"1 g",SIB,SIBG,NS,NS,NS,NS,"chamber oxygen during burn","20","%","approximate","ground","O2% varies slightly but is roughly constant at 20%.")
add(L,"Slide 'SIBAL Flame Width Comparison'","New Shepard NS-29 vs ground 1-g burns","lunar (simulated) vs 1 g",SIB,SIBG,NS,NS,NS,NS,"how much sooner extinction occurs in 1 g than in lunar gravity","45","s","approximate","mixed","1-g extinction happens ~ 45 seconds sooner than partial-g extinction")
add(L,"Slide 'LUCI Partial-G Recap: SIBAL'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","flame width during semi-steady spread","3.2","cm","approximate","flight-spin","constant flame width and length are observed (~3.2 cm and ~1.5 cm respectively)")
add(L,"Slide 'LUCI Partial-G Recap: SIBAL'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","flame length during semi-steady spread","1.5","cm","approximate","flight-spin","constant flame width and length are observed (~3.2 cm and ~1.5 cm respectively)")
add(L,"Slide 'LUCI Partial-G Recap: SIBAL Preheat Length'",LP,LG,SIB,SIBG,"downward",NS,"normal pressure","air","preheat length shrink rate","-0.094","mm/s","exact","flight-spin","Preheat length shrink rate = -0.094 mm/s.")
add(L,"Slide 'LUCI: PMMA Quadratic Fit for PMMA Flame Base Spread'",LP,LG,PM,PMG,"upward",NS,"normal pressure","air","peak instantaneous flame base spread rate (before 125 s)","0.6","mm/s","approximate","flight-spin","Flame spread rate increases linearly from 0 to ~.6 mm/s (before gravity starts dropping at t = 125s)")
add(L,"Slide '1-G Results: SIBAL fabric LUCI NS-29 Results'",G1,"1 g",SIB,SIBG,NS,NS,NS,NS,"time at which flame width suddenly decreases","24","s","approximate","ground","Flame width decreases suddenly at ~24 seconds, and goes to 0 within 4 seconds.")
add(L,"Summary bullets (slide after 'Page 10')",LP,LG,"SIBAL fabric and PMMA rod (burned simultaneously)",NS,NS,NS,"normal pressure","air","vehicle rotation rate","11","RPM","exact","flight-spin","A steady vehicle rotation of 11 RPM is established, with an effective radius of rotation of 1.22 m at the experiment location.")
add(L,"Summary bullets (slide after 'Page 10')",LP,LG,"SIBAL fabric and PMMA rod (burned simultaneously)",NS,NS,NS,"normal pressure","air","effective radius of rotation at the experiment","1.22","m","exact","flight-spin","A steady vehicle rotation of 11 RPM is established, with an effective radius of rotation of 1.22 m at the experiment location.")
add(L,"Summary bullets (slide after 'Page 10')",LP,LG,"SIBAL fabric and PMMA rod (burned simultaneously)",NS,NS,NS,"normal pressure","air","burn duration","2.5","min","lower bound","flight-spin","the burn lasts for over two and a half minutes")
# ---------------- Saffire VI paper ----------------
S6 = "saffire6_paper_2024"; CYG = "Cygnus cargo spacecraft (in orbit)"; MG = "microgravity (orbit)"
cond6 = {"IV-1": ("SIBAL cloth","50 cm long","concurrent","20 cm/s","100.0 kPa","22.0 mol %"),
         "V-2": ("cotton jersey","50 cm long","concurrent","20 cm/s","70.7 kPa","26.2 mol %"),
         "VI-2": ("SIBAL cloth","50 cm long","concurrent","20 cm/s","54.1 kPa","31.0 mol %"),
         "VI-3": ("two-sided PMMA","18 cm long","concurrent","20 cm/s","54.6 kPa","30.3 mol %"),
         "VI-4": ("one-sided PMMA","18 cm long","concurrent","20 cm/s","55.2 kPa","28.8 mol %")}
t2 = {"IV-1": "IV-1 SIBAL 130 3,150 409 45 25 1390 1.03 80", "V-2": "V-2 Cotton Jersey 200 2,800 560 46 23 2360 1.26 83",
      "VI-2": "VI-2 SIBAL 112 3217 580 3,650 409 48 20 2800 1.15 120", "VI-3": "VI-3 2-sided PMMA 780 3080 1280 77 21 8539 3.51 308",
      "VI-4": "VI-4 1-sided PMMA 1200 1507 830 57 21 8117 3.37 320"}
meas = [("burn duration","s",{"IV-1":"130","V-2":"200","VI-2":"112","VI-3":"780","VI-4":"1200"}),
        ("peak heat release (oxygen consumption calorimetry)","W",{"VI-2":"3217","VI-3":"3080","VI-4":"1507"}),
        ("average heat release (fuel consumption calorimetry)","W",{"IV-1":"3150","V-2":"2800","VI-2":"3650"}),
        ("maximum temperature at flow-unit outlet","degC",{"IV-1":"45","V-2":"46","VI-2":"48","VI-3":"77","VI-4":"57"}),
        ("CO2 increase at far-field inlet","ppm",{"IV-1":"1390","V-2":"2360","VI-2":"2800","VI-3":"8539","VI-4":"8117"}),
        ("CO increase at far-field inlet","ppm",{"IV-1":"80","V-2":"83","VI-2":"120","VI-3":"308","VI-4":"320"})]
for m, u, vals in meas:
    for test, v in vals.items():
        mat, geo, d, f, p, o = cond6[test]
        add(S6, f"Table 2, row {test} (conditions in Table 1, p. 3)", CYG + f", test {test}", MG, mat, geo, d, f, p, o, m, v, u, "exact", "flight-orbit", t2[test])
# ---------------- Saffire VI presentation ----------------
SP = "saffire6_pres_2024"
for m, v in [("ignition time","637"),("time flow reduced from 20 to 5 cm/s","1120"),("time duct flow terminated","1420")]:
    snip = {"637":"Ignition at 637 s","1120":"Flow reduced at 1120 s","1420":"Duct flow terminated at 0.2 0.3 1420 seconds"}[v]
    add(SP, "Slide 'Temperature results for Saffire VI-3 (two-sided PMMA)'", CYG + ", test VI-3", MG, "two-sided PMMA", "18 cm long", "concurrent", "20 cm/s, reduced to 5 cm/s", "54.6 kPa", "30.3 mol %", m, v, "s", "exact", "flight-orbit", snip)
# ---------------- Saffire IV and V paper ----------------
S45 = "saffire45_paper_2021"
t2b = {"I-1":("20","21","100","SIBAL","4","6.2","46","41","94"),"II-5":("20","21","100","SIBAL","4","4","46","5","30"),
       "II-6":("25","21","100","SIBAL","5","5","46","5","30"),"III-1":("25","21","100","SIBAL","5","8.2","46","41","94"),
       "IV-1":("20","22","100","SIBAL","8.5","11.0","30","41","50"),"V-2":("20","26.2","70.7","Cotton jersey","10.0","14.0","30","41","50")}
for test,(fl,ox,pr,mat,ss,mx,dh,w,ln) in t2b.items():
    d = "concurrent" if test in ("IV-1","V-2") else NS
    for m, v in [("steady-state flame size", ss), ("maximum flame size", mx)]:
        add(S45, f"Table 2, column {test}", "Cygnus cargo spacecraft (in orbit), Saffire " + test, MG, mat, f"{w} cm wide x {ln} cm long; duct height {dh} cm", d, f"{fl} cm/s", f"{pr} kPa", f"{ox} %", m, v, "cm", "exact", "flight-orbit", "Table 2 Test Conditions and flame size for thin samples")
add(S45,"Text discussing Figure 3 (Saffire V sample 2)","Cygnus cargo spacecraft (in orbit), Saffire V-2",MG,"cotton jersey","50 cm long","concurrent","20 cm/s (fan on)","70.7 kPa","26.2 mol %","steady burning period while the fan was on","300","s","exact","flight-orbit","The sample burned steadily for the initial 300 seconds while the fan was on.")
add(S45,"Text discussing Figures 5 and 6","Cygnus cargo spacecraft (in orbit), Saffire V-3",MG,"one-sided PMMA","18 cm long","concurrent","20 cm/s, then fan off","71.3 kPa","25.4 mol %","response when fan turned off","extinguished immediately","-","categorical","flight-orbit","when the fan was turned off in Saffire V-3 and V-4, the sample extinguished immediately")
add(S45,"Text discussing Figures 5 and 6","Cygnus cargo spacecraft (in orbit), Saffire V-4",MG,"structured PMMA","20 cm long","opposed","20 cm/s, then fan off","72.6 kPa","25.7 mol %","response when fan turned off","extinguished immediately","-","categorical","flight-orbit","when the fan was turned off in Saffire V-3 and V-4, the sample extinguished immediately")
add(S45,"Text discussing Figure 4 (Saffire IV sample 2)","Cygnus cargo spacecraft (in orbit), Saffire IV-2",MG,"two-sided PMMA","18 cm long","concurrent","20 cm/s","100.0 kPa","22.0 mol %","extinguishment behaviour","delayed extinguishment","-","categorical","flight-orbit","Delayed extinguishment was also seen on Saffire IV, sample 2 (Figure 4).")
# ---------------- FM2 poster ----------------
F = "fm2_poster_2024"; FM = "FM2 on a lunar lander (planned)"
for d in ("upward","downward"):
    add(F,"Poster, Introduction",FM,"lunar (on the Moon)","SIBAL fabric (cotton/fiberglass blend)",NS,d,NS,"14.7 psia","21% (air)","planned burn","no result yet","-","categorical","planned","two SIBAL fabrics (cotton/fiberglass blend) which will be burned in air")
    add(F,"Poster, Introduction",FM,"lunar (on the Moon)","PMMA (acrylic) rod","4 mm diameter rod",d,NS,"8.2 psia","34%","planned burn","no result yet","-","categorical","planned","two acrylic rods which will be burned in Normoxic Space Exploration Atmospheres (SEA)")
add(F,"Poster, Introduction","lunar-gravity centrifuge and parabolic flight","lunar (simulated)","SIBAL fabric (cotton/fiberglass blend)",NS,"downward",NS,NS,"air","burning behaviour","burns (only downward)","-","categorical","aircraft","SIBAL fabric has been found to only burn downward in air in lunar gravity (via Lunar gravity centrifuge and parabolic flight)")
add(F,"Poster, Introduction","ground","1 g","SIBAL fabric (cotton/fiberglass blend)",NS,"downward",NS,NS,"air","burning behaviour","extinguishes immediately after ignition","-","categorical","ground","where on Earth's gravity it extinguishes immediately after ignition")
# ---------------- BASS-II poster ----------------
B = "bass2_poster_2014"; ISS = "ISS Microgravity Science Glovebox (BASS-II)"; MGI = "microgravity (ISS)"
add(B,"Olson panel, Status","ground","1 g","PMMA rod","1/4 inch diameter rod",NS,NS,NS,"varied","blowoff limit oxygen","16","%","exact","ground","The 1g blowoff for the 1⁄4” rod is at 16% oxygen")
add(B,"Olson panel, Status",ISS,MGI,"PMMA rod","1/4 inch diameter rod","concurrent (stagnation point)",NS,NS,"varied","lowest oxygen with steady spreading","13.6","%","exact","flight-orbit","we obtained steady spreading at 13.6% oxygen in BASS-II")
add(B,"Olson panel, Status","ISS BASS-II vs ground","microgravity vs 1 g","PMMA rod","1/4 inch diameter rod",NS,NS,NS,"varied","oxygen margin of safety","-2.4","% O2","exact","mixed","negative Oxygen Margin of Safety of 2.4% O2")
add(B,"Olson panel, Status",ISS,MGI,"PMMA rods",NS,"concurrent (stagnation point)",NS,NS,NS,"number of rods burned","24","-","exact","flight-orbit","24 plastic rods (PMMA, polymethyl methacrylate) were burned in concurrent (stagnation point) flow")
add(B,"Bhattacharjee panel (radiative quenching vs blow off)",ISS,MGI,"PMMA sheet","0.1 mm thick","opposed","varied",NS,NS,"flow speed below which radiative quenching occurs","2","cm/s","upper bound","flight-orbit","radiative quenching when flow velocity goes below 2 cm/s")
add(B,"Bhattacharjee panel (radiative quenching vs blow off)",ISS,MGI,"PMMA sheet","0.1 mm thick","opposed","varied",NS,NS,"flow speed near blow-off extinction","40","cm/s","approximate","flight-orbit","Flame nearing blow off extinction as the flow velocity crosses 40 cm/s.")
add(B,"Bhattacharjee panel, Status",ISS,MGI,"PMMA sheets","1-cm and 2-cm wide; 0.1 to 0.4 mm thick",NS,NS,NS,NS,"test points obtained","22","-","exact","flight-orbit","22 test points obtained with BASS-II experiments.")
add(B,"Miller panel, Status",ISS,MGI,"PMMA sheets","1-cm and 2-cm wide; 1 to 5 mm thick","opposed","varied",NS,"18% to 20% initial","test points obtained","20","-","exact","flight-orbit","20 test points obtained with BASS-II experiments.")
add(B,"Fernandez-Pello panel, Status",ISS,MGI,"PMMA rods (black and clear)","0.25, 0.375 and 0.5 inch diameter",NS,"0.4 to 4 cm/s",NS,"16% to 21%","unique flame spread rates obtained","54","-","exact","flight-orbit","The total set of experiments yielded 54 unique flame spread rates.")
add(B,"T'ien panel, Status",ISS,MGI,"SIBAL fabric (mostly) and PMMA spherical section",NS,"concurrent",NS,NS,"various","tests conducted","29","-","exact","flight-orbit","29 tests were conducted in total mostly with cotton-fiberglass fabric (SIBAL) and two with a plastic (PMMA; polymethyl methacrylate) spherical section.")
add(B,"T'ien panel, Status",ISS,MGI,"SIBAL fabric","1.2-cm or 2.2-cm wide, 10 cm long","concurrent","reduced (quenching cases)",NS,"various","quenching cases","6","-","exact","flight-orbit","6 quenching cases (reducing flow) and 1 blow-off case (increasing flow, 1.2-cm wide sample).")
add(B,"T'ien panel, quenching image caption",ISS,MGI,"SIBAL fabric","2.2 cm wide","concurrent","5 cm/s at ignition","1 atm","18.7%","flow speed after gradual reduction (quenching sequence)","2.2","cm/s","exact","flight-orbit","Ignited at 5 cm/s flow at right end, then reduced to 2.2 cm/s gradually.")
add(B,"Hardware description","ISS Microgravity Science Glovebox (BASS-II wind tunnel)",MGI,"various solid samples",NS,NS,"up to 40 cm/s",NS,"21% and below","maximum airflow speed of wind tunnel","40","cm/s","upper bound","flight-orbit","could impose airflow speeds up to 40 cm/s")
add(B,"Main variables list",ISS,MGI,"various solid samples",NS,NS,"0 to 55 cm/s",NS,"21% and below","airflow speed range","0 to 55","cm/s","range","flight-orbit","Airflow speed (0 to 55 cm/s)")
# ---------------- Sacksteder 2003 ----------------
K = "sacksteder_2003"; KC = "NASA KC-135 aircraft"
add(K,"Text discussing Figure 1",KC,"partial gravity (0.1, 0.16, 0.38 g)","Kimwipes thin cellulosic tissue","2 cm wide","upward",NS,"27.6 kPa","air","dependence of upward spread rate on gravity","linear","-","categorical","aircraft","The upward burning spread rate varied linearly with gravity level for all pressure environments and sample widths tested")
add(K,"Figure 1 caption and text",KC,"partial gravity (0.1, 0.16, 0.38 g)","Kimwipes thin cellulosic tissue","2 cm wide","downward",NS,"27.6 kPa (4.0 psia)","air","gravity level at which downward spread rate peaks","0.38","g","approximate","aircraft","peaks near the Martian gravity")
add(K,"Text discussing Figure 3 (computed LOI)","numerical model","zero gravity (computed)","thin solid fuel (model)",NS,NS,"forced flow (varied)",NS,NS,"forced flow speed at minimum limiting oxygen index (computed)","5","cm/s","approximate","model","the LOI at zero gravity is non-monotonic and has a minimum around 5 cm/s")
# ---------------- Feier 2001 ----------------
E = "feier_2001"
add(E,"Text discussing Figure 6 (2-cm width flammability limit)","ground","1 g","thin cellulose (Kimwipes)","2 cm wide","upward",NS,"above 0.15 atm","air","outcome above this pressure","entire sample burned","-","categorical","ground","In normal gravity at pressures above 0.15 atm, the entire sample burned")
add(E,"Text discussing Figure 6 (2-cm width flammability limit)","ground","1 g","thin cellulose (Kimwipes)","2 cm wide","upward",NS,"below approximately 0.10 atm","air","outcome below this pressure","extinguished immediately after promoted ignition","-","categorical","ground","for pressures below approximately 0.10 atm, the fuel extinguished immediately after the promoted ignition")
add(E,"Experimental section (aircraft)","NASA KC-135 aircraft","0.10, 0.16 and 0.38 G","thin cellulose (Kimwipes)",NS,"upward",NS,"0.2-0.4 atm","21% O2, balance N2","time within 15% of nominal acceleration","5-20","s","range","aircraft","Times of 5-20 seconds were observed during which acceleration levels remained within 15% of the nominal value.")
add(E,"Experimental section (aircraft)","NASA KC-135 aircraft","0.1, 0.16 and 0.38 G","thin cellulose (Kimwipes)",NS,"upward",NS,"0.2-0.4 atm","21% O2, balance N2","partial-gravity parabolas per flight","10","-","upper bound","aircraft","Up to ten partial gravity parabolas were obtained per flight at nominal accelerations levels of 0.1, 0.16, and 0.38 G.")
# ---------------- verify snippets & write ----------------
cache = {s: norm(open(f"{SRC}/{s}.txt", encoding="utf-8").read()) for s in TITLES}
bad = []
for i, r in enumerate(rows, 1):
    r["row_id"] = f"R{i:03d}"
    r["source_title"] = TITLES[r["source_id"]]
    if norm(r["snippet"]) not in cache[r["source_id"]]:
        bad.append((r["row_id"], r["source_id"], r["snippet"][:80]))
print("rows", len(rows), "| snippets not found:", len(bad))
for b in bad: print("  MISSING", b)
from collections import Counter
print(Counter(r["source_id"] for r in rows))
FIELDS = ["row_id","source_id","source_title","locator","platform","gravity","material","geometry","direction","flow","pressure","oxygen","measurement","value","unit","qualifier","evidence_tier","snippet"]
with open("ledger_v1.csv","w",newline="",encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); [w.writerow({k:r[k] for k in FIELDS}) for r in rows]
json.dump(rows, open("ledger_v1.json","w"), indent=1, ensure_ascii=False)

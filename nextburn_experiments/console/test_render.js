// Checks the console's render functions against the data embedded in index.html (no browser needed).
// Usage: node console/test_render.js [path/to/index.html]
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const file = process.argv[2] || path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(file, "utf8");
const grab = (id) => { const m = new RegExp('<script[^>]*id="' + id + '"[^>]*>([\\s\\S]*?)</script>').exec(html); if (!m) throw new Error("missing script " + id); return m[1]; };
const D = JSON.parse(grab("nb-data")), IM = JSON.parse(grab("nb-images"));
const ctxVm = { console }; vm.createContext(ctxVm);
vm.runInContext(grab("nb-app") + "\nthis.NBR = NBR;", ctxVm);
const NBR = ctxVm.NBR;
let fails = 0;
const ok = (cond, msg) => { if (!cond) { fails++; console.log("FAIL " + msg); } else console.log("PASS " + msg); };
const bad = (s) => /undefined|NaN|\[object Object\]/.exec(s);
const ctxStatic = { live: false, repo: "", img: (k) => IM[k] || "", link: (p) => p };
const ctxLive = { live: true, repo: "https://github.com/example/nextburn", img: (k) => (D.image_paths[k] || ""), link: (p) => p };
const st = NBR.initialState(D);
for (const tab of NBR.TABS) {
  for (const [name, c] of [["static", ctxStatic], ["live", ctxLive]]) {
    const out = NBR.renderTab(tab, D, st, c);
    const b = bad(out.replace(/data:image\/png;base64,[A-Za-z0-9+/=]+/g, ""));
    ok(out.length > 300 && !b, `${tab} (${name}) renders ${out.length} chars` + (b ? ` but contains "${b[0]}" near: ${out.slice(Math.max(0, b.index - 160), b.index + 40)}` : ""));
  }
}
const ov = NBR.renderTab("overview", D, st, ctxStatic);
ok(ov.includes(">313<"), "overview shows 313 test points");
ok(ov.includes("45.3%"), "overview shows the top test's 45.3% reduction");
ok(ov.includes("05e2f02efcd6"), "overview shows the FM2 hash prefix");
const fm = NBR.renderTab("fm2", D, st, ctxStatic);
ok(fm.includes("05e2f02efcd6487f758b40a543ac24e26a01ad81b58e34bb538c8054a5978248"), "FM2 tab shows the full published hash");
ok((fm.match(/<tr>/g) || []).length >= 4, "FM2 tab lists the burns");
const ex = NBR.renderTab("experiments", D, st, ctxStatic);
ok(ex.includes("97.2%") && ex.includes("NOT SATISFACTORY"), "Experiment 1 shown as 97.2% and failed");
ok((ex.match(/<img /g) || []).length === 6, "six experiment charts embedded (Experiments 2 to 7)");
// coverage with a selected bin
st.cov.family = "thin_fabric"; st.cov.bin = "thin_fabric|micro|19.5-22.5|13.5-15.5";
const cv = NBR.renderTab("coverage", D, st, ctxStatic);
ok(cv.includes("Tests in the bin") && !bad(cv), "coverage bin detail renders");
const lunar = D.coverage.families.thin_fabric.summary_by_gravity.lunar;
ok(cv.includes(`${lunar.tested} tested, ${lunar.nearby} nearby, ${lunar.none} none`), "coverage caption matches Step 3 counts for the Moon");
// boundary what-if
const sh = NBR.panelShares(D, NBR.defaultThr(D));
console.log(`INFO what-if at model settings: ${sh.cells - sh.diff} of ${sh.cells} cells agree; declined share what-if ${sh.whatif.toFixed(4)}, model ${sh.model.toFixed(4)}, step4 ${D.boundary.grid_decline_share.toFixed(4)}`);
ok(Math.abs(sh.model - D.boundary.grid_decline_share) < 1e-9, "exported decline flags reproduce the Step 4 decline share");
ok(sh.diff <= 10, "what-if agrees with the model except at threshold cells");
st.bd.cell = [10, 12];
ok(!bad(NBR.renderBoundaryOut(D, st)), "boundary cell detail renders");
const loose = NBR.panelShares(D, { support: 3, width: 1, conflict: 0 });
ok(loose.whatif < sh.whatif, "loosening the decline rule answers more cells");
// ledger
ok(NBR.ledgerRows(D, { q: "" }).length === D.ledger.length, "ledger unfiltered = all rows");
ok(NBR.ledgerRows(D, { family: "thin_fabric", use: "model" }).every((r) => r.family === "thin_fabric"), "ledger filters by family");
st.lg = { q: "TP042", page: 0, open: "TP042" };
const lo = NBR.renderLedgerOut(D, st);
ok(lo.includes("ntrs.nasa.gov") && lo.includes("of 1 matching") && lo.includes("TP042"), "ledger search opens TP042 with its NTRS link");
const csv = NBR.ledgerCsv(NBR.ledgerRows(D, { q: "SIBAL" }));
ok(csv.split("\n")[0].startsWith("tp_id,") && csv.length > 100, "ledger CSV export");
// settings
const key = "config/coverage.json|default_o2_pts";
st.set.edits = { [key]: "4" };
const ch = NBR.fileChanges(D, st.set.edits, "config/coverage.json");
ok(ch.changes.length === 1 && ch.changes[0].value === 4 && ch.errors.length === 0, "settings change collected");
const upd = NBR.updatedFile(D, "config/coverage.json", ch.changes);
ok(upd.default_o2_pts === 4 && D.settings.files["config/coverage.json"].default_o2_pts !== 4, "updated file has the change, original untouched");
st.set.edits = { "config/weights.json|oxygen_exponent": "-1", "config/facilities.json|facilities[id=iss_sofie].available": "false" };
const ch2 = NBR.fileChanges(D, st.set.edits, "config/weights.json");
ok(ch2.errors.length === 1, "out-of-range value refused");
const ch3 = NBR.fileChanges(D, st.set.edits, "config/facilities.json");
ok(ch3.changes.length === 1 && ch3.changes[0].value === false, "facility switch collected");
const fu = NBR.updatedFile(D, "config/facilities.json", ch3.changes);
ok(NBR.getPath(fu, "facilities[id=iss_sofie].available") === false, "path syntax with [id=...] works");
const body = NBR.issueBody(NBR.changeRequest(D, "config/facilities.json", ch3.changes, "2026-11-16T00:00:00Z"));
ok(body.includes("```json") && body.includes("facilities[id=iss_sofie].available"), "GitHub issue body has the change request");
ok(!bad(NBR.renderTab("settings", D, st, ctxStatic)) && !bad(NBR.renderTab("settings", D, st, ctxLive)), "settings with pending edits render");
// runs, live, with a job and history
st.runs = { job: { id: "x", label: "Regression tests", status: "ok", started_utc: "2026-11-16T01:00:00+00:00", finished_utc: "2026-11-16T01:00:01+00:00", log_tail: "PASS" }, history: { changes: [{ time_utc: "2026-11-16T01:00:00+00:00", file: "config/coverage.json", changes: [{ path: "default_o2_pts", old: 2, new: 4 }], backup: "b1" }], runs: [{ started_utc: "2026-11-16T01:00:00+00:00", label: "Regression tests", status: "ok", seconds: 0.4 }] }, msg: "" };
ok(!bad(NBR.renderTab("runs", D, st, ctxLive)), "runs tab with job and history renders");
console.log(fails ? `\n${fails} check(s) failed` : "\nAll console render checks passed");
process.exit(fails ? 1 : 0);

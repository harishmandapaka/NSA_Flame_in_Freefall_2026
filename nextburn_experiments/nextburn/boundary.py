"""Step 4: a flammability boundary with uncertainty, and a rule for declining to answer.

Bayesian logistic regression for P(sustained flame) against oxygen, pressure and gravity (plus flame direction and a
material offset), fitted by Metropolis sampling with numpy only. Observations whose pressure or direction is not stated
enter with their likelihood averaged over the plausible values, so no single value is assumed.
"""
import json
import math
import os

import numpy as np
from scipy.optimize import minimize

from . import ingest

CFG = json.load(open(os.path.join(ingest.CONFIG, "boundary_model.json")))
FEATS = ["intercept", "o2", "lnp", "micro", "g", "g2", "dir", "dir_g", "dir_g2"]
NB = len(FEATS)


def features(o2, p_kpa, g, d):
    o2, p, g, d = (np.asarray(x, float) for x in (o2, p_kpa, g, d))
    micro = (g < 0.01).astype(float)
    return np.stack([np.ones_like(o2), (o2 - 21.0) / 5.0, np.log2(p / 101.325), micro, g, g ** 2, d, d * g, d * g ** 2], axis=-1)


def _variants(ob):
    o2s = list(np.linspace(ob["o2"][0], ob["o2"][1], 3)) if isinstance(ob["o2"], list) else [ob["o2"]]
    ps = list(np.exp(np.linspace(math.log(ob["p_kpa"][0]), math.log(ob["p_kpa"][1]), 5))) if isinstance(ob["p_kpa"], list) else [ob["p_kpa"]]
    ds = [ob["dir"]] if ob["dir"] in (1, -1) else [1, -1]
    return [(o, p, ob["g"], d) for o in o2s for p in ps for d in ds]


def split_rhat(ch):
    c, n, k = ch.shape
    h = n // 2
    s = np.concatenate([ch[:, :h], ch[:, h:2 * h]], axis=0)
    m, v = s.mean(axis=1), s.var(axis=1, ddof=1)
    W, B = v.mean(axis=0), h * m.var(axis=0, ddof=1)
    return np.sqrt(((h - 1) / h * W + B / h) / W)


class BoundaryModel:
    def __init__(self, family, obs, cfg=CFG):
        self.family, self.obs, self.cfg = family, obs, cfg
        self.materials = sorted({o["material"] for o in obs})
        rows, owner = [], []
        for i, o in enumerate(obs):
            for v in _variants(o):
                rows.append(v)
                owner.append(i)
        v = np.array(rows)
        self.X = features(v[:, 0], v[:, 1], v[:, 2], v[:, 3])
        self.owner = np.array(owner)
        self.counts = np.bincount(self.owner, minlength=len(obs)).astype(float)
        self.y = np.array([o["y"] for o in obs], float)
        self.mat = np.array([self.materials.index(o["material"]) for o in obs])
        pri = cfg["priors"]
        self.mu = np.array([pri[f]["mean"] for f in FEATS] + [0.0] * len(self.materials))
        self.sd = np.array([pri[f]["sd"] for f in FEATS] + [cfg["material_sd"]] * len(self.materials))
        self.dim = len(self.mu)

    def _p_obs(self, th):
        eta = self.X @ th[:NB] + th[NB:][self.mat[self.owner]]
        pv = 1.0 / (1.0 + np.exp(-eta))
        return np.bincount(self.owner, weights=pv, minlength=len(self.y)) / self.counts

    def logpost(self, th):
        p = np.clip(self._p_obs(th), 1e-12, 1 - 1e-12)
        return float(np.sum(self.y * np.log(p) + (1 - self.y) * np.log(1 - p)) - 0.5 * np.sum(((th - self.mu) / self.sd) ** 2))

    def _chain(self, th, L, n, rng, burn=0, thin=1):
        lp, keep, acc = self.logpost(th), [], 0
        for t in range(n):
            prop = th + L @ rng.standard_normal(self.dim)
            lpp = self.logpost(prop)
            if math.log(rng.random()) < lpp - lp:
                th, lp, acc = prop, lpp, acc + 1
            if t >= burn and (t - burn) % thin == 0:
                keep.append(th.copy())
        return th, np.array(keep), acc / n

    def fit(self, seed=None):
        mc = self.cfg["mcmc"]
        rng = np.random.default_rng(mc["seed"] if seed is None else seed)
        res = minimize(lambda th: -self.logpost(th), self.mu.copy(), method="BFGS")
        cov = np.array(res.hess_inv)
        cov = (cov + cov.T) / 2
        try:
            L0 = np.linalg.cholesky(cov + 1e-8 * np.eye(self.dim))
        except np.linalg.LinAlgError:
            L0 = np.diag(self.sd) * 0.3
        scale = 2.38 / math.sqrt(self.dim)
        for _ in range(8):
            _, _, a = self._chain(res.x.copy(), L0 * scale, 1500, rng)
            if a < 0.15:
                scale *= 0.6
            elif a > 0.40:
                scale *= 1.5
            else:
                break
        chains, accs = [], []
        for c in range(mc["chains"]):
            start = res.x + L0 @ rng.standard_normal(self.dim) * 0.5
            _, keep, a = self._chain(start, L0 * scale, mc["iterations"], rng, mc["burn_in"], mc["thin"])
            chains.append(keep)
            accs.append(a)
        self.chains = np.array(chains)
        self.samples = self.chains.reshape(-1, self.dim)
        self.rhat = split_rhat(self.chains)
        self.acceptance = accs
        self.map = res.x
        return self

    def prob(self, X, material=None, rng=None):
        eta = self.samples[:, :NB] @ np.atleast_2d(X).T
        if material == "new":
            rng = rng or np.random.default_rng(7)
            eta = eta + rng.normal(0.0, self.cfg["material_sd"], size=(eta.shape[0], 1))
        elif material is not None:
            eta = eta + self.samples[:, NB + self.materials.index(material)][:, None]
        return 1.0 / (1.0 + np.exp(-eta))

    def support(self, o2, p_kpa, g, d):
        """Distance from each query to the nearest observation of this family (same units as the decline rule)."""
        sc = self.cfg["decline"]["scales"]
        o2, p, g, d = (np.atleast_1d(np.asarray(x, float)) for x in (o2, p_kpa, g, d))
        best, idx = np.full(o2.shape, np.inf), np.zeros(o2.shape, int)
        self._last_dist = np.zeros((len(self.obs),) + o2.shape)
        for k, ob in enumerate(self.obs):
            olo, ohi = (ob["o2"][0], ob["o2"][1]) if isinstance(ob["o2"], list) else (ob["o2"], ob["o2"])
            plo, phi = (ob["p_kpa"][0], ob["p_kpa"][1]) if isinstance(ob["p_kpa"], list) else (ob["p_kpa"], ob["p_kpa"])
            dO = (o2 - np.clip(o2, olo, ohi)) / sc["o2_pts"]
            dP = (np.log(p) - np.clip(np.log(p), math.log(plo), math.log(phi))) / math.log(1 + sc["p_frac"])
            dG = (g - ob["g"]) / sc["g"]
            dD = np.where((ob["dir"] == 0) | (d == 0) | (d == ob["dir"]), 0.0, sc["direction_mismatch"])
            dist = np.sqrt(dO ** 2 + dP ** 2 + dG ** 2 + dD ** 2)
            self._last_dist[k] = dist
            better = dist < best
            best, idx = np.where(better, dist, best), np.where(better, k, idx)
        return best, idx

    def answer(self, o2, p_kpa, g, d, material=None):
        X = features(o2, p_kpa, g, d)
        P = self.prob(X, material)
        mean, lo, hi = P.mean(0), np.quantile(P, 0.05, axis=0), np.quantile(P, 0.95, axis=0)
        dist, idx = self.support(o2, p_kpa, g, d)
        dc = self.cfg["decline"]
        out = []
        for i in range(len(mean)):
            reasons = []
            if dist[i] > dc["support_max_distance"]:
                reasons.append("no %s test within distance %.1f (nearest %.2f: %s)" % (self.family.replace("_", " "), dc["support_max_distance"], dist[i], self.obs[idx[i]]["label"]))
            if hi[i] - lo[i] > dc["ci90_max_width"]:
                reasons.append("90%% interval %.2f to %.2f is wider than %.1f" % (lo[i], hi[i], dc["ci90_max_width"]))
            call = 1 if mean[i] >= 0.5 else 0
            clash = [k for k in range(len(self.obs)) if self._last_dist[k][i] <= dc.get("conflict_radius", 0.0) and self.obs[k]["y"] != call]
            if clash:
                reasons.append("the model's answer contradicts %s at distance %.2f (%s)" % (self.obs[clash[0]]["label"], self._last_dist[clash[0]][i], self.obs[clash[0]]["outcome"]))
            decision = "declined" if reasons else ("sustains" if mean[i] >= 0.5 else "does not sustain")
            n = self.obs[idx[i]]
            out.append({"p_mean": float(mean[i]), "p_lo90": float(lo[i]), "p_hi90": float(hi[i]), "support_distance": float(dist[i]),
                        "nearest_obs": n["obs_id"], "nearest_label": n["label"], "nearest_outcome": n["outcome"], "decision": decision, "reasons": reasons})
        return out

    def loo(self):
        """Importance-sampling leave-one-out: how well each observation is predicted by the others."""
        S = self.samples
        eta = S[:, :NB] @ self.X.T + S[:, NB:][:, self.mat[self.owner]]
        pv = 1 / (1 + np.exp(-eta))
        P = np.stack([pv[:, self.owner == i].mean(1) for i in range(len(self.y))], axis=1)
        lik = np.where(self.y == 1, P, 1 - P)
        w = 1 / np.clip(lik, 1e-12, None)
        p_loo = (w * P).sum(0) / w.sum(0)
        rows = [{"obs_id": o["obs_id"], "label": o["label"], "material": o["material"], "y": int(o["y"]), "p_in_sample": float(P[:, i].mean()),
                 "p_leave_one_out": float(p_loo[i]), "correct_loo": bool((p_loo[i] >= 0.5) == (o["y"] == 1))} for i, o in enumerate(self.obs)]
        return {"brier_loo": float(np.mean((p_loo - self.y) ** 2)), "accuracy_loo": float(np.mean([r["correct_loo"] for r in rows])),
                "brier_in_sample": float(np.mean((P.mean(0) - self.y) ** 2)), "base_rate": float(self.y.mean()), "rows": rows}

    def summary(self):
        names = FEATS + ["material:" + m for m in self.materials]
        q = np.quantile(self.samples, [0.05, 0.5, 0.95], axis=0)
        return {"family": self.family, "observations": len(self.obs), "sustained": int(self.y.sum()), "not_sustained": int(len(self.y) - self.y.sum()),
                "materials": self.materials, "samples": int(self.samples.shape[0]), "acceptance": [round(a, 3) for a in self.acceptance],
                "max_rhat": float(np.max(self.rhat)),
                "coefficients": [{"name": n, "q05": float(q[0, k]), "median": float(q[1, k]), "q95": float(q[2, k]),
                                  "prior_mean": float(self.mu[k]), "prior_sd": float(self.sd[k]), "rhat": float(self.rhat[k])} for k, n in enumerate(names)]}

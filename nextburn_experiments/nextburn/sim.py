"""Experiment 6 (SIMULATION): test-planner efficiency on simulated extinction boundaries.

Everything in this module is a simulation.  The extinction boundaries are random
U-shaped surfaces of the minimum oxygen concentration that sustains burning (MOC),
anchored only on the published SoFIE-GEL operating ranges (forced flow 0.2-80 cm/s,
oxygen 13-34 %, pressure 0.15-1.1 atm).  They are not NASA data.

Public API (names fixed by the experiment plan):
    make_boundary(seed, dims=2)                      -> (moc_function, true_minimum)
    next_test(strategy, history, model)              -> next test condition
    run_strategy(strategy, boundary, budget, noise)  -> run record (dict)
    tests_to_converge(estimates, true_min, tol)      -> int, or math.inf if never

Coordinates are normalized to [0, 1]: u = position on the log10(flow) axis,
q = position on the pressure axis (linear in atm), r = position on the oxygen axis
(go/no-go tests only).  flow_cm_s(), pressure_atm() and o2_pct() convert to
physical units.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.linalg import LinAlgError, cho_solve, cholesky, solve_triangular
from scipy.optimize import minimize
from scipy.special import log_ndtr

LABEL = "SIMULATION"

FLOW_RANGE_CM_S = (0.2, 80.0)
O2_RANGE_PCT = (13.0, 34.0)
PRESSURE_RANGE_ATM = (0.15, 1.1)
MIN_EXTINCTION_O2_RANGE = (13.0, 14.0)

BUDGET = 40
NOISE_SD = 0.5
TOL = 0.5
KAPPA = 2.0
MATRIX_LEVEL_SETS = {"inset": np.linspace(0.05, 0.95, 6), "endpoints": np.linspace(0.0, 1.0, 6)}
MATRIX_LEVELS = MATRIX_LEVEL_SETS["inset"]
REOPT_EVERY = 5
FIXED_SHUFFLE_SEED = 6

STRATEGIES = ("fixed_matrix", "space_filling", "random", "uncertainty_driven")
VARIANTS = ("two_variable", "one_variable", "go_no_go")
FIXED_ORDERS = ("flow_major", "pressure_high_first", "pressure_low_first", "shuffled")

STRATEGY_LABELS = {
    "fixed_matrix": "Fixed 6x6 test matrix",
    "space_filling": "Space-filling (Halton)",
    "random": "Random",
    "uncertainty_driven": "Uncertainty-driven (lower confidence bound)",
}
FIXED_LABELS = {
    "two_variable": "Fixed 6x6 test matrix (6 flows x 6 pressures)",
    "one_variable": "Fixed sweep (6 flows, repeated low to high)",
    "go_no_go": "Fixed 6x6 test matrix (6 flows x 6 oxygen levels)",
}
FIXED_ORDER_LABELS = {
    "flow_major": "flows low to high; at each flow, pressures low to high (plan prototype order)",
    "pressure_high_first": "highest-pressure row first; flows low to high within each row",
    "pressure_low_first": "lowest-pressure row first; flows low to high within each row",
    "shuffled": f"one fixed random permutation of the 36 cells (seed {FIXED_SHUFFLE_SEED})",
}
FIXED_LEVEL_LABELS = {
    "inset": "levels at 5-95% of each range (plan prototype)",
    "endpoints": "levels spanning each full range, ends included",
}

_LOG_FLOW = (math.log10(FLOW_RANGE_CM_S[0]), math.log10(FLOW_RANGE_CM_S[1]))
_SQRT5 = math.sqrt(5.0)


def strategy_label(strategy, variant="two_variable"):
    if strategy == "fixed_matrix":
        return FIXED_LABELS[variant]
    return STRATEGY_LABELS[strategy]


def flow_cm_s(u):
    """Normalized log-flow position -> forced flow in cm/s."""
    return 10.0 ** (_LOG_FLOW[0] + np.asarray(u, float) * (_LOG_FLOW[1] - _LOG_FLOW[0]))


def pressure_atm(q):
    """Normalized pressure position -> pressure in atm."""
    lo, hi = PRESSURE_RANGE_ATM
    return lo + np.asarray(q, float) * (hi - lo)


def o2_pct(r):
    """Normalized oxygen position -> oxygen in percent."""
    lo, hi = O2_RANGE_PCT
    return lo + np.asarray(r, float) * (hi - lo)


def o2_to_r(o2):
    lo, hi = O2_RANGE_PCT
    return (np.asarray(o2, float) - lo) / (hi - lo)


# --------------------------------------------------------------------------- boundaries
def make_boundary(seed, dims=2):
    """Draw one simulated extinction boundary.

    Returns (moc, true_min).  moc(x) gives the minimum oxygen (%) that sustains burning
    at a normalized condition: x = u (or [u]) for dims=1, x = [u, q] or an (n, 2) array
    for dims=2.  The shape, as a function of lo = 1 - q (0 at 1.1 atm, 1 at 0.15 atm):

        MOC = xmin + rise * ((1 - curv) * lo + curv * lo**2)
              + a_side * (1 + steep * lo) * (u - u0 - shift * lo)**2,  clipped to 13-34 %

    a_side is the quench-side curvature below the optimum flow and the blowoff-side
    curvature above it.  |shift| is capped so MOC rises as pressure falls at every flow
    (nested boundaries), while the flow at the minimum still moves with pressure and the
    U narrows (interaction terms).  The global minimum is xmin, drawn uniformly in
    [13, 14), at u = u0 and 1.1 atm.  dims=1 is exactly the 1.1 atm slice of dims=2 for
    the same seed.
    """
    if dims not in (1, 2):
        raise ValueError("dims must be 1 or 2")
    rng = np.random.default_rng(seed)
    xmin = float(rng.uniform(*MIN_EXTINCTION_O2_RANGE))
    u0 = float(rng.uniform(0.30, 0.70))
    a_quench = float(rng.uniform(20.0, 60.0))
    a_blowoff = float(rng.uniform(8.0, 30.0))
    rise = float(rng.uniform(3.0, 8.0))
    curv = float(rng.uniform(0.0, 0.5))
    steep = float(rng.uniform(0.5, 1.5))
    direction = 1.0 if rng.uniform() < 0.5 else -1.0
    frac = float(rng.uniform(0.3, 1.0))
    a_rel = a_blowoff if direction > 0 else a_quench
    shift_max = math.sqrt(steep * rise * (1.0 - curv) / a_rel) / (1.0 + steep)
    shift = direction * frac * shift_max
    params = dict(xmin=xmin, u0=u0, a_quench=a_quench, a_blowoff=a_blowoff, rise=rise,
                  curv=curv, steep=steep, shift=shift)
    lo_o2, hi_o2 = O2_RANGE_PCT

    def moc(x):
        x = np.asarray(x, float)
        if dims == 1:
            single = x.ndim == 0 or x.size == 1
            u = x.reshape(-1) if x.ndim <= 1 else x[:, 0]
            lo = np.zeros_like(u)
        else:
            single = x.ndim == 1
            x2 = np.atleast_2d(x)
            u, lo = x2[:, 0], 1.0 - x2[:, 1]
        t = u - (u0 + shift * lo)
        a = np.where(t < 0.0, a_quench, a_blowoff) * (1.0 + steep * lo)
        val = xmin + rise * ((1.0 - curv) * lo + curv * lo * lo) + a * t * t
        val = np.clip(val, lo_o2, hi_o2)
        return float(val[0]) if single else val

    moc.params = params
    moc.dims = dims
    moc.seed = seed
    moc.true_min = xmin
    moc.argmin = (u0,) if dims == 1 else (u0, 1.0)
    return moc, xmin


# --------------------------------------------------------------------------- designs
def halton(n, bases, skip=1):
    """First n points of the (unscrambled) Halton sequence, skipping the origin."""
    out = np.empty((n, len(bases)))
    for j, b in enumerate(bases):
        for i in range(n):
            k, f, r = i + skip, 1.0, 0.0
            while k > 0:
                f /= b
                r += f * (k % b)
                k //= b
            out[i, j] = r
    return out


def fixed_matrix(order="flow_major", levels="inset"):
    """6 x 6 matrix of normalized conditions (first axis flow) in a fixed run order."""
    lv = MATRIX_LEVEL_SETS[levels]
    if order == "flow_major":
        pts = [(a, b) for a in lv for b in lv]
    elif order == "pressure_high_first":
        pts = [(a, b) for b in lv[::-1] for a in lv]
    elif order == "pressure_low_first":
        pts = [(a, b) for b in lv for a in lv]
    elif order == "shuffled":
        base = [(a, b) for a in lv for b in lv]
        perm = np.random.default_rng(FIXED_SHUFFLE_SEED).permutation(len(base))
        pts = [base[i] for i in perm]
    else:
        raise ValueError(f"unknown fixed order {order!r}")
    return np.array(pts, float)


@dataclass(frozen=True)
class Variant:
    name: str
    boundary_dims: int
    test_dims: int
    measurement: str        # "limit" (noisy MOC value) or "go_no_go" (burn / no burn)
    n_first: int            # first test count with an estimate (= Halton start of the planner)
    grid: np.ndarray        # estimator / planner grid (GP) or candidate flows (go/no-go)
    halton: np.ndarray
    fixed: np.ndarray
    fixed_order: str
    fixed_levels: str


@lru_cache(maxsize=None)
def make_variant(name, fixed_order="flow_major", budget=BUDGET, fixed_levels="inset"):
    if name == "two_variable":
        g = np.linspace(0.0, 1.0, 41)
        grid = np.array([(a, b) for a in g for b in g])
        return Variant(name, 2, 2, "limit", 5, grid, halton(budget, (2, 3)),
                       fixed_matrix(fixed_order, fixed_levels), fixed_order, fixed_levels)
    if name == "one_variable":
        grid = np.linspace(0.0, 1.0, 201)[:, None]
        return Variant(name, 1, 1, "limit", 4, grid, halton(budget, (2,)),
                       MATRIX_LEVEL_SETS[fixed_levels][:, None].copy(), "flow_ascending", fixed_levels)
    if name == "go_no_go":
        grid = GoNoGoPosterior.U0_GRID[:, None].copy()
        return Variant(name, 1, 2, "go_no_go", 5, grid, halton(budget, (2, 3)),
                       fixed_matrix(fixed_order, fixed_levels), fixed_order, fixed_levels)
    raise ValueError(f"unknown variant {name!r}")


# --------------------------------------------------------------------------- GP model
def _matern52(A, B, ls, sf2):
    D = (A[:, None, :] - B[None, :, :]) / ls
    r = np.sqrt(np.einsum("ijk,ijk->ij", D, D))
    return sf2 * (1.0 + _SQRT5 * r + (5.0 / 3.0) * r * r) * np.exp(-_SQRT5 * r)


class GP:
    """Gaussian-process regression for limit-test data (shared by every strategy).

    Matern-5/2 kernel with one length scale per input, constant mean, outputs
    standardized by their sample mean and s.d. (like scikit-learn normalize_y), and the
    known measurement noise (noise_sd, in O2 points).  Signal variance and length scales
    are fitted by maximum marginal likelihood (L-BFGS-B, bounded, warm start plus a
    default start) only when fit(..., optimize=True); otherwise the last values are kept.
    """

    LOG_SF2_BOUNDS = (math.log(0.05), math.log(20.0))
    LOG_LS_BOUNDS = (math.log(0.05), math.log(2.0))
    JITTER = 1e-8

    def __init__(self, dims, noise_sd=NOISE_SD, grid=None):
        self.dims = dims
        self.noise_sd = noise_sd
        self.grid = grid
        self.theta0 = np.r_[0.0, np.full(dims, math.log(0.3))]
        self.theta = self.theta0.copy()
        self.n_optimizations = 0

    def _nll(self, theta, X, yn, nv):
        sf2 = math.exp(theta[0])
        ls = np.exp(theta[1:])
        D = (X[:, None, :] - X[None, :, :]) / ls
        D2 = D * D
        r = np.sqrt(D2.sum(-1))
        e = np.exp(-_SQRT5 * r)
        Kf = sf2 * (1.0 + _SQRT5 * r + (5.0 / 3.0) * r * r) * e
        n = len(yn)
        K = Kf + (nv + self.JITTER) * np.eye(n)
        try:
            L = cholesky(K, lower=True)
        except LinAlgError:
            return 1e25, np.zeros_like(theta)
        alpha = cho_solve((L, True), yn)
        nll = 0.5 * yn @ alpha + np.log(np.diag(L)).sum() + 0.5 * n * math.log(2.0 * math.pi)
        W = np.outer(alpha, alpha) - cho_solve((L, True), np.eye(n))
        grad = np.empty_like(theta)
        grad[0] = -0.5 * np.sum(W * Kf)
        C = sf2 * (5.0 / 3.0) * (1.0 + _SQRT5 * r) * e
        for i in range(self.dims):
            grad[1 + i] = -0.5 * np.sum(W * C * D2[:, :, i])
        return nll, grad

    def _optimize(self, X, yn, nv):
        bounds = [self.LOG_SF2_BOUNDS] + [self.LOG_LS_BOUNDS] * self.dims
        starts = [self.theta] if np.allclose(self.theta, self.theta0) else [self.theta, self.theta0]
        best = None
        for start in starts:
            res = minimize(self._nll, start, args=(X, yn, nv), jac=True, method="L-BFGS-B",
                           bounds=bounds, options={"maxiter": 60})
            if np.isfinite(res.fun) and (best is None or res.fun < best.fun):
                best = res
        if best is not None:
            lo = np.array([b[0] for b in bounds])
            hi = np.array([b[1] for b in bounds])
            self.theta = np.clip(best.x, lo, hi)
        self.n_optimizations += 1

    def fit(self, X, y, optimize=False):
        X = np.asarray(X, float).reshape(len(X), -1)
        y = np.asarray(y, float)
        self.ym = float(y.mean())
        sd = float(y.std())
        self.ys = sd if sd > 1e-9 else 1.0
        yn = (y - self.ym) / self.ys
        nv = (self.noise_sd / self.ys) ** 2
        if optimize:
            self._optimize(X, yn, nv)
        self.sf2 = math.exp(self.theta[0])
        self.ls = np.exp(self.theta[1:])
        K = _matern52(X, X, self.ls, self.sf2) + (nv + self.JITTER) * np.eye(len(X))
        self.L = cholesky(K, lower=True)
        self.alpha = cho_solve((self.L, True), yn)
        self.X = X
        return self

    def predict(self, Xs, return_std=False):
        Ks = _matern52(np.asarray(Xs, float), self.X, self.ls, self.sf2)
        mu = Ks @ self.alpha * self.ys + self.ym
        if not return_std:
            return mu
        v = solve_triangular(self.L, Ks.T, lower=True, check_finite=False)
        var = self.sf2 - np.einsum("ij,ij->j", v, v)
        return mu, np.sqrt(np.maximum(var, 0.0)) * self.ys

    def estimate(self):
        """Estimated minimum extinction oxygen: minimum of the posterior mean on the grid."""
        return float(self.predict(self.grid).min())

    def pick(self, kappa=KAPPA):
        """Lower-confidence-bound choice: grid point minimizing mean - kappa * s.d."""
        mu, sd = self.predict(self.grid, return_std=True)
        return self.grid[int(np.argmin(mu - kappa * sd))].copy()


# --------------------------------------------------------------------------- go/no-go model
class GoNoGoPosterior:
    """Bayesian grid posterior for burn / no-burn tests (shared by every strategy).

    Model: MOC(u) = min(xmin + a_side * (u - u0)^2, 34) with a_side = aL below u0 and
    aR above it; P(burn at O2) = Phi((O2 - MOC(u)) / noise_sd).  Uniform prior over the
    parameter grid below (much wider than the [13, 14) range the truth is drawn from).
    The estimate is the posterior mean of xmin, the minimum extinction oxygen.
    The posterior is kept in probability space and renormalized after every test; the
    probit likelihood is read from a fine lookup table (step 0.002 O2 points).
    """

    XMIN_GRID = np.round(np.arange(11.0, 22.0 + 1e-9, 0.1), 2)
    U0_GRID = np.linspace(0.0, 1.0, 33)
    A_GRID = np.geomspace(5.0, 120.0, 7)
    MASS_FLOOR = 1e-12
    _V_MAX = 40.0
    _V_STEP = 0.002

    def __init__(self, noise_sd=NOISE_SD, flow_candidates=None):
        u0, al, ar = np.meshgrid(self.U0_GRID, self.A_GRID, self.A_GRID, indexing="ij")
        self.u0, self.al, self.ar = u0.ravel(), al.ravel(), ar.ravel()
        self.x = self.XMIN_GRID
        self.w = np.full((self.x.size, self.u0.size), 1.0 / (self.x.size * self.u0.size))
        self.noise_sd = noise_sd
        cand = self.U0_GRID if flow_candidates is None else np.asarray(flow_candidates, float)
        self.cand = cand.reshape(-1)
        self.d_cand = np.stack([self._shape_term(u) for u in self.cand])
        vt = np.arange(-self._V_MAX, self._V_MAX + self._V_STEP / 2, self._V_STEP)
        self._tab = np.exp(log_ndtr(vt / noise_sd))

    def _shape_term(self, u):
        t = u - self.u0
        return np.where(t < 0.0, self.al, self.ar) * t * t

    def update(self, u, o2, burn):
        moc = np.minimum(self.x[:, None] + self._shape_term(float(u))[None, :], O2_RANGE_PCT[1])
        v = (o2 - moc) if burn else (moc - o2)
        idx = np.rint((v + self._V_MAX) / self._V_STEP).astype(np.intp)
        np.clip(idx, 0, self._tab.size - 1, out=idx)
        self.w *= self._tab[idx]
        self.w /= self.w.sum()

    def weights(self):
        return self.w

    def estimate(self):
        return float(self.w.sum(axis=1) @ self.x)

    def boundary_moments(self):
        """Posterior mean and s.d. of the (clipped) MOC at each candidate flow.

        Shapes whose total posterior mass is below MASS_FLOOR are skipped.
        """
        active = np.flatnonzero(self.w.sum(axis=0) > self.MASS_FLOOR)
        w = self.w[:, active]
        x = self.x
        top = O2_RANGE_PCT[1]
        zero = np.zeros((1, w.shape[1]))
        c0 = np.vstack([zero, np.cumsum(w, axis=0)])
        c1 = np.vstack([zero, np.cumsum(w * x[:, None], axis=0)])
        c2 = np.vstack([zero, np.cumsum(w * (x * x)[:, None], axis=0)])
        d = self.d_cand[:, active]
        k = np.searchsorted(x, top - d, side="left")
        cols = np.arange(w.shape[1])[None, :]
        s0, s1, s2 = c0[k, cols], c1[k, cols], c2[k, cols]
        tot = c0[-1][None, :]
        e1 = (s1 + d * s0 + top * (tot - s0)).sum(axis=1)
        e2 = (s2 + 2.0 * d * s1 + d * d * s0 + top * top * (tot - s0)).sum(axis=1)
        return e1, np.sqrt(np.maximum(e2 - e1 * e1, 0.0))

    def pick(self, kappa=KAPPA):
        """Flow with the lowest lower bound on MOC; oxygen at the posterior-mean boundary."""
        mean, sd = self.boundary_moments()
        c = int(np.argmin(mean - kappa * sd))
        o2 = float(np.clip(mean[c], *O2_RANGE_PCT))
        return np.array([self.cand[c], float(o2_to_r(o2))])


# --------------------------------------------------------------------------- planner loop
def next_test(strategy, history, model, *, variant="two_variable", rng=None, kappa=KAPPA):
    """Next normalized test condition for a strategy, given past tests and the model.

    history: list of (condition, outcome) pairs so far; model: the fitted shared model
    (GP or GoNoGoPosterior) or None before the first fit.  The fixed matrix cycles
    through its cells in order; space-filling takes the next Halton point; random draws
    uniformly with rng; uncertainty-driven starts with the first Halton points and then
    picks the lower-confidence-bound condition from the model.
    """
    spec = variant if isinstance(variant, Variant) else make_variant(variant)
    n = len(history)
    if strategy == "fixed_matrix":
        return spec.fixed[n % len(spec.fixed)].copy()
    if strategy == "space_filling":
        return spec.halton[n].copy()
    if strategy == "random":
        if rng is None:
            raise ValueError("random strategy needs an rng")
        return rng.uniform(0.0, 1.0, spec.test_dims)
    if strategy == "uncertainty_driven":
        if model is None or n < spec.n_first:
            return spec.halton[n].copy()
        return model.pick(kappa)
    raise ValueError(f"unknown strategy {strategy!r}")


def tests_to_converge(estimates, true_min, tol=TOL):
    """First test count after which every later estimate is within tol of true_min.

    Estimates that are missing (NaN, before the first fit) count as outside the
    tolerance.  Returns math.inf when the last estimate is outside (never converged).
    """
    est = np.asarray(estimates, float)
    ok = np.isfinite(est) & (np.abs(est - true_min) <= tol)
    if ok.size == 0 or not ok[-1]:
        return math.inf
    bad = np.flatnonzero(~ok)
    return int(bad[-1] + 2) if bad.size else 1


def run_strategy(strategy, boundary, budget=BUDGET, noise=NOISE_SD, *, variant="two_variable",
                 seed=0, noise_draws=None, fixed_order="flow_major", fixed_levels="inset", tol=TOL,
                 kappa=KAPPA, keep_history=False):
    """Run one strategy on one boundary for a fixed test budget.

    boundary: (moc_function, true_min) from make_boundary.  noise: s.d. of the limit-test
    reading (or of the burn threshold for go/no-go), in O2 points.  noise_draws: optional
    standard-normal draws (one per test) so that every strategy sees the same noise
    sequence on a boundary.  seed: seeds the random strategy's choices.
    """
    f, true_min = boundary
    spec = (variant if isinstance(variant, Variant)
            else make_variant(variant, fixed_order, max(budget, BUDGET), fixed_levels))
    rng = np.random.default_rng(seed)
    if noise_draws is None:
        noise_draws = np.random.default_rng([*np.atleast_1d(seed).tolist(), 1]).standard_normal(budget)
    if len(noise_draws) < budget:
        raise ValueError("need one noise draw per test")
    if spec.measurement == "limit":
        shared = GP(spec.test_dims, noise, spec.grid)
    else:
        shared = GoNoGoPosterior(noise, spec.grid)
    history, estimates, model = [], [], None
    for n in range(budget):
        x = np.asarray(next_test(strategy, history, model, variant=spec, rng=rng, kappa=kappa), float)
        eps = noise * float(noise_draws[n])
        if spec.measurement == "limit":
            y = float(f(x if spec.boundary_dims == 2 else x[0])) + eps
        else:
            o2 = float(o2_pct(x[1]))
            y = bool(o2 > float(f(x[0])) + eps)
            shared.update(x[0], o2, y)
        history.append((x, y))
        k = n + 1
        if k >= spec.n_first:
            if spec.measurement == "limit":
                X = np.array([h[0] for h in history])
                Y = np.array([h[1] for h in history])
                shared.fit(X, Y, optimize=(k == spec.n_first or k % REOPT_EVERY == 0))
            model = shared
            estimates.append(shared.estimate())
        else:
            estimates.append(math.nan)
    out = {
        "strategy": strategy,
        "variant": spec.name,
        "fixed_order": spec.fixed_order if strategy == "fixed_matrix" else "",
        "fixed_levels": spec.fixed_levels if strategy == "fixed_matrix" else "",
        "true_min": float(true_min),
        "estimates": estimates,
        "final_estimate": float(estimates[-1]),
        "tests_to_converge": tests_to_converge(estimates, true_min, tol),
    }
    if keep_history:
        out["history"] = history
    return out


# --------------------------------------------------------------------------- summaries
def quantile(values, p):
    """Linear-interpolation quantile (numpy default) that treats inf (failure) safely."""
    v = np.sort(np.asarray(values, float))
    if v.size == 0:
        return math.nan
    h = (v.size - 1) * p
    lo, hi = int(math.floor(h)), int(math.ceil(h))
    if lo == hi or h == lo:
        return float(v[lo])
    if not np.isfinite(v[hi]):
        return math.inf
    return float(v[lo] + (v[hi] - v[lo]) * (h - lo))


def summarize(values):
    """Success rate, median, 80th percentile (failures = inf) and mean over successes."""
    a = np.asarray(values, float)
    fin = a[np.isfinite(a)]
    return {
        "n_runs": int(a.size),
        "n_success": int(fin.size),
        "success_rate": float(fin.size / a.size) if a.size else math.nan,
        "median_tests": quantile(a, 0.5),
        "p80_tests": quantile(a, 0.8),
        "mean_tests": float(fin.mean()) if fin.size else math.inf,
    }

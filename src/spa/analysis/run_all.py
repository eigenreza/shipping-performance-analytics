"""Analysis questions 1 to 5 (methods fixed in spa.analysis.plan).

Writes results/analysis/*.json, results/figures/*.png and the model
parameters table used by the Power BI scenario measures.
"""

from __future__ import annotations

import json
import math

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from spa.analysis import plan
from spa.analysis.scenario import ets_cost_saved, extra_days, saved_share
from spa.paths import EXPORTS, RESULTS, WAREHOUSE

OUT = RESULTS / "analysis"
FIG = RESULTS / "figures"


def _q(con, sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def pct_interval(draws: np.ndarray) -> tuple[float, float]:
    a = (1 - plan.CI) / 2
    return float(np.nanquantile(draws, a)), float(np.nanquantile(draws, 1 - a))


def r(x, n=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), n)


# ---------------------------------------------------------------- Q1 models
class Panel:
    """Arrays for fast estimation and cluster bootstrap over ships."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.y = np.log(self.df["co2_kg_per_nm"].to_numpy())
        self.x = np.log(self.df["avg_speed_kn"].to_numpy())
        self.years = pd.get_dummies(self.df["reporting_year"], drop_first=True, dtype=float).to_numpy()
        codes, self.ships = pd.factorize(self.df["ship_key"])
        self.rows_by_ship = [np.flatnonzero(codes == i) for i in range(len(self.ships))]
        self.codes = codes
        self.Xc, self.names = cross_design(self.df)

    def within(self, rows: np.ndarray, clusters: np.ndarray) -> float:
        X = np.column_stack([self.x[rows], self.years[rows]])
        y = self.y[rows]
        n_c = clusters.max() + 1
        cnt = np.bincount(clusters, minlength=n_c)

        def demean(a):
            if a.ndim == 1:
                return a - (np.bincount(clusters, a, n_c) / cnt)[clusters]
            return np.column_stack([demean(a[:, j]) for j in range(a.shape[1])])

        beta, *_ = np.linalg.lstsq(demean(X), demean(y), rcond=None)
        return float(beta[0])

    def within_full(self) -> float:
        rows = np.arange(len(self.y))
        return self.within(rows, self.codes)

    def cross(self, rows: np.ndarray) -> np.ndarray:
        beta, *_ = np.linalg.lstsq(self.Xc[rows], self.y[rows], rcond=None)
        return beta

    def draws(self, fn: str, n: int, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        out = []
        for _ in range(n):
            pick = rng.integers(0, len(self.ships), len(self.ships))
            parts = [self.rows_by_ship[i] for i in pick]
            rows = np.concatenate(parts)
            clusters = np.repeat(np.arange(len(pick)), [len(p) for p in parts])
            out.append(self.within(rows, clusters) if fn == "within" else self.cross(rows))
        return np.array(out)


def cross_design(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    cols = {
        "log_speed": np.log(df["avg_speed_kn"]),
        "log_gt": np.log(df["gross_tonnage"]),
        "eedi_generation": (df["design_generation"].str.startswith("EEDI")).astype(float),
        "vehicle_carrier": (df["segment_key"] == "Vehicle carrier").astype(float),
    }
    X = pd.DataFrame(cols)
    years = pd.get_dummies(df["reporting_year"], prefix="y", drop_first=True, dtype=float)
    X = pd.concat([pd.Series(1.0, index=df.index, name="const"), X, years], axis=1)
    return X.to_numpy(dtype=float), list(X.columns)


def q1(con) -> dict:
    df = _q(con, """
        select f.ship_key, f.reporting_year, f.segment_key, f.co2_kg_per_nm, f.avg_speed_kn, f.co2_g_per_tonne_nm,
               s.gross_tonnage, s.design_generation, s.size_class, s.ship_pseudonym
        from marts.fct_ship_year_emissions f
        join marts.dim_ship s on s.ship_version_key = f.ship_version_key
        where f.is_quality_ok and s.gross_tonnage is not null and f.co2_kg_per_nm > 0
    """)
    multi = df[df.groupby("ship_key")["ship_key"].transform("size") >= 2].copy()
    pm, pa_ = Panel(multi), Panel(df)
    b_within = pm.within_full()
    draws_within = pm.draws("within", plan.BOOTSTRAP_DRAWS, plan.SEED)
    beta, names = pa_.cross(np.arange(len(pa_.y))), pa_.names
    resid = pa_.y - pa_.Xc @ beta
    draws_cross = pa_.draws("cross", plan.BOOTSTRAP_DRAWS, plan.SEED + 1)
    coef = {}
    for i, n in enumerate(names):
        if n.startswith("y_") or n == "const":
            continue
        lo, hi = pct_interval(draws_cross[:, i])
        coef[n] = {"estimate": r(beta[i]), "low": r(lo), "high": r(hi)}
    seg = {}
    for s, part in multi.groupby("segment_key"):
        ps = Panel(part)
        b = ps.within_full()
        d = ps.draws("within", plan.BOOTSTRAP_DRAWS, plan.SEED + 2)
        lo, hi = pct_interval(d)
        seg[s] = {"estimate": r(b), "low": r(lo), "high": r(hi), "ships": int(part.ship_key.nunique())}
    lo, hi = pct_interval(draws_within)
    df = pa_.df.assign(residual=resid)
    result = {
        "question": "What drives fuel efficiency differences between vehicle carriers and ro-ro ships?",
        "ship_years": int(len(df)),
        "ships": int(df.ship_key.nunique()),
        "ships_within_model": int(multi.ship_key.nunique()),
        "speed_elasticity_within": {"estimate": r(b_within), "low": r(lo), "high": r(hi)},
        "speed_elasticity_by_segment": seg,
        "cross_sectional": coef,
        "cross_sectional_r2": r(1 - np.var(resid) / np.var(np.log(df["co2_kg_per_nm"]))),
        "size_effect_doubling_gt_pct": r((2 ** coef["log_gt"]["estimate"] - 1) * 100, 1),
        "eedi_generation_effect_pct": r((math.exp(coef["eedi_generation"]["estimate"]) - 1) * 100, 1),
        "eedi_generation_effect_interval_pct": [r((math.exp(coef["eedi_generation"]["low"]) - 1) * 100, 1),
                                                r((math.exp(coef["eedi_generation"]["high"]) - 1) * 100, 1)],
    }
    i_speed = names.index("log_speed")
    return result, df, draws_cross[:, i_speed], float(beta[i_speed])


# ---------------------------------------------------------------- Q2
def q2(con, b: float, draws: np.ndarray) -> dict:
    year = con.sql("select max(reporting_year) from marts.fct_ship_year_emissions").fetchall()[0][0]
    agg = _q(con, f"""
        select segment_key, sum(co2_t) co2_t, sum(fuel_t) fuel_t, sum(hours_at_sea) hours_at_sea, count(distinct ship_key) ships,
               sum(co2_ets_scope_t) ets_scope_t
        from marts.fct_ship_year_emissions where reporting_year = {year} and is_quality_ok group by 1
    """)
    tot = agg.sum(numeric_only=True)
    price = con.sql(f"select avg(eua_price_eur_per_t) from marts.fct_daily_carbon_price where year(date_key) = {year}").fetchall()[0][0]
    latest = con.sql("select max(date_key) from marts.fct_daily_carbon_price").fetchall()[0][0]
    price_2026 = con.sql("select avg(eua_price_eur_per_t) from marts.fct_daily_carbon_price where year(date_key) = 2026").fetchall()[0][0]
    fuel_price = con.sql("select value from reference.fuel_assumptions where assumption = 'fuel_price'").fetchall()[0][0]
    scope_share = tot["ets_scope_t"] / tot["co2_t"]

    def scenarios(bb: float, bdraws: np.ndarray | None) -> list[dict]:
        rows = []
        for dv in plan.SPEED_CHANGES:
            factor = saved_share(dv, bb)
            lo, hi = pct_interval(1 - (1 + dv) ** bdraws) if bdraws is not None else (factor, factor)
            co2_saved = tot["co2_t"] * factor
            rows.append({
                "speed_change": dv,
                "co2_saved_t": r(co2_saved, 0), "co2_saved_low_t": r(tot["co2_t"] * lo, 0), "co2_saved_high_t": r(tot["co2_t"] * hi, 0),
                "co2_saved_share": r(factor), "co2_saved_share_low": r(lo), "co2_saved_share_high": r(hi),
                "fuel_cost_saved_eur": r(tot["fuel_t"] * factor * fuel_price, 0),
                "ets_cost_saved_eur": r(ets_cost_saved(co2_saved, scope_share, price_2026), 0),
                "extra_days_per_ship": r(extra_days(tot["hours_at_sea"] / tot["ships"], dv), 1),
            })
        return rows

    lo, hi = pct_interval(draws)
    return {
        "question": "What would slower steaming save?",
        "base_year": int(year), "ships": int(tot["ships"]), "co2_t": r(tot["co2_t"], 0), "fuel_t": r(tot["fuel_t"], 0),
        "ets_scope_share": r(scope_share), "fuel_price_eur_per_t": r(fuel_price, 0),
        "carbon_price_eur_per_t": r(price_2026, 2), "carbon_price_basis": f"average daily EU ETS price in 2026 up to {latest}",
        "carbon_price_base_year_eur_per_t": r(price, 2),
        "relations": {
            "mrv_estimate": {"label": "Estimated from MRV data (conservative)", "elasticity": r(b),
                             "low": r(lo), "high": r(hi), "scenarios": scenarios(b, draws)},
            "engineering": {"label": "Engineering rule: fuel per mile rises with speed squared", "elasticity": plan.ENGINEERING_ELASTICITY,
                            "scenarios": scenarios(plan.ENGINEERING_ELASTICITY, None)},
        },
    }


# ---------------------------------------------------------------- Q3
def q3(con) -> dict:
    df = _q(con, """
        select f.reporting_year, f.segment_key, f.cii_rating, f.is_rating_worse, f.ship_key, s.ship_pseudonym
        from marts.fct_ship_year_emissions f join marts.dim_ship s on s.ship_version_key = f.ship_version_key
        where f.cii_rating is not null
    """)
    by = []
    for (y, s), g in df.groupby(["reporting_year", "segment_key"]):
        k = int(g.cii_rating.isin(["D", "E"]).sum())
        lo, hi = wilson(k, len(g))
        dist = g.cii_rating.value_counts().reindex(list("ABCDE"), fill_value=0)
        by.append({"year": int(y), "segment": s, "rated": len(g), "share_d_or_e": r(k / len(g)), "low": r(lo), "high": r(hi),
                   **{f"n_{c}": int(dist[c]) for c in "ABCDE"}})
    latest = int(df.reporting_year.max())
    first = 2023
    pv = df[df.reporting_year.isin([first, latest])].pivot_table(index=["ship_key", "ship_pseudonym", "segment_key"],
                                                                 columns="reporting_year", values="cii_rating", aggfunc="first").dropna()
    drift = pv[pv[latest] > pv[first]].reset_index()
    improve = pv[pv[latest] < pv[first]]
    drifting = [{"ship": row.ship_pseudonym, "segment": row.segment_key, "rating_first": row[first], "rating_latest": row[latest]}
                for _, row in drift.sort_values([latest, first], ascending=[False, True]).iterrows()]
    worse_by_year = df.groupby("reporting_year").is_rating_worse.sum().astype(int).to_dict()
    lat = df[df.reporting_year == latest]
    k = int(lat.cii_rating.isin(["D", "E"]).sum())
    return {
        "question": "Which ships drift toward poor carbon ratings?",
        "latest_year": latest, "first_official_year": first,
        "share_d_or_e_latest": r(k / len(lat)), "share_d_or_e_latest_interval": [r(x) for x in wilson(k, len(lat))],
        "ships_compared": int(len(pv)), "ships_worse_than_first_year": int(len(drift)), "ships_better_than_first_year": int(len(improve)),
        "ships_worse_than_previous_year": {str(k2): v for k2, v in worse_by_year.items()},
        "by_year_segment": by, "drifting_ships": drifting,
    }


# ---------------------------------------------------------------- Q4
def q4(con) -> dict:
    calls = _q(con, """
        select p.port_name, c.* from marts.fct_port_call c join marts.dim_port p using (port_key)
        where not c.is_window_edge
    """)
    ports = []
    for name, g in calls.groupby("port_name"):
        if len(g) < plan.MIN_CALLS_PER_PORT:
            continue
        k = int(g.has_waiting.sum())
        lo, hi = wilson(k, len(g))
        ports.append({
            "port": name, "calls": len(g), "ships": int(g.ship_key.nunique()),
            "share_with_waiting": r(k / len(g)), "share_low": r(lo), "share_high": r(hi),
            "median_waiting_h": r(g.waiting_hours.median(), 2), "p90_waiting_h": r(g.waiting_hours.quantile(0.9), 2),
            "median_berth_h": r(g.berth_hours.median(), 2), "p90_berth_h": r(g.berth_hours.quantile(0.9), 2),
            "median_port_h": r(g.port_hours.median(), 2),
        })
    ports.sort(key=lambda x: -x["calls"])
    k = int(calls.has_waiting.sum())
    waiting = calls[calls.has_waiting]
    # Weather and speed
    pos = _q(con, f"""
        select w.ship_key, w.sog_kn, w.wind_speed_ms, w.wave_height_m, w.wind_relative_deg, l.voyage_leg_key
        from intermediate.int_track_weather w
        join marts.fct_voyage_leg l on l.ship_key = w.ship_key and w.position_ts > l.departure_utc and w.position_ts <= l.arrival_utc
        where w.sog_kn >= {plan.MIN_TRANSIT_SPEED_KN} and w.wind_speed_ms is not null
    """)
    calm = pos[(pos.wind_speed_ms < plan.CALM_WIND_MS) & (pos.wave_height_m.fillna(0) < plan.CALM_WAVE_M)]
    ref = calm.groupby("ship_key").sog_kn.median().rename("calm_kn")
    pos = pos.join(ref, on="ship_key").dropna(subset=["calm_kn"])
    pos["rel"] = pos.sog_kn / pos.calm_kn - 1

    def bands(col, edges, unit):
        out = []
        rng = np.random.default_rng(plan.SEED + 3)
        cut = pd.cut(pos[col], edges, right=False)
        for iv, g in pos.groupby(cut, observed=True):
            legs = g.groupby("voyage_leg_key").rel.agg(["sum", "count"])
            if len(legs) < 5:
                continue
            est = legs["sum"].sum() / legs["count"].sum()
            draws = []
            arr = legs.to_numpy()
            for _ in range(plan.BOOTSTRAP_DRAWS):
                s = arr[rng.integers(0, len(arr), len(arr))]
                draws.append(s[:, 0].sum() / s[:, 1].sum())
            lo, hi = pct_interval(np.array(draws))
            out.append({"band": f"{iv.left:g} to {iv.right:g} {unit}" if iv.right < edges[-1] else f"{iv.left:g} {unit} and more",
                        "positions": int(len(g)), "legs": int(len(legs)),
                        "speed_change": r(est), "low": r(lo), "high": r(hi)})
        return out

    return {
        "question": "How much time is lost waiting at Norwegian ports, and does weather explain slow legs?",
        "calls": int(len(calls)), "ships": int(calls.ship_key.nunique()), "ports_with_calls": int(calls.port_name.nunique()),
        "share_with_waiting": r(k / len(calls)), "share_with_waiting_interval": [r(x) for x in wilson(k, len(calls))],
        "total_waiting_h": r(calls.waiting_hours.sum(), 1),
        "mean_waiting_when_waiting_h": r(waiting.waiting_hours.mean(), 1) if len(waiting) else None,
        "median_berth_h": r(calls.berth_hours.median(), 2),
        "kystverket_confirmed_share": r(calls.is_kystverket_matched.mean()),
        "ports": ports,
        "speed_by_wind": bands("wind_speed_ms", plan.WIND_BANDS, "m/s"),
        "speed_by_waves": bands("wave_height_m", plan.WAVE_BANDS, "m"),
        "transit_positions": int(len(pos)), "ships_with_calm_reference": int(pos.ship_key.nunique()),
    }


# ---------------------------------------------------------------- Q5
def q5(df: pd.DataFrame) -> dict:
    mad = np.median(np.abs(df.residual - np.median(df.residual)))
    df = df.assign(z=(df.residual - np.median(df.residual)) / (1.4826 * mad))
    flagged = df[df.z.abs() > plan.DEVIATION_Z].copy()
    flagged["excess_pct"] = (np.exp(flagged.residual) - 1) * 100
    items = [{
        "ship": row.ship_pseudonym, "segment": row.segment_key, "year": int(row.reporting_year), "size_class": row.size_class,
        "co2_kg_per_nm": r(row.co2_kg_per_nm, 1), "speed_kn": r(row.avg_speed_kn, 1),
        "excess_vs_expected_pct": r(row.excess_pct, 1), "z": r(row.z, 2),
        "direction": "above expected" if row.z > 0 else "below expected",
    } for _, row in flagged.sort_values("z", ascending=False).iterrows()]
    return {
        "question": "Which ship-years are far from what speed, size and age predict?",
        "ship_years_tested": int(len(df)), "flagged": int(len(flagged)),
        "flagged_above": int((flagged.z > 0).sum()), "flagged_below": int((flagged.z < 0).sum()),
        "threshold_z": plan.DEVIATION_Z, "items": items,
    }, df


# ---------------------------------------------------------------- figures
def figure(df: pd.DataFrame, res1: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG.mkdir(parents=True, exist_ok=True)
    latest = df[df.reporting_year == df.reporting_year.max()]
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    colors = {"Vehicle carrier": "#eb6834", "Ro-ro ship": "#2a78d6"}
    for seg, g in latest.groupby("segment_key"):
        ax.scatter(g.avg_speed_kn, g.co2_kg_per_nm, s=14, alpha=0.6, color=colors.get(seg, "#6B7A8F"), label=seg, edgecolors="none")
    b = res1["cross_sectional"]["log_speed"]["estimate"]
    xs = np.linspace(latest.avg_speed_kn.quantile(0.02), latest.avg_speed_kn.quantile(0.98), 50)
    x0 = latest.avg_speed_kn.median()
    y0 = latest.co2_kg_per_nm.median()
    ax.plot(xs, y0 * (xs / x0) ** b, color="#0b0b0b", lw=2, label=f"Fitted across ships: CO2 per nm ~ speed^{b:.2f}")
    ax.plot(xs, y0 * (xs / x0) ** plan.ENGINEERING_ELASTICITY, color="#52514e", lw=1.5, ls="--",
            label="Engineering rule: CO2 per nm ~ speed^2")
    ax.set_xlabel("Average speed (knots)")
    ax.set_ylabel("CO2 per nautical mile (kg)")
    ax.set_title(f"Ro-ro ships and vehicle carriers, EU MRV {int(latest.reporting_year.max())}", loc="left", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E5E9EF")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "efficiency_vs_speed.png", metadata={"Software": None})
    plt.close(fig)


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        r1, df, draws, b = q1(con)
        r2 = q2(con, b, draws)
        r3 = q3(con)
        r4 = q4(con)
        r5, _ = q5(df)
    finally:
        con.close()
    for name, res in (("q1_drivers", r1), ("q2_scenarios", r2), ("q3_ratings", r3), ("q4_ports_weather", r4), ("q5_deviations", r5)):
        (OUT / f"{name}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    figure(df, r1)
    e = r1["speed_elasticity_within"]
    c = r1["cross_sectional"]["log_speed"]
    params = pd.DataFrame([
        {"parameter": "speed_elasticity_mrv", "segment": "All", "value": c["estimate"], "low": c["low"], "high": c["high"],
         "description": "Exponent b in CO2 per nautical mile ~ speed^b across ships, controlling for size, design generation, segment and year (MRV data)."},
        {"parameter": "speed_elasticity_engineering", "segment": "All", "value": plan.ENGINEERING_ELASTICITY,
         "low": plan.ENGINEERING_ELASTICITY, "high": plan.ENGINEERING_ELASTICITY,
         "description": "Engineering rule: propulsion power ~ speed^3, so fuel per nautical mile ~ speed^2."},
        {"parameter": "speed_elasticity_within_ship", "segment": "All", "value": e["estimate"], "low": e["low"], "high": e["high"],
         "description": "Same-ship estimate with ship and year fixed effects. Biased toward zero because MRV time at sea includes waiting."},
    ] + [
        {"parameter": "speed_elasticity_within_ship", "segment": s, "value": v["estimate"], "low": v["low"], "high": v["high"],
         "description": f"Same-ship estimate on {s.lower()}s only."} for s, v in r1["speed_elasticity_by_segment"].items()
    ])
    pq.write_table(pa.Table.from_pandas(params, preserve_index=False).replace_schema_metadata(None),
                   EXPORTS / "gold" / "model_parameters.parquet")
    print(json.dumps({"speed_elasticity_within": e, "speed_elasticity_mrv": c, "q3_de": r3["share_d_or_e_latest"], "q4_wait": r4["share_with_waiting"],
                      "q5_flagged": r5["flagged"]}, indent=1))
    return {"q1": r1, "q2": r2, "q3": r3, "q4": r4, "q5": r5}


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
Generate the FINAL exact-data Figures 2 and 3 for:
"The Neuroepidemiological Transition in Brazil: Nationwide Trends in
Cerebrovascular, Dementia, Alzheimer's, and Parkinson's Mortality, 2000-2024"

This script uses the exact annual analytical CSVs:
  outputs/article2/article2_standardized_rates.csv
  outputs/article2/article2_nti.csv

and the frozen primary trend table:
  Article2_Table2_Primary.csv

Outputs (all generated directly from the analytical data):
  Figure2_FINAL_EXACT.pdf      # vector
  Figure2_FINAL_EXACT.svg      # vector
  Figure2_FINAL_EXACT_600dpi.tiff
  Figure3_FINAL_EXACT.pdf      # vector
  Figure3_FINAL_EXACT.svg      # vector
  Figure3_FINAL_EXACT_600dpi.tiff

Primary trend model:
  inverse-variance-weighted piecewise log-linear regression,
  exhaustive BIC-selected breakpoints already frozen in Table 2,
  minimum segment length = 4 years.
"""

from pathlib import Path
import argparse
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Publication-safe font embedding and typography.
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 11.5,
    "axes.labelsize": 10.5,
    "xtick.labelsize": 9.0,
    "ytick.labelsize": 9.0,
    "legend.fontsize": 8.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

CAUSES = ["Cerebrovascular", "Dementia", "Alzheimer", "Parkinson"]
DISPLAY = {
    "Cerebrovascular": "Cerebrovascular disease",
    "Dementia": "Dementia",
    "Alzheimer": "Alzheimer's disease",
    "Parkinson": "Parkinson's disease",
}
PANELS = dict(zip(CAUSES, "ABCD"))

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--rates", default="outputs/article2/article2_standardized_rates.csv")
    p.add_argument("--nti", default="outputs/article2/article2_nti.csv")
    p.add_argument("--table2", default="outputs/article2/final/table2_piecewise_trends.csv")
    p.add_argument("--sensdir", default="outputs/article2/piecewise_bic_sensitivity")
    p.add_argument("--outdir", default="outputs/article2/final_exact")
    return p.parse_args()

def require_cols(df, cols, name):
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise ValueError(f"{name}: missing columns: {miss}")


def load_canonical_trends(table2_path: Path, sensdir: Path):
    """
    Return a canonical numeric trend table with columns:
      Outcome, Breakpoints, Segment,
      APC_percent, APC_LCL95, APC_UCL95,
      AAPC_2000_2024_percent, AAPC_LCL95, AAPC_UCL95

    First tries the supplied Table 2 CSV. If it does not contain split CI columns
    (the common final-output format stores CIs as formatted strings), it rebuilds
    the canonical table from the exact primary sensitivity CSVs used to create Table 2.
    """
    if table2_path.exists():
        t = pd.read_csv(table2_path)
        canonical = [
            "Outcome", "Breakpoints", "Segment",
            "APC_percent", "APC_LCL95", "APC_UCL95",
            "AAPC_2000_2024_percent", "AAPC_LCL95", "AAPC_UCL95",
        ]
        if all(c in t.columns for c in canonical):
            return t[canonical].copy()

    sel_path = sensdir / "sensitivity_selected_models.csv"
    apc_path = sensdir / "sensitivity_APC_by_segment.csv"
    aapc_path = sensdir / "sensitivity_AAPC.csv"
    for p in (sel_path, apc_path, aapc_path):
        if not p.exists():
            raise FileNotFoundError(
                "Could not use the formatted Table 2 CSV and a required exact "
                f"sensitivity file is missing: {p}"
            )

    sel = pd.read_csv(sel_path)
    apc = pd.read_csv(apc_path)
    aapc = pd.read_csv(aapc_path)

    PRIMARY = "full_min4_primary"
    for name, df in [("selected", sel), ("APC", apc), ("AAPC", aapc)]:
        if "scenario" not in df.columns or "series" not in df.columns:
            raise ValueError(f"{name} sensitivity CSV has unexpected columns: {list(df.columns)}")

    sel = sel[sel["scenario"] == PRIMARY].copy()
    apc = apc[apc["scenario"] == PRIMARY].copy()
    aapc = aapc[aapc["scenario"] == PRIMARY].copy()

    required_apc = ["start_year", "end_year", "APC", "APC_low", "APC_high"]
    required_aapc = ["AAPC", "AAPC_low", "AAPC_high"]
    for c in required_apc:
        if c not in apc.columns:
            raise ValueError(f"APC sensitivity CSV missing column {c}; columns={list(apc.columns)}")
    for c in required_aapc:
        if c not in aapc.columns:
            raise ValueError(f"AAPC sensitivity CSV missing column {c}; columns={list(aapc.columns)}")
    if "breakpoints" not in sel.columns:
        raise ValueError(f"Selected-model CSV missing breakpoints; columns={list(sel.columns)}")

    order = ["Cerebrovascular", "Dementia", "Alzheimer", "Parkinson", "NTI"]
    rows = []
    for series in order:
        ssel = sel[sel["series"] == series]
        sa = apc[apc["series"] == series].sort_values(["start_year", "end_year"])
        aa = aapc[aapc["series"] == series]
        if ssel.empty or sa.empty or aa.empty:
            raise RuntimeError(f"Primary results missing for {series}")

        bp = ssel.iloc[0]["breakpoints"]
        bp = "" if pd.isna(bp) else str(bp)
        aa0 = aa.iloc[0]

        first = True
        for _, r in sa.iterrows():
            rows.append({
                "Outcome": series,
                "Breakpoints": bp if first else "",
                "Segment": f'{int(round(r["start_year"]))}–{int(round(r["end_year"]))}',
                "APC_percent": float(r["APC"]),
                "APC_LCL95": float(r["APC_low"]),
                "APC_UCL95": float(r["APC_high"]),
                "AAPC_2000_2024_percent": float(aa0["AAPC"]) if first else np.nan,
                "AAPC_LCL95": float(aa0["AAPC_low"]) if first else np.nan,
                "AAPC_UCL95": float(aa0["AAPC_high"]) if first else np.nan,
            })
            first = False

    return pd.DataFrame(rows)


def national_rates(rates, cause):
    d = rates[
        (rates["geography_level"] == "Brazil") &
        (rates["geography"] == "Brazil") &
        (rates["sex"] == "Both") &
        (rates["cause"] == cause)
    ].copy()
    d = d.sort_values("year")
    if list(d["year"].astype(int)) != list(range(2000, 2025)):
        raise ValueError(f"{cause}: expected exactly annual 2000-2024 data.")
    return d

def national_nti(nti):
    d = nti[
        (nti["geography_level"] == "Brazil") &
        (nti["geography"] == "Brazil") &
        (nti["sex"] == "Both")
    ].copy().sort_values("year")
    if list(d["year"].astype(int)) != list(range(2000, 2025)):
        raise ValueError("NTI: expected exactly annual 2000-2024 data.")
    return d

def breakpoints_for(table2, outcome):
    r = table2[table2["Outcome"] == outcome]
    if r.empty:
        raise ValueError(f"Table 2 missing outcome: {outcome}")
    raw = r["Breakpoints"].dropna()
    if raw.empty or str(raw.iloc[0]).strip() == "":
        return []
    return [int(float(x)) for x in str(raw.iloc[0]).split(";")]

def fit_piecewise(year, y, se, knots):
    """Same weighted log-linear parameterization used in the frozen analysis."""
    year = np.asarray(year, dtype=float)
    y = np.asarray(y, dtype=float)
    se = np.asarray(se, dtype=float)
    if np.any(y <= 0) or np.any(se <= 0):
        raise ValueError("All estimates and SEs must be positive for log-WLS.")
    y0 = year.min()
    t = year - y0
    cols = [np.ones_like(t), t]
    for k in knots:
        cols.append(np.maximum(0.0, t - (float(k) - y0)))
    X = np.column_stack(cols)
    logy = np.log(y)
    selog = se / y
    w = 1.0 / np.square(selog)
    XtW = X.T * w
    beta = np.linalg.solve(XtW @ X, XtW @ logy)
    fitted = np.exp(X @ beta)
    return beta, fitted

def segment_slopes(beta, knots):
    slopes = []
    s = beta[1]
    slopes.append(s)
    for j in range(len(knots)):
        s = s + beta[2 + j]
        slopes.append(s)
    return slopes

def apc_from_slope(s):
    return 100.0 * (math.exp(s) - 1.0)

def model_aapc(beta, knots, start=2000, end=2024):
    # Linear contrast corresponding to average annual log change over full interval.
    T = end - start
    c = np.zeros_like(beta, dtype=float)
    c[1] = 1.0
    for j, k in enumerate(knots):
        c[2 + j] = (end - k) / T
    return 100.0 * (math.exp(float(c @ beta)) - 1.0)

def table_rows(table2, outcome):
    r = table2[table2["Outcome"] == outcome].copy()
    return r

def validate_model_against_table(beta, knots, table2, outcome, tol=0.015):
    rows = table_rows(table2, outcome)
    slopes = segment_slopes(beta, knots)
    apcs = [apc_from_slope(s) for s in slopes]
    expected = rows["APC_percent"].astype(float).tolist()
    if len(apcs) != len(expected):
        raise AssertionError(f"{outcome}: segment count mismatch.")
    for got, exp in zip(apcs, expected):
        if abs(got - exp) > tol:
            raise AssertionError(
                f"{outcome}: recomputed APC {got:.6f} differs from frozen Table 2 {exp:.6f}."
            )
    exp_aapc = float(rows["AAPC_2000_2024_percent"].dropna().iloc[0])
    got_aapc = model_aapc(beta, knots)
    if abs(got_aapc - exp_aapc) > tol:
        raise AssertionError(
            f"{outcome}: recomputed AAPC {got_aapc:.6f} differs from frozen Table 2 {exp_aapc:.6f}."
        )

def fmt_pct(x):
    # Use ASCII minus in PDF text for maximal renderer compatibility.
    return f"{x:+.2f}%"

def annotation_text(table2, outcome):
    r = table_rows(table2, outcome)
    lines = []
    for _, z in r.iterrows():
        est = float(z["APC_percent"])
        lo = float(z["APC_LCL95"])
        hi = float(z["APC_UCL95"])
        lines.append(
            f'{z["Segment"]}: {fmt_pct(est)} ({lo:.2f} to {hi:.2f})'
        )
    first = r[r["AAPC_2000_2024_percent"].notna()].iloc[0]
    ae = float(first["AAPC_2000_2024_percent"])
    al = float(first["AAPC_LCL95"])
    ah = float(first["AAPC_UCL95"])
    lines += ["", "AAPC 2000-2024:", f"{fmt_pct(ae)} ({al:.2f} to {ah:.2f})"]
    return "\n".join(lines)

def set_common_axis(ax, ymax=None):
    ax.set_xlim(1999.4, 2024.6)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2024])
    ax.set_xlabel("Year", labelpad=4)
    ax.set_ylabel("ASMR per 100,000", labelpad=5)
    ax.tick_params(direction="out", length=3.5, width=0.8, pad=3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ymax is not None:
        ax.set_ylim(0, ymax)
    else:
        ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))


def save_figure(fig, outdir, stem):
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(outdir / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(
        outdir / f"{stem}_600dpi.tiff",
        dpi=600,
        bbox_inches="tight",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    # Extra PNG preview, not the submission master.
    fig.savefig(outdir / f"{stem}_preview.png", dpi=220, bbox_inches="tight")

def make_figure2(rates, table2, outdir):
    # Publication layout: 2x2 panels, shared legend, neutral breakpoint styling.
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 9.0))
    axes = axes.ravel()

    ymax = {
        "Cerebrovascular": 72,
        "Dementia": 14,
        "Alzheimer": 12,
        "Parkinson": 2.7,
    }

    box_pos = {
        "Cerebrovascular": (0.51, 0.965),
        "Dementia": (0.035, 0.965),
        "Alzheimer": (0.035, 0.965),
        "Parkinson": (0.035, 0.965),
    }

    shared_handles = None
    shared_labels = None

    for ax, cause in zip(axes, CAUSES):
        d = national_rates(rates, cause)
        knots = breakpoints_for(table2, cause)
        beta, fitted = fit_piecewise(
            d["year"], d["asmr_per_100k"], d["asmr_se"], knots
        )
        validate_model_against_table(beta, knots, table2, cause)

        # Observed annual estimates and exact piecewise fit.
        h_obs = ax.plot(
            d["year"], d["asmr_per_100k"],
            linestyle="None", marker="o", markersize=4.0,
            color="#0072B2", label="Observed", zorder=3
        )[0]
        h_fit = ax.plot(
            d["year"], fitted,
            linewidth=2.0, color="#D55E00",
            label="Fitted (piecewise)", zorder=2
        )[0]

        if shared_handles is None:
            shared_handles = [h_obs, h_fit]
            shared_labels = ["Observed", "Fitted (piecewise)"]

        # TRUE model breakpoints only. Neutral gray avoids confusion with x-axis ticks/grid.
        for k in knots:
            ax.axvline(
                k, linestyle=(0, (4, 3)), linewidth=0.95,
                color="0.55", alpha=0.85, zorder=1
            )
            # Label clearly as a breakpoint; no relation to 5-year tick spacing.
            ax.text(
                k, 0.028, f"BP {k}",
                transform=ax.get_xaxis_transform(),
                ha="center", va="bottom",
                fontsize=8.0, color="0.35"
            )

        ax.set_title(DISPLAY[cause], fontweight="bold", pad=9)
        ax.text(
            -0.105, 1.035, PANELS[cause],
            transform=ax.transAxes, fontsize=17, fontweight="bold",
            ha="left", va="top"
        )

        set_common_axis(ax, ymax[cause])

        ax.text(
            *box_pos[cause], annotation_text(table2, cause),
            transform=ax.transAxes, va="top", ha="left", fontsize=8.35,
            linespacing=1.18,
            bbox=dict(
                boxstyle="round,pad=0.42", facecolor="white",
                edgecolor="0.65", linewidth=0.75, alpha=0.96
            ),
            zorder=4
        )

        # No per-panel legend: prevents overlap with breakpoint labels/data.
        leg = ax.get_legend()
        if leg is not None:
            leg.remove()

    # One shared legend for all four panels.
    fig.legend(
        shared_handles, shared_labels,
        loc="lower center", bbox_to_anchor=(0.5, 0.025),
        ncol=2, frameon=False, handlelength=2.8,
        columnspacing=2.0, fontsize=9.2
    )

    fig.subplots_adjust(
        left=0.075, right=0.992, bottom=0.11, top=0.95,
        wspace=0.27, hspace=0.34
    )
    save_figure(fig, outdir, "Figure2_FINAL_EXACT")
    plt.close(fig)


def make_figure3(nti, table2, outdir):
    d = national_nti(nti)
    knots = breakpoints_for(table2, "NTI")
    beta, fitted = fit_piecewise(d["year"], d["nti"], d["nti_se"], knots)
    validate_model_against_table(beta, knots, table2, "NTI")

    fig, ax = plt.subplots(figsize=(9.2, 6.25))

    h_obs = ax.plot(
        d["year"], d["nti"],
        linestyle="None", marker="o", markersize=4.4,
        color="#0072B2", label="Observed", zorder=3
    )[0]
    h_fit = ax.plot(
        d["year"], fitted,
        linewidth=2.1, color="#D55E00",
        label="Fitted (piecewise)", zorder=2
    )[0]

    # Only TRUE BIC-selected breakpoints. Neutral gray and "BP" labels make this explicit.
    for k in knots:
        ax.axvline(
            k, linestyle=(0, (4, 3)), linewidth=0.95,
            color="0.55", alpha=0.85, zorder=1
        )
        ax.text(
            k, 0.022, f"BP {k}",
            transform=ax.get_xaxis_transform(),
            ha="center", va="bottom",
            fontsize=8.5, color="0.35"
        )

    ax.set_xlim(1999.5, 2024.6)
    ax.set_ylim(0, 0.40)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2024])
    ax.set_xlabel("Year", labelpad=5)
    ax.set_ylabel("Neuroepidemiological Transition Index (NTI)", labelpad=7)
    ax.tick_params(direction="out", length=3.5, width=0.8, pad=3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.text(
        0.025, 0.965, annotation_text(table2, "NTI"),
        transform=ax.transAxes, va="top", ha="left", fontsize=9.25,
        linespacing=1.20,
        bbox=dict(
            boxstyle="round,pad=0.46", facecolor="white",
            edgecolor="0.65", linewidth=0.75, alpha=0.96
        ),
        zorder=4
    )

    # Legend fully outside plotting area.
    ax.legend(
        handles=[h_obs, h_fit],
        labels=["Observed", "Fitted (piecewise)"],
        frameon=False, loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=2, handlelength=2.7, columnspacing=1.8
    )

    fig.subplots_adjust(left=0.12, right=0.985, bottom=0.205, top=0.975)
    save_figure(fig, outdir, "Figure3_FINAL_EXACT")
    plt.close(fig)


def main():
    args = parse_args()
    rates_path = Path(args.rates)
    nti_path = Path(args.nti)
    table2_path = Path(args.table2)
    sensdir = Path(args.sensdir)
    outdir = Path(args.outdir)

    for p in [rates_path, nti_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    rates = pd.read_csv(rates_path)
    nti = pd.read_csv(nti_path)
    table2 = load_canonical_trends(table2_path, sensdir)

    require_cols(
        rates,
        ["geography_level", "geography", "sex", "cause",
         "year", "asmr_per_100k", "asmr_se"],
        "article2_standardized_rates.csv"
    )
    require_cols(
        nti,
        ["geography_level", "geography", "sex", "year", "nti", "nti_se"],
        "article2_nti.csv"
    )
    require_cols(
        table2,
        ["Outcome", "Breakpoints", "Segment", "APC_percent",
         "APC_LCL95", "APC_UCL95", "AAPC_2000_2024_percent",
         "AAPC_LCL95", "AAPC_UCL95"],
        "canonical primary trend table"
    )

    # Strict endpoint checks against the frozen manuscript/table values.
    expected_endpoints = {
        "Cerebrovascular": (63.692170814854016, 36.88069405911038),
        "Dementia": (1.754170199822264, 11.385291122267985),
        "Alzheimer": (1.2375944235061795, 9.743717410420764),
        "Parkinson": (0.8146584639587928, 2.1145466979105634),
    }
    for cause, (v2000, v2024) in expected_endpoints.items():
        d = national_rates(rates, cause).set_index("year")
        if not np.isclose(d.loc[2000, "asmr_per_100k"], v2000, rtol=0, atol=1e-9):
            raise AssertionError(f"{cause}: 2000 ASMR differs from frozen analysis.")
        if not np.isclose(d.loc[2024, "asmr_per_100k"], v2024, rtol=0, atol=1e-9):
            raise AssertionError(f"{cause}: 2024 ASMR differs from frozen analysis.")

    dn = national_nti(nti).set_index("year")
    if not np.isclose(dn.loc[2000, "nti"], 1.754170199822264 / 63.692170814854016, atol=1e-9):
        raise AssertionError("NTI 2000 differs from frozen component rates.")
    if not np.isclose(dn.loc[2024, "nti"], 11.385291122267985 / 36.88069405911038, atol=1e-9):
        raise AssertionError("NTI 2024 differs from frozen component rates.")

    make_figure2(rates, table2, outdir)
    make_figure3(nti, table2, outdir)

    print(f"Done. Exact-data figures written to: {outdir.resolve()}")
    print("Figure 2 and Figure 3 validated against frozen endpoints, breakpoints, APCs, and AAPCs.")

if __name__ == "__main__":
    main()
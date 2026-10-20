#!/usr/bin/env python3
"""
Article 2 — final Table 2 and publication figures.

Run from the project root:
    python 12_article2_final_outputs.py

Inputs
------
outputs/article2/article2_standardized_rates.csv
outputs/article2/article2_nti.csv
outputs/article2/piecewise_bic_sensitivity/sensitivity_selected_models.csv
outputs/article2/piecewise_bic_sensitivity/sensitivity_APC_by_segment.csv
outputs/article2/piecewise_bic_sensitivity/sensitivity_AAPC.csv

Outputs
-------
outputs/article2/final/table2_piecewise_trends.csv
outputs/article2/final/table2_piecewise_trends_pretty.csv
outputs/article2/final/figure1_national_trajectories.{png,pdf,svg,tiff}
outputs/article2/final/figure2_nti.{png,pdf,svg,tiff}
outputs/article2/final/figure_captions.txt

The primary specification is full_min4_primary: weighted piecewise log-linear
regression, inverse-variance weights in the log scale, 0–4 breakpoints,
exhaustive BIC selection, minimum segment length of four years.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RATES = Path("outputs/article2/article2_standardized_rates.csv")
NTI = Path("outputs/article2/article2_nti.csv")
SENS = Path("outputs/article2/piecewise_bic_sensitivity")
SEL = SENS / "sensitivity_selected_models.csv"
APC = SENS / "sensitivity_APC_by_segment.csv"
AAPC = SENS / "sensitivity_AAPC.csv"
OUT = Path("outputs/article2/final")
PRIMARY = "full_min4_primary"


def require(path: Path):
    if not path.exists():
        sys.exit(f"Missing required file: {path}")


def p_string(p):
    if pd.isna(p):
        return ""
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def ci_string(est, lo, hi, digits=2, plus=False):
    sign = "+" if plus and est > 0 else ""
    return f"{sign}{est:.{digits}f} ({lo:.{digits}f} to {hi:.{digits}f})"


def make_table2():
    sel = pd.read_csv(SEL)
    apc = pd.read_csv(APC)
    aapc = pd.read_csv(AAPC)

    sel = sel[sel["scenario"] == PRIMARY].copy()
    apc = apc[apc["scenario"] == PRIMARY].copy()
    aapc = aapc[aapc["scenario"] == PRIMARY].copy()

    order = ["Cerebrovascular", "Dementia", "Alzheimer", "Parkinson", "NTI"]
    rows = []
    for series in order:
        ssel = sel[sel["series"] == series]
        sa = apc[apc["series"] == series].sort_values("segment")
        aa = aapc[aapc["series"] == series]
        if ssel.empty or sa.empty or aa.empty:
            raise RuntimeError(f"Primary results missing for {series}")
        breakpoints = str(ssel.iloc[0]["breakpoints"]) if pd.notna(ssel.iloc[0]["breakpoints"]) else ""
        aa0 = aa.iloc[0]
        first = True
        for _, r in sa.iterrows():
            rows.append({
                "Outcome": series,
                "Breakpoints": breakpoints if first else "",
                "Segment": f"{int(round(r.start_year))}–{int(round(r.end_year))}",
                "APC_percent": r.APC,
                "APC_lcl95": r.APC_low,
                "APC_ucl95": r.APC_high,
                "APC_p": r.p_value,
                "AAPC_2000_2024_percent": aa0.AAPC if first else np.nan,
                "AAPC_lcl95": aa0.AAPC_low if first else np.nan,
                "AAPC_ucl95": aa0.AAPC_high if first else np.nan,
                "AAPC_p": aa0.p_value if first else np.nan,
            })
            first = False

    t = pd.DataFrame(rows)
    t.to_csv(OUT / "table2_piecewise_trends.csv", index=False)

    pretty = pd.DataFrame({
        "Outcome": t["Outcome"],
        "BIC-selected breakpoints": t["Breakpoints"].replace(";", ", ", regex=False),
        "Segment": t["Segment"],
        "APC, % per year (95% CI)": [
            ci_string(e, l, u, 2) for e, l, u in zip(t.APC_percent, t.APC_lcl95, t.APC_ucl95)
        ],
        "P value": [p_string(p) for p in t.APC_p],
        "AAPC 2000–2024, % per year (95% CI)": [
            "" if pd.isna(e) else ci_string(e, l, u, 2)
            for e, l, u in zip(t.AAPC_2000_2024_percent, t.AAPC_lcl95, t.AAPC_ucl95)
        ],
        "AAPC P value": ["" if pd.isna(p) else p_string(p) for p in t.AAPC_p],
    })
    pretty.to_csv(OUT / "table2_piecewise_trends_pretty.csv", index=False)
    return sel, apc, aapc


def wls_piecewise(year, y, se, knots):
    year = np.asarray(year, dtype=float)
    y = np.asarray(y, dtype=float)
    se = np.asarray(se, dtype=float)
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
    return fitted


def save_all(fig, stem):
    fig.savefig(OUT / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.tiff", dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})


def national_rate_frame(rates, cause):
    d = rates[(rates.geography_level == "Brazil") &
              (rates.geography == "Brazil") &
              (rates.sex == "Both") &
              (rates.cause == cause)].copy()
    return d.sort_values("year")


def make_figures(sel, aapc):
    rates = pd.read_csv(RATES)
    nti = pd.read_csv(NTI)
    psel = sel.set_index("series")
    paa = aapc.set_index("series")

    # Figure 1: two-panel national ASMR trajectories.
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 7.4), sharex=True, constrained_layout=True)
    for ax, cause, panel in zip(axes, ["Cerebrovascular", "Dementia"], ["A", "B"]):
        d = national_rate_frame(rates, cause)
        bp_raw = psel.loc[cause, "breakpoints"]
        knots = [] if pd.isna(bp_raw) or str(bp_raw).strip() == "" else [float(x) for x in str(bp_raw).split(";")]
        fit = wls_piecewise(d.year, d.asmr_per_100k, d.asmr_se, knots)
        ax.plot(d.year, d.asmr_per_100k, marker="o", markersize=3.4, linewidth=0.9, label="Observed ASMR")
        ax.plot(d.year, fit, linewidth=2.0, label="Piecewise log-linear fit")
        for k in knots:
            ax.axvline(k, linestyle="--", linewidth=0.8, alpha=0.65)
            ax.text(k, ax.get_ylim()[1], str(int(round(k))), ha="center", va="bottom", fontsize=8)
        aa = paa.loc[cause]
        ax.text(0.02, 0.08,
                f"AAPC {aa.AAPC:.2f}%/year\n95% CI {aa.AAPC_low:.2f} to {aa.AAPC_high:.2f}",
                transform=ax.transAxes, fontsize=8.5, va="bottom")
        ax.set_ylabel("ASMR per 100,000")
        ax.text(-0.08, 1.03, panel, transform=ax.transAxes, fontsize=12, fontweight="bold")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", linewidth=0.35, alpha=0.35)
    axes[-1].set_xlabel("Year")
    axes[0].legend(frameon=False, loc="best", fontsize=8.5)
    save_all(fig, "figure1_national_trajectories")
    plt.close(fig)

    # Figure 2: NTI trajectory.
    d = nti[(nti.geography_level == "Brazil") &
            (nti.geography == "Brazil") &
            (nti.sex == "Both")].copy().sort_values("year")
    bp_raw = psel.loc["NTI", "breakpoints"]
    knots = [] if pd.isna(bp_raw) or str(bp_raw).strip() == "" else [float(x) for x in str(bp_raw).split(";")]
    fit = wls_piecewise(d.year, d.nti, d.nti_se, knots)

    fig, ax = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    ax.plot(d.year, d.nti, marker="o", markersize=3.6, linewidth=0.9, label="Observed NTI")
    ax.plot(d.year, fit, linewidth=2.0, label="Piecewise log-linear fit")
    for k in knots:
        ax.axvline(k, linestyle="--", linewidth=0.8, alpha=0.65)
        ax.text(k, ax.get_ylim()[1], str(int(round(k))), ha="center", va="bottom", fontsize=8)
    aa = paa.loc["NTI"]
    ax.text(0.02, 0.92,
            f"AAPC {aa.AAPC:.2f}%/year (95% CI {aa.AAPC_low:.2f} to {aa.AAPC_high:.2f})",
            transform=ax.transAxes, fontsize=8.5, va="top")
    ax.set_xlabel("Year")
    ax.set_ylabel("Neuroepidemiological Transition Index (NTI)")
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linewidth=0.35, alpha=0.35)
    ax.legend(frameon=False, loc="best", fontsize=8.5)
    save_all(fig, "figure2_nti")
    plt.close(fig)


def write_captions():
    text = """Figure 1. National age-standardized mortality trajectories for cerebrovascular disease and dementia in Brazil, 2000–2024. Annual age-standardized mortality rates (ASMRs) per 100,000 population are shown together with inverse-variance-weighted piecewise log-linear fits. Vertical dashed lines indicate BIC-selected breakpoints from the primary model, which required a minimum segment length of four years. Panel A shows cerebrovascular mortality and Panel B dementia mortality. AAPC, average annual percentage change; CI, confidence interval.\n\nFigure 2. Neuroepidemiological Transition Index in Brazil, 2000–2024. The NTI was defined as the ratio of dementia to cerebrovascular age-standardized mortality rates. Annual estimates are shown with the inverse-variance-weighted piecewise log-linear fit. Vertical dashed lines indicate BIC-selected breakpoints from the primary model. AAPC, average annual percentage change; CI, confidence interval.\n"""
    (OUT / "figure_captions.txt").write_text(text, encoding="utf-8")


def main():
    for f in [RATES, NTI, SEL, APC, AAPC]:
        require(f)
    OUT.mkdir(parents=True, exist_ok=True)
    sel, apc, aapc = make_table2()
    make_figures(sel, aapc)
    write_captions()
    print("Final Table 2 and Figures 1–2 written to:", OUT.resolve())


if __name__ == "__main__":
    main()
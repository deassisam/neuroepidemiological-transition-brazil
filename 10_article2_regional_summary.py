#!/usr/bin/env python3
"""
Artigo 2 — resumo regional para abstract/Table 4.

Entradas:
  outputs/article2/article2_standardized_rates.csv
  outputs/article2/article2_nti.csv

Saídas:
  outputs/article2/tables/table4_regional_summary.csv
  outputs/article2/tables/table4_regional_summary_pretty.csv
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

RATES = Path("outputs/article2/article2_standardized_rates.csv")
NTI = Path("outputs/article2/article2_nti.csv")
OUTDIR = Path("outputs/article2/tables")

YEARS = [2000, 2024]
CAUSES = ["Cerebrovascular", "Dementia"]

def pct_change(v0, v1):
    return np.nan if pd.isna(v0) or pd.isna(v1) or v0 == 0 else 100.0*(v1/v0 - 1.0)

def main():
    if not RATES.exists() or not NTI.exists():
        sys.exit("Execute primeiro: python 06_article2_rates.py")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    r = pd.read_csv(RATES)
    n = pd.read_csv(NTI)

    rr = r[
        (r["geography_level"] == "Region")
        & (r["sex"] == "Both")
        & (r["cause"].isin(CAUSES))
        & (r["year"].isin(YEARS))
    ].copy()

    if rr.empty:
        sys.exit("Não encontrei séries regionais Both para 2000/2024.")

    piv = rr.pivot_table(
        index="geography",
        columns=["cause", "year"],
        values="asmr_per_100k",
        aggfunc="first"
    )

    rows = []
    for region in sorted(piv.index):
        cvd0 = piv.loc[region].get(("Cerebrovascular", 2000), np.nan)
        cvd1 = piv.loc[region].get(("Cerebrovascular", 2024), np.nan)
        dem0 = piv.loc[region].get(("Dementia", 2000), np.nan)
        dem1 = piv.loc[region].get(("Dementia", 2024), np.nan)

        nn = n[
            (n["geography_level"] == "Region")
            & (n["geography"] == region)
            & (n["sex"] == "Both")
            & (n["year"].isin(YEARS))
        ].set_index("year")

        nti0 = nn["nti"].get(2000, np.nan)
        nti1 = nn["nti"].get(2024, np.nan)

        rows.append({
            "Region": region,
            "Cerebrovascular_ASMR_2000": cvd0,
            "Cerebrovascular_ASMR_2024": cvd1,
            "Cerebrovascular_pct_change_2000_2024": pct_change(cvd0, cvd1),
            "Dementia_ASMR_2000": dem0,
            "Dementia_ASMR_2024": dem1,
            "Dementia_pct_change_2000_2024": pct_change(dem0, dem1),
            "NTI_2000": nti0,
            "NTI_2024": nti1,
            "NTI_fold_change": np.nan if pd.isna(nti0) or nti0 == 0 else nti1/nti0,
        })

    out = pd.DataFrame(rows)
    out.to_csv(OUTDIR/"table4_regional_summary.csv", index=False)

    pretty = out.copy()
    for c in [
        "Cerebrovascular_ASMR_2000","Cerebrovascular_ASMR_2024",
        "Dementia_ASMR_2000","Dementia_ASMR_2024"
    ]:
        pretty[c] = pretty[c].map(lambda x: f"{x:.2f}")
    for c in [
        "Cerebrovascular_pct_change_2000_2024",
        "Dementia_pct_change_2000_2024"
    ]:
        pretty[c] = pretty[c].map(lambda x: f"{x:+.1f}%")
    for c in ["NTI_2000","NTI_2024"]:
        pretty[c] = pretty[c].map(lambda x: f"{x:.3f}")
    pretty["NTI_fold_change"] = pretty["NTI_fold_change"].map(lambda x: f"{x:.1f}×")
    pretty.to_csv(OUTDIR/"table4_regional_summary_pretty.csv", index=False)

    print("\nRegional summary — Both sexes")
    print(pretty.to_string(index=False))

    # Destaques automáticos para o abstract.
    i_nti = out["NTI_fold_change"].idxmax()
    i_dem = out["Dementia_pct_change_2000_2024"].idxmax()
    i_cvd = out["Cerebrovascular_pct_change_2000_2024"].idxmin()

    print("\nDestaques:")
    print(
        f"Maior aumento relativo do NTI: {out.loc[i_nti,'Region']} "
        f"({out.loc[i_nti,'NTI_2000']:.3f} → {out.loc[i_nti,'NTI_2024']:.3f}; "
        f"{out.loc[i_nti,'NTI_fold_change']:.1f}×)."
    )
    print(
        f"Maior aumento percentual da ASMR de demência: {out.loc[i_dem,'Region']} "
        f"({out.loc[i_dem,'Dementia_ASMR_2000']:.2f} → "
        f"{out.loc[i_dem,'Dementia_ASMR_2024']:.2f}; "
        f"{out.loc[i_dem,'Dementia_pct_change_2000_2024']:+.1f}%)."
    )
    print(
        f"Maior redução percentual da ASMR cerebrovascular: {out.loc[i_cvd,'Region']} "
        f"({out.loc[i_cvd,'Cerebrovascular_ASMR_2000']:.2f} → "
        f"{out.loc[i_cvd,'Cerebrovascular_ASMR_2024']:.2f}; "
        f"{out.loc[i_cvd,'Cerebrovascular_pct_change_2000_2024']:+.1f}%)."
    )

if __name__ == "__main__":
    main()
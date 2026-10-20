#!/usr/bin/env python3
"""Gera tabelas e figuras preliminares do Artigo 2 após as análises principais."""
from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt

OUT = Path("outputs/article2")
FIG = OUT/"figures"; TAB=OUT/"tables"


def main():
    rates_p=OUT/"article2_standardized_rates.csv"
    nti_p=OUT/"article2_nti.csv"
    dec_p=OUT/"article2_decomposition.csv"
    if not all(p.exists() for p in [rates_p,nti_p,dec_p]):
        sys.exit("Execute 06_article2_rates.py e 08_article2_decomposition.py antes.")
    FIG.mkdir(parents=True,exist_ok=True); TAB.mkdir(parents=True,exist_ok=True)
    r=pd.read_csv(rates_p); n=pd.read_csv(nti_p); d=pd.read_csv(dec_p)
    nat=r[(r.geography_level=="Brazil")&(r.geography=="Brazil")&(r.sex=="Both")]

    # Table 1 — selected years
    sel=nat[nat.year.isin([2000,2010,2019,2024]) & nat.cause.isin(["Cerebrovascular","Dementia","Alzheimer","Parkinson"])].copy()
    sel[["year","cause","deaths","crude_rate_per_100k","asmr_per_100k","asmr_lcl95","asmr_ucl95","unknown_age_pct"]].to_csv(TAB/"table1_selected_years.csv",index=False)

    # Figure 1
    fig,ax=plt.subplots(figsize=(8,5))
    for cause in ["Cerebrovascular","Dementia"]:
        x=nat[nat.cause==cause].sort_values("year")
        ax.plot(x.year,x.asmr_per_100k,marker="o",markersize=2,label=cause)
    ax.set_xlabel("Year"); ax.set_ylabel("Age-standardized mortality rate per 100,000")
    ax.set_title("Cerebrovascular and dementia-related mortality in Brazil, 2000–2024")
    ax.legend(); fig.tight_layout(); fig.savefig(FIG/"figure1_trajectories.png",dpi=300); plt.close(fig)

    # Figure 2
    x=n[(n.geography_level=="Brazil")&(n.geography=="Brazil")&(n.sex=="Both")].sort_values("year")
    fig,ax=plt.subplots(figsize=(8,5)); ax.plot(x.year,x.nti,marker="o",markersize=2)
    ax.axhline(1,linestyle="--",linewidth=1); ax.set_xlabel("Year"); ax.set_ylabel("NTI (dementia ASMR / cerebrovascular ASMR)")
    ax.set_title("Neuroepidemiological Transition Index in Brazil, 2000–2024")
    fig.tight_layout(); fig.savefig(FIG/"figure2_nti.png",dpi=300); plt.close(fig)

    # Figure 3 — decomposition 2000–2024, Both
    z=d[(d.sex=="Both")&(d.year0==2000)&(d.year1==2024)&d.cause.isin(["Cerebrovascular","Dementia","Alzheimer","Parkinson"])].copy()
    z=z.set_index("cause")[["population_growth_contribution","population_ageing_contribution","mortality_rate_change_contribution"]]
    ax=z.plot(kind="bar",figsize=(9,5)); ax.set_xlabel(""); ax.set_ylabel("Contribution to change in number of deaths")
    ax.set_title("Decomposition of neurological mortality change, Brazil, 2000–2024")
    plt.tight_layout(); plt.savefig(FIG/"figure3_decomposition.png",dpi=300); plt.close()
    print("Tabelas/figuras preliminares geradas em", OUT.resolve())

if __name__=="__main__": main()
#!/usr/bin/env python3
"""
Decomposição Shapley exata da mudança de mortes em três componentes:
1) population growth; 2) population ageing; 3) age-specific mortality-rate change.

D = N * sum_a(s_a * r_a)

A contribuição de cada fator é a média do seu efeito marginal nas 3! ordens
possíveis de substituição dos valores do ano inicial pelos do ano final.
"""
from pathlib import Path
from itertools import permutations
import sys
import numpy as np
import pandas as pd
try:
    import duckdb
except ImportError:
    duckdb = None

AGE_RATES = Path("data/processed/article2_age_specific_rates.parquet")
OUT = Path("outputs/article2")
EXPECTED_AGES = [f"{a:02d}-{a+4:02d}" for a in range(0,90,5)] + ["90+"]
CAUSES = ["Cerebrovascular","Dementia","Alzheimer","Parkinson"]
COMPARISONS = [(2000,2024),(2000,2010),(2010,2019),(2019,2024)]
FACTORS = ["growth","ageing","rate_change"]


def load():
    con=duckdb.connect(); return con.execute("SELECT * FROM read_parquet(?)", [str(AGE_RATES)]).df()


def outcome(N, S, R):
    return float(N * np.dot(S, R))


def shapley_decompose(N0,S0,R0,N1,S1,R1):
    base = {"growth":N0, "ageing":S0, "rate_change":R0}
    final = {"growth":N1, "ageing":S1, "rate_change":R1}
    contrib = {f:0.0 for f in FACTORS}
    for perm in permutations(FACTORS):
        state = dict(base)
        before = outcome(state["growth"],state["ageing"],state["rate_change"])
        for f in perm:
            state[f] = final[f]
            after = outcome(state["growth"],state["ageing"],state["rate_change"])
            contrib[f] += after-before
            before = after
    for f in contrib:
        contrib[f] /= 6.0
    return contrib


def vector_for(d, year, cause, sex):
    x = d[(d.year==year)&(d.cause==cause)&(d.sex==sex)].copy()
    x = x.set_index("age_std_group").reindex(EXPECTED_AGES)
    if x[["deaths","population"]].isna().any().any():
        raise ValueError(f"Estrato incompleto: year={year}, cause={cause}, sex={sex}")
    pop = x["population"].to_numpy(float)
    deaths = x["deaths"].to_numpy(float)
    N = pop.sum()
    S = pop/N
    R = deaths/pop
    return N,S,R,float(deaths.sum())


def main():
    if not AGE_RATES.exists(): sys.exit("Execute primeiro: python 06_article2_rates.py")
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()
    d = d[(d.geography_level=="Brazil") & (d.geography=="Brazil")]
    rows=[]
    for cause in CAUSES:
        for sex in ["Both","Male","Female"]:
            for y0,y1 in COMPARISONS:
                N0,S0,R0,D0 = vector_for(d,y0,cause,sex)
                N1,S1,R1,D1 = vector_for(d,y1,cause,sex)
                c = shapley_decompose(N0,S0,R0,N1,S1,R1)
                net = D1-D0
                residual = net-sum(c.values())
                row = {
                    "cause":cause,"sex":sex,"year0":y0,"year1":y1,
                    "population0":N0,"population1":N1,
                    "known_age_deaths0":D0,"known_age_deaths1":D1,
                    "net_change_deaths":net,
                    "population_growth_contribution":c["growth"],
                    "population_ageing_contribution":c["ageing"],
                    "mortality_rate_change_contribution":c["rate_change"],
                    "decomposition_residual":residual,
                }
                for key,col in [
                    ("population_growth_contribution","population_growth_pct_net"),
                    ("population_ageing_contribution","population_ageing_pct_net"),
                    ("mortality_rate_change_contribution","mortality_rate_change_pct_net"),
                ]:
                    row[col] = np.nan if abs(net)<1e-12 else 100*row[key]/net
                rows.append(row)
    out = pd.DataFrame(rows)
    if out["decomposition_residual"].abs().max() > 1e-6:
        sys.exit("Erro: decomposição não reconstruiu exatamente a mudança de mortes.")
    out.to_csv(OUT/"article2_decomposition.csv", index=False)

    long = out.melt(
        id_vars=["cause","sex","year0","year1","net_change_deaths"],
        value_vars=["population_growth_contribution","population_ageing_contribution","mortality_rate_change_contribution"],
        var_name="component", value_name="contribution_deaths"
    )
    long.to_csv(OUT/"article2_decomposition_long.csv", index=False)
    print("Decomposição concluída:", (OUT/"article2_decomposition.csv").resolve())

if __name__ == "__main__":
    main()
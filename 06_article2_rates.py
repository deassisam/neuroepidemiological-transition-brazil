#!/usr/bin/env python3
"""
Artigo 2 — taxas específicas, taxas padronizadas WHO 2000–2025 e NTI.

Entradas:
  data/processed/article2_underlying_counts_2000_2024.parquet
  data/processed/ibge_population_all_geographies_2000_2024.parquet

Saídas principais:
  data/processed/article2_age_specific_rates.parquet
  outputs/article2/article2_standardized_rates.csv
  outputs/article2/article2_nti.csv
  outputs/qc/article2_rate_denominator_qc.csv
"""
from pathlib import Path
import math
import sys

try:
    import duckdb
except ImportError:
    duckdb = None
import numpy as np
import pandas as pd

DEATHS = Path("data/processed/article2_underlying_counts_2000_2024.parquet")
POP = Path("data/processed/ibge_population_all_geographies_2000_2024.parquet")
OUTDIR = Path("outputs/article2")
QC_DIR = Path("outputs/qc")
AGE_OUT = Path("data/processed/article2_age_specific_rates.parquet")

UF_CODE = {
  11:"RO",12:"AC",13:"AM",14:"RR",15:"PA",16:"AP",17:"TO",
  21:"MA",22:"PI",23:"CE",24:"RN",25:"PB",26:"PE",27:"AL",28:"SE",29:"BA",
  31:"MG",32:"ES",33:"RJ",35:"SP",41:"PR",42:"SC",43:"RS",
  50:"MS",51:"MT",52:"GO",53:"DF"
}
EXPECTED_AGES = [f"{a:02d}-{a+4:02d}" for a in range(0,90,5)] + ["90+"]

# WHO World Standard 2000–2025 (%). A faixa terminal do IBGE é 90+;
# portanto 90–94, 95–99 e 100+ são agregados: 0.15 + 0.04 + 0.005 = 0.195.
WHO_RAW = {
 "00-04":8.86, "05-09":8.69, "10-14":8.60, "15-19":8.47,
 "20-24":8.22, "25-29":7.93, "30-34":7.61, "35-39":7.15,
 "40-44":6.59, "45-49":6.04, "50-54":5.37, "55-59":4.55,
 "60-64":3.72, "65-69":2.96, "70-74":2.21, "75-79":1.52,
 "80-84":0.91, "85-89":0.44, "90+":0.195,
}
WHO_SUM = sum(WHO_RAW.values())
WHO = {k: v/WHO_SUM for k,v in WHO_RAW.items()}  # normaliza arredondamentos publicados

CAUSE_COLS = {
 "Cerebrovascular":"cerebrovascular_deaths",
 "Ischemic_stroke":"ischemic_stroke_deaths",
 "Intracerebral_hemorrhage":"ich_deaths",
 "Dementia":"dementia_deaths",
 "Alzheimer":"alzheimer_deaths",
 "Vascular_dementia":"vascular_dementia_deaths",
 "Parkinson":"parkinson_deaths",
 "Ill_defined":"ill_defined_deaths",
}


def load_parquet(path):
    con = duckdb.connect()
    return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()


def harmonize_age(x):
    if pd.isna(x): return "Unknown"
    s = str(x)
    if s in {"90-94","95-99","100+"}: return "90+"
    return s


def geography_aggregates(d):
    d = d.copy()
    d["uf"] = pd.to_numeric(d["uf_code"], errors="coerce").map(UF_CODE)
    value_cols = list(CAUSE_COLS.values())
    # Sensibilidade: demência exceto demência vascular.
    d["dementia_excluding_vascular_deaths"] = (
        d["dementia_deaths"] - d["vascular_dementia_deaths"]
    ).clip(lower=0)
    value_cols.append("dementia_excluding_vascular_deaths")

    pieces = []
    for level, geo_col, subset in [
        ("Brazil", None, d),
        ("Region", "region", d[d["region"].notna()]),
        ("UF", "uf", d[d["uf"].notna()]),
    ]:
        # Ambos os sexos: inclui óbitos com sexo desconhecido.
        group = ["year","age_std_group"] + ([] if geo_col is None else [geo_col])
        b = subset.groupby(group, as_index=False, dropna=False)[value_cols].sum()
        b["sex"] = "Both"
        b["geography_level"] = level
        b["geography"] = "Brazil" if geo_col is None else b[geo_col]
        pieces.append(b[["year","age_std_group","sex","geography_level","geography"]+value_cols])

        # Sexos específicos: somente Male/Female.
        ss = subset[subset["sex"].isin(["Male","Female"])]
        group = ["year","age_std_group","sex"] + ([] if geo_col is None else [geo_col])
        s = ss.groupby(group, as_index=False, dropna=False)[value_cols].sum()
        s["geography_level"] = level
        s["geography"] = "Brazil" if geo_col is None else s[geo_col]
        pieces.append(s[["year","age_std_group","sex","geography_level","geography"]+value_cols])
    return pd.concat(pieces, ignore_index=True)


def melt_causes(wide):
    cmap = dict(CAUSE_COLS)
    cmap["Dementia_excluding_vascular"] = "dementia_excluding_vascular_deaths"
    inv = {v:k for k,v in cmap.items()}
    out = wide.melt(
        id_vars=["year","age_std_group","sex","geography_level","geography"],
        value_vars=list(inv), var_name="cause_col", value_name="deaths"
    )
    out["cause"] = out["cause_col"].map(inv)
    return out.drop(columns="cause_col")


def save_parquet(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.register("df", df)
    con.execute(f"COPY df TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def main():
    for p in [DEATHS, POP]:
        if not p.exists(): sys.exit(f"Entrada ausente: {p}")
    OUTDIR.mkdir(parents=True, exist_ok=True); QC_DIR.mkdir(parents=True, exist_ok=True)

    d = load_parquet(DEATHS)
    d["age_std_group"] = d["age_group5"].map(harmonize_age)
    dw = geography_aggregates(d)
    dl = melt_causes(dw)

    pop = load_parquet(POP)
    pop = pop[["year","geography_level","geography","sex","age_group5","population"]].copy()

    # Totais de mortes incluindo idade desconhecida para taxa bruta/QC.
    totals = dl.groupby(["year","geography_level","geography","sex","cause"], as_index=False)["deaths"].sum()
    unknown = dl[dl["age_std_group"].eq("Unknown")].groupby(
        ["year","geography_level","geography","sex","cause"], as_index=False
    )["deaths"].sum().rename(columns={"deaths":"unknown_age_deaths"})

    known = dl[dl["age_std_group"].isin(EXPECTED_AGES)].copy()

    # Usa o denominador IBGE como grade mestra. Se uma causa tiver zero mortes em um
    # estrato, o estrato permanece na padronização com deaths=0 em vez de desaparecer.
    causes = pd.DataFrame({"cause": sorted(known["cause"].unique())})
    pop_grid = pop.rename(columns={"age_group5":"age_std_group"}).copy()
    pop_grid["_k"] = 1; causes["_k"] = 1
    pop_grid = pop_grid.merge(causes, on="_k", how="inner").drop(columns="_k")
    merged = pop_grid.merge(
        known,
        on=["year","geography_level","geography","sex","age_std_group","cause"],
        how="left", validate="one_to_one"
    )
    merged["deaths"] = merged["deaths"].fillna(0.0)
    if (merged["population"] <= 0).any(): sys.exit("Denominador populacional <=0.")

    merged["who_weight"] = merged["age_std_group"].map(WHO)
    if merged["who_weight"].isna().any(): sys.exit("Grupo etário sem peso WHO.")
    merged["age_specific_rate_per_100k"] = merged["deaths"] / merged["population"] * 100000.0
    save_parquet(merged, AGE_OUT)

    group = ["year","geography_level","geography","sex","cause"]
    def summarize(g):
        # Todas as 19 idades devem estar presentes. Death counts zero ainda aparecem porque
        # a base agregada do SIM possui os estratos; o denominador é obrigatório.
        weights = g["who_weight"].to_numpy(float)
        death = g["deaths"].to_numpy(float)
        popv = g["population"].to_numpy(float)
        rate = death/popv
        asmr = float(np.sum(weights * rate) * 100000.0)
        var = float(np.sum((weights**2) * death/(popv**2)) * (100000.0**2))
        se = math.sqrt(max(var,0.0))
        return pd.Series({
            "asmr_per_100k": asmr,
            "asmr_se": se,
            "asmr_lcl95": max(0.0, asmr-1.96*se),
            "asmr_ucl95": asmr+1.96*se,
            "known_age_deaths": float(death.sum()),
            "population_age_sum": float(popv.sum()),
            "n_age_groups": int(g["age_std_group"].nunique()),
        })
    rates = merged.groupby(group, dropna=False).apply(summarize, include_groups=False).reset_index()

    pop_total = pop.groupby(["year","geography_level","geography","sex"], as_index=False)["population"].sum()
    rates = rates.merge(totals, on=group, how="left").merge(unknown, on=group, how="left")
    rates = rates.merge(pop_total, on=["year","geography_level","geography","sex"], how="left")
    rates["deaths"] = rates["deaths"].fillna(0)
    rates["unknown_age_deaths"] = rates["unknown_age_deaths"].fillna(0)
    rates["crude_rate_per_100k"] = rates["deaths"] / rates["population"] * 100000.0
    rates["unknown_age_pct"] = np.where(rates["deaths"]>0, 100*rates["unknown_age_deaths"]/rates["deaths"], 0.0)

    bad = rates[rates["n_age_groups"] != len(EXPECTED_AGES)]
    qc = rates[["year","geography_level","geography","sex","cause","n_age_groups","deaths","unknown_age_deaths","unknown_age_pct","population"]]
    qc.to_csv(QC_DIR/"article2_rate_denominator_qc.csv", index=False)
    if not bad.empty:
        print(bad.head(30).to_string(index=False))
        sys.exit("Algumas séries não contêm os 19 grupos etários esperados.")

    rates = rates.sort_values(["geography_level","geography","sex","cause","year"])
    rates.to_csv(OUTDIR/"article2_standardized_rates.csv", index=False)

    # Neuroepidemiological Transition Index = ASMR dementia / ASMR cerebrovascular.
    sub = rates[rates["cause"].isin(["Dementia","Cerebrovascular"])].copy()
    piv = sub.pivot(index=["year","geography_level","geography","sex"], columns="cause", values=["asmr_per_100k","asmr_se"]).reset_index()
    piv.columns = ["_".join([str(x) for x in c if str(x)]) if isinstance(c, tuple) else c for c in piv.columns]
    piv = piv.rename(columns={
        "asmr_per_100k_Dementia":"dementia_asmr",
        "asmr_per_100k_Cerebrovascular":"cerebrovascular_asmr",
        "asmr_se_Dementia":"dementia_se",
        "asmr_se_Cerebrovascular":"cerebrovascular_se",
    })
    ok = (piv["dementia_asmr"]>0) & (piv["cerebrovascular_asmr"]>0)
    piv["nti"] = np.where(ok, piv["dementia_asmr"]/piv["cerebrovascular_asmr"], np.nan)
    relse = np.sqrt((piv["dementia_se"]/piv["dementia_asmr"])**2 + (piv["cerebrovascular_se"]/piv["cerebrovascular_asmr"])**2)
    piv["nti_se"] = piv["nti"] * relse
    piv["log_nti"] = np.log(piv["nti"])
    piv["log_nti_se"] = relse
    piv["nti_lcl95"] = np.exp(piv["log_nti"] - 1.96*piv["log_nti_se"])
    piv["nti_ucl95"] = np.exp(piv["log_nti"] + 1.96*piv["log_nti_se"])
    piv.to_csv(OUTDIR/"article2_nti.csv", index=False)

    nat = rates[(rates.geography_level=="Brazil") & (rates.geography=="Brazil") & (rates.sex=="Both")]
    print("Taxas calculadas com sucesso.")
    for cause in ["Cerebrovascular","Dementia","Alzheimer","Parkinson"]:
        x = nat[(nat.cause==cause) & (nat.year.isin([2000,2024]))][["year","asmr_per_100k"]]
        print("\n", cause); print(x.to_string(index=False))
    print("\nWHO raw weights sum =", WHO_SUM, "; normalized to 1.0 before ASMR.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Cria entradas enxutas para os dois artigos SEM testar as hipóteses.

Artigo 1:
  all deaths age >=60, mantendo flags de qualquer menção.

Artigo 2:
  contagens por ano/sexo/idade/região usando exclusivamente causa básica.
  Ainda NÃO calcula taxas: denominadores por idade/sexo do IBGE entram depois.
"""
from pathlib import Path
import duckdb
import sys

MASTER = Path("data/processed/sim_master_2000_2024.parquet")
OUTDIR = Path("data/processed")
A1 = OUTDIR / "article1_all_deaths_60plus_2000_2024.parquet"
A2 = OUTDIR / "article2_underlying_counts_2000_2024.parquet"

A1_FLAGS = [
    "any_ad", "any_dementia", "any_vascular_dementia", "any_parkinson",
    "any_cerebrovascular", "any_ischemic_stroke", "any_intracerebral_hemorrhage",
    "any_hypertension", "any_ischemic_heart_disease", "any_atrial_fibrillation",
    "any_heart_failure", "any_atherosclerosis", "any_diabetes", "any_obesity",
    "any_lipoprotein_disorder", "any_ckd", "any_copd", "any_pneumonia",
    "any_respiratory_failure", "any_sepsis", "any_malignant_neoplasm",
    "any_covid19", "any_ill_defined"
]

def main():
    if not MASTER.exists():
        sys.exit("Base-mãe ausente. Execute 02_build_sim_master.py.")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    flag_sql = ", ".join(A1_FLAGS)
    con.execute(f"""
      COPY (
        SELECT
          year, period5, age_years, age_group4, age_group5,
          sex, race_color, education_raw, education2010_raw,
          municipality_residence, uf_code, region,
          underlying_cause, n_causes,
          {flag_sql}
        FROM read_parquet('{MASTER.as_posix()}')
        WHERE age_years >= 60
      ) TO '{A1.as_posix()}'
      (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000);
    """)

    con.execute(f"""
      COPY (
        SELECT
          year, sex, age_group5, age_group4, uf_code, region,
          count(*) AS all_deaths,
          sum(uc_cerebrovascular)::BIGINT AS cerebrovascular_deaths,
          sum(uc_ischemic_stroke)::BIGINT AS ischemic_stroke_deaths,
          sum(uc_intracerebral_hemorrhage)::BIGINT AS ich_deaths,
          sum(uc_dementia)::BIGINT AS dementia_deaths,
          sum(uc_ad)::BIGINT AS alzheimer_deaths,
          sum(uc_vascular_dementia)::BIGINT AS vascular_dementia_deaths,
          sum(uc_parkinson)::BIGINT AS parkinson_deaths,
          sum(uc_ill_defined)::BIGINT AS ill_defined_deaths
        FROM read_parquet('{MASTER.as_posix()}')
        GROUP BY year, sex, age_group5, age_group4, uf_code, region
        ORDER BY year, sex, age_group5, uf_code
      ) TO '{A2.as_posix()}'
      (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    n1 = con.execute("SELECT count(*) FROM read_parquet(?)", [str(A1)]).fetchone()[0]
    n2 = con.execute("SELECT count(*) FROM read_parquet(?)", [str(A2)]).fetchone()[0]
    print(f"Artigo 1: {A1.resolve()} ({n1:,} linhas)")
    print(f"Artigo 2: {A2.resolve()} ({n2:,} linhas agregadas)")
    print("Nenhuma hipótese principal foi testada.")

if __name__ == "__main__":
    main()
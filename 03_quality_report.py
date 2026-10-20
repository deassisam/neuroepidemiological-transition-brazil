#!/usr/bin/env python3
"""
Gera relatório de qualidade antes de abrir as análises principais.
"""
from pathlib import Path
import duckdb
import sys

MASTER = Path("data/processed/sim_master_2000_2024.parquet")
OUT = Path("outputs/qc")
OUT.mkdir(parents=True, exist_ok=True)

def main():
    if not MASTER.exists():
        sys.exit("Base-mãe ausente. Execute: python 02_build_sim_master.py")

    con = duckdb.connect()

    annual_csv = OUT / "quality_by_year.csv"
    con.execute(f"""
    COPY (
      SELECT
        year,
        count(*) AS deaths,
        sum(age_years IS NULL)::BIGINT AS age_unknown_n,
        100.0 * avg((age_years IS NULL)::INTEGER) AS age_unknown_pct,
        sum(sex IS NULL)::BIGINT AS sex_unknown_n,
        100.0 * avg((sex IS NULL)::INTEGER) AS sex_unknown_pct,
        sum(race_color IS NULL)::BIGINT AS race_unknown_n,
        100.0 * avg((race_color IS NULL)::INTEGER) AS race_unknown_pct,
        sum(region IS NULL)::BIGINT AS region_unknown_n,
        100.0 * avg((region IS NULL)::INTEGER) AS region_unknown_pct,
        avg(n_causes) AS mean_number_causes,
        median(n_causes) AS median_number_causes,
        sum(uc_ill_defined)::BIGINT AS ill_defined_uc_n,
        100.0 * avg(uc_ill_defined::INTEGER) AS ill_defined_uc_pct,
        sum(any_ad)::BIGINT AS alzheimer_any_mention_n,
        sum(uc_ad)::BIGINT AS alzheimer_underlying_n,
        sum(uc_dementia)::BIGINT AS dementia_underlying_n,
        sum(uc_cerebrovascular)::BIGINT AS cerebrovascular_underlying_n,
        sum(uc_parkinson)::BIGINT AS parkinson_underlying_n
      FROM read_parquet('{MASTER.as_posix()}')
      GROUP BY year
      ORDER BY year
    ) TO '{annual_csv.as_posix()}' (HEADER, DELIMITER ',');
    """)

    period_csv = OUT / "quality_by_period.csv"
    con.execute(f"""
    COPY (
      SELECT
        period5,
        count(*) AS deaths,
        round(avg(n_causes),3) AS mean_number_causes,
        round(100.0 * avg((age_years IS NULL)::INTEGER),3) AS age_unknown_pct,
        round(100.0 * avg((sex IS NULL)::INTEGER),3) AS sex_unknown_pct,
        round(100.0 * avg((region IS NULL)::INTEGER),3) AS region_unknown_pct,
        round(100.0 * avg(uc_ill_defined::INTEGER),3) AS ill_defined_uc_pct
      FROM read_parquet('{MASTER.as_posix()}')
      GROUP BY period5
      ORDER BY period5
    ) TO '{period_csv.as_posix()}' (HEADER, DELIMITER ',');
    """)

    totals = con.execute(f"""
      SELECT
        count(*) AS n,
        min(year), max(year),
        sum(any_ad)::BIGINT,
        sum(uc_dementia)::BIGINT,
        sum(uc_cerebrovascular)::BIGINT
      FROM read_parquet('{MASTER.as_posix()}')
    """).fetchone()

    summary = OUT / "qc_summary.txt"
    summary.write_text(
        "SIM 2000–2024 — QC inicial\n"
        "==========================\n"
        f"Registros: {totals[0]:,}\n"
        f"Período: {totals[1]}–{totals[2]}\n"
        f"Alzheimer em qualquer menção: {totals[3]:,}\n"
        f"Demência como causa básica: {totals[4]:,}\n"
        f"Doença cerebrovascular como causa básica: {totals[5]:,}\n\n"
        "Antes de qualquer teste de hipótese, comparar os totais anuais com "
        "TABNET/DATASUS e inspecionar quality_by_year.csv.\n",
        encoding="utf-8"
    )

    print("Relatórios gerados:")
    print(" ", annual_csv.resolve())
    print(" ", period_csv.resolve())
    print(" ", summary.resolve())

if __name__ == "__main__":
    main()
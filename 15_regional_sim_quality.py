#!/usr/bin/env python3
"""
Reviewer-response analysis: regional SIM data-quality indicators, Brazil, 2000–2024.

Input (project root):
  data/processed/sim_master_2000_2024.parquet

Outputs:
  outputs/article2/reviewer_revision/Supplementary_Table_S6_regional_SIM_quality.csv
  outputs/article2/reviewer_revision/Supplementary_Table_S6_regional_SIM_quality_pretty.csv
  outputs/article2/reviewer_revision/regional_SIM_quality_residence_QC.csv

The table quantifies by Brazilian macro-region and 5-year period:
  - deaths, n
  - mean number of distinct causes recorded per certificate
  - unknown age, %
  - unknown sex, %
  - ill-defined underlying cause (ICD-10 R00-R99), %

A Brazil total is included for direct reconciliation with the original national quality table.
"""
from pathlib import Path
import sys
import duckdb
import pandas as pd

INFILE = Path("data/processed/sim_master_2000_2024.parquet")
OUTDIR = Path("outputs/article2/reviewer_revision")
REGION_ORDER = ["North", "Northeast", "Central-West", "Southeast", "South"]
PERIOD_ORDER = ["2000–2004", "2005–2009", "2010–2014", "2015–2019", "2020–2024"]


def period_expr():
    return """
    CASE
      WHEN year BETWEEN 2000 AND 2004 THEN '2000–2004'
      WHEN year BETWEEN 2005 AND 2009 THEN '2005–2009'
      WHEN year BETWEEN 2010 AND 2014 THEN '2010–2014'
      WHEN year BETWEEN 2015 AND 2019 THEN '2015–2019'
      WHEN year BETWEEN 2020 AND 2024 THEN '2020–2024'
    END
    """


def main():
    if not INFILE.exists():
        sys.exit(f"Missing required file: {INFILE}\nRun this script from the neuroepidemiologia_sim_pipeline project root.")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")

    cols = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(INFILE)]).fetchall()}
    required = {"year", "region", "age_years", "sex", "uc_ill_defined", "n_causes"}
    missing = sorted(required - cols)
    if missing:
        sys.exit("Missing required columns in sim_master: " + ", ".join(missing))

    pexpr = period_expr()
    regional = con.execute(f"""
        SELECT
          region AS Region,
          {pexpr} AS Period,
          count(*)::BIGINT AS Deaths_n,
          avg(n_causes)::DOUBLE AS Mean_causes_per_certificate,
          100.0 * avg(CASE WHEN age_years IS NULL THEN 1 ELSE 0 END)::DOUBLE AS Unknown_age_pct,
          100.0 * avg(CASE WHEN sex IS NULL THEN 1 ELSE 0 END)::DOUBLE AS Unknown_sex_pct,
          100.0 * avg(CASE WHEN uc_ill_defined THEN 1 ELSE 0 END)::DOUBLE AS Ill_defined_uc_pct
        FROM read_parquet(?)
        WHERE year BETWEEN 2000 AND 2024
          AND region IN ('North','Northeast','Central-West','Southeast','South')
        GROUP BY 1,2
    """, [str(INFILE)]).df()

    brazil = con.execute(f"""
        SELECT
          'Brazil' AS Region,
          {pexpr} AS Period,
          count(*)::BIGINT AS Deaths_n,
          avg(n_causes)::DOUBLE AS Mean_causes_per_certificate,
          100.0 * avg(CASE WHEN age_years IS NULL THEN 1 ELSE 0 END)::DOUBLE AS Unknown_age_pct,
          100.0 * avg(CASE WHEN sex IS NULL THEN 1 ELSE 0 END)::DOUBLE AS Unknown_sex_pct,
          100.0 * avg(CASE WHEN uc_ill_defined THEN 1 ELSE 0 END)::DOUBLE AS Ill_defined_uc_pct
        FROM read_parquet(?)
        WHERE year BETWEEN 2000 AND 2024
        GROUP BY 2
    """, [str(INFILE)]).df()

    qc = con.execute(f"""
        SELECT
          {pexpr} AS Period,
          count(*)::BIGINT AS Deaths_total,
          sum(CASE WHEN region IS NULL THEN 1 ELSE 0 END)::BIGINT AS Missing_region_n,
          100.0 * avg(CASE WHEN region IS NULL THEN 1 ELSE 0 END)::DOUBLE AS Missing_region_pct
        FROM read_parquet(?)
        WHERE year BETWEEN 2000 AND 2024
        GROUP BY 1
    """, [str(INFILE)]).df()

    out = pd.concat([regional, brazil], ignore_index=True)
    out["_r"] = pd.Categorical(out["Region"], categories=REGION_ORDER + ["Brazil"], ordered=True)
    out["_p"] = pd.Categorical(out["Period"], categories=PERIOD_ORDER, ordered=True)
    out = out.sort_values(["_r", "_p"]).drop(columns=["_r", "_p"])

    # Internal reconciliation check: Brazil totals must match the known five-year death totals.
    frozen = {
        "2000–2004": 4916899,
        "2005–2009": 5266437,
        "2010–2014": 5926124,
        "2015–2019": 6553132,
        "2020–2024": 7931364,
    }
    got = dict(zip(brazil["Period"], brazil["Deaths_n"].astype(int)))
    bad = {k: (frozen[k], got.get(k)) for k in frozen if got.get(k) != frozen[k]}
    if bad:
        raise AssertionError(f"Brazil total reconciliation failed: {bad}")

    raw_path = OUTDIR / "Supplementary_Table_S6_regional_SIM_quality.csv"
    pretty_path = OUTDIR / "Supplementary_Table_S6_regional_SIM_quality_pretty.csv"
    qc_path = OUTDIR / "regional_SIM_quality_residence_QC.csv"

    out.to_csv(raw_path, index=False)
    pretty = out.copy()
    pretty["Deaths_n"] = pretty["Deaths_n"].map(lambda x: f"{int(x):,}")
    for c in ["Mean_causes_per_certificate", "Unknown_age_pct", "Unknown_sex_pct", "Ill_defined_uc_pct"]:
        pretty[c] = pretty[c].map(lambda x: f"{x:.3f}")
    pretty.to_csv(pretty_path, index=False)
    qc.to_csv(qc_path, index=False)

    print("Regional SIM quality analysis completed.")
    print(f"Saved: {raw_path}")
    print(f"Saved: {pretty_path}")
    print(f"Saved: {qc_path}")
    print("\nBrazil reconciliation:")
    print(brazil.sort_values("Period").to_string(index=False))
    print("\nResidence-region QC:")
    print(qc.sort_values("Period").to_string(index=False))


if __name__ == "__main__":
    main()
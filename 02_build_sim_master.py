#!/usr/bin/env python3
"""
Constrói a base-mãe SIM 2000–2024 para os dois artigos.

Saída:
  data/processed/sim_master_2000_2024.parquet

Princípios:
- DuckDB lê o Parquet diretamente; não carrega tudo em pandas/RAM.
- Exclui óbitos fetais se TIPOBITO estiver disponível.
- Mantém idades desconhecidas (necessárias para QC), mas decodifica idade em anos.
- Gera flags de CAUSA BÁSICA e de QUALQUER MENÇÃO separadamente.
- Gera n_causes = número de códigos CID-10 distintos nas linhas da DO.
"""
from pathlib import Path
import duckdb
import sys

INFILE_NAME = "declaracoes_de_obito_cid10.parquet"
OUTFILE = Path("data/processed/sim_master_2000_2024.parquet")
START_YEAR = 2000
END_YEAR = 2024

# ICD-10: regex aplicadas após remoção de ponto e conversão para maiúsculas.
ICD = {
    "ad": r"(G30|F00)[0-9A-Z]?",
    "dementia": r"(F0[0-3]|G30)[0-9A-Z]?",
    "vascular_dementia": r"F01[0-9A-Z]?",
    "parkinson": r"G20[0-9A-Z]?",
    "cerebrovascular": r"I6[0-9][0-9A-Z]?",
    "ischemic_stroke": r"I63[0-9A-Z]?",
    "intracerebral_hemorrhage": r"I61[0-9A-Z]?",
    "hypertension": r"I1[0-5][0-9A-Z]?",
    "ischemic_heart_disease": r"I2[0-5][0-9A-Z]?",
    "atrial_fibrillation": r"I48[0-9A-Z]?",
    "heart_failure": r"I50[0-9A-Z]?",
    "atherosclerosis": r"I70[0-9A-Z]?",
    "diabetes": r"E1[0-4][0-9A-Z]?",
    "obesity": r"E66[0-9A-Z]?",
    "lipoprotein_disorder": r"E78[0-9A-Z]?",
    "ckd": r"N18[0-9A-Z]?",
    "copd": r"J4[0-4][0-9A-Z]?",
    "pneumonia": r"J1[2-8][0-9A-Z]?",
    "respiratory_failure": r"J96[0-9A-Z]?",
    "sepsis": r"A4[01][0-9A-Z]?",
    "malignant_neoplasm": r"(C[0-8][0-9]|C9[0-7])[0-9A-Z]?",
    "covid19": r"U07[12]",
    "ill_defined": r"R[0-9]{2}[0-9A-Z]?",
}

UF_REGION = """
CASE uf_code
  WHEN 11 THEN 'North' WHEN 12 THEN 'North' WHEN 13 THEN 'North'
  WHEN 14 THEN 'North' WHEN 15 THEN 'North' WHEN 16 THEN 'North'
  WHEN 17 THEN 'North'
  WHEN 21 THEN 'Northeast' WHEN 22 THEN 'Northeast' WHEN 23 THEN 'Northeast'
  WHEN 24 THEN 'Northeast' WHEN 25 THEN 'Northeast' WHEN 26 THEN 'Northeast'
  WHEN 27 THEN 'Northeast' WHEN 28 THEN 'Northeast' WHEN 29 THEN 'Northeast'
  WHEN 31 THEN 'Southeast' WHEN 32 THEN 'Southeast'
  WHEN 33 THEN 'Southeast' WHEN 35 THEN 'Southeast'
  WHEN 41 THEN 'South' WHEN 42 THEN 'South' WHEN 43 THEN 'South'
  WHEN 50 THEN 'Central-West' WHEN 51 THEN 'Central-West'
  WHEN 52 THEN 'Central-West' WHEN 53 THEN 'Central-West'
  ELSE NULL
END
"""

def locate():
    hits = list(Path("data/raw").rglob(INFILE_NAME))
    if not hits:
        sys.exit(
            f"Não encontrei {INFILE_NAME} em data/raw.\n"
            "Execute: python 00_download_sim.py"
        )
    return hits[0]

def q(name):
    return '"' + name.replace('"', '""') + '"'

def get_columns(con, path):
    rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    return {r[0].upper(): r[0] for r in rows}

def col(cols, name, default="NULL"):
    actual = cols.get(name.upper())
    return q(actual) if actual else default

def clean_expr(expr):
    return f"upper(replace(coalesce(CAST({expr} AS VARCHAR), ''), '.', ''))"

def bounded_regex(regex):
    return rf"(^|[^A-Z0-9]){regex}([^A-Z0-9]|$)"

def flag_from_blob(name, regex):
    return f"regexp_matches(cause_blob, '{bounded_regex(regex)}') AS any_{name}"

def flag_from_uc(name, regex):
    return f"regexp_matches(underlying_cause, '^{regex}$') AS uc_{name}"

def main():
    infile = locate()
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA preserve_insertion_order=false")

    cols = get_columns(con, infile)
    required = ["DTOBITO", "IDADE", "SEXO", "CAUSABAS"]
    missing = [x for x in required if x not in cols]
    if missing:
        sys.exit("Colunas essenciais ausentes: " + ", ".join(missing))

    cause_line_names = [x for x in ["CAUSABAS","LINHAA","LINHAB","LINHAC","LINHAD","LINHAII"]
                        if x in cols]
    if len(cause_line_names) < 2:
        sys.exit("Não há linhas suficientes de causas múltiplas no arquivo.")

    dto = col(cols, "DTOBITO")
    idade = col(cols, "IDADE")
    sexo = col(cols, "SEXO")
    racacor = col(cols, "RACACOR")
    esc = col(cols, "ESC")
    esc2010 = col(cols, "ESC2010")
    codmunres = col(cols, "CODMUNRES")
    tipobito = col(cols, "TIPOBITO")
    numerodo = col(cols, "NUMERODO")
    causabas = col(cols, "CAUSABAS")

    # concat_ws ignora NULLs. Os códigos são separados por espaços para criar
    # fronteiras seguras mesmo que diferentes campos da DO estejam adjacentes.
    cause_parts = ", ".join(clean_expr(col(cols, c)) for c in cause_line_names)
    cause_blob_expr = f"concat_ws(' ', {cause_parts})"

    uc_clean = (
        f"regexp_extract({clean_expr(causabas)}, '[A-Z][0-9]{{2}}[0-9A-Z]?', 0)"
    )

    # DTOBITO pode chegar como DDMMYYYY ou como DATE serializado.
    dto_text = f"trim(CAST({dto} AS VARCHAR))"
    death_ts = (
        f"try_strptime({dto_text}, "
        "['%d%m%Y','%Y-%m-%d','%d/%m/%Y','%Y-%m-%d %H:%M:%S'])"
    )

    # IDADE: microdatasus/DATASUS: 4xx = anos 0–99; 5xx = anos 100+.
    age_raw = (
        f"lpad(CAST(try_cast({idade} AS BIGINT) AS VARCHAR), 3, '0')"
    )

    if "CODMUNRES" in cols:
        uf_expr = f"try_cast(substr(trim(CAST({codmunres} AS VARCHAR)),1,2) AS INTEGER)"
    else:
        uf_expr = "NULL::INTEGER"

    fetal_filter = ""
    if "TIPOBITO" in cols:
        fetal_filter = f"AND (trim(CAST({tipobito} AS VARCHAR)) <> '1' OR {tipobito} IS NULL)"

    any_flags = ",\n        ".join(flag_from_blob(k, v) for k, v in ICD.items())
    uc_flags = ",\n        ".join(flag_from_uc(k, v) for k, v in ICD.items())

    sql = f"""
    COPY (
      WITH raw AS (
        SELECT
          {numerodo} AS numero_do,
          {death_ts} AS death_ts,
          {age_raw} AS age_raw,
          trim(CAST({sexo} AS VARCHAR)) AS sex_raw,
          trim(CAST({racacor} AS VARCHAR)) AS race_raw,
          trim(CAST({esc} AS VARCHAR)) AS education_raw,
          trim(CAST({esc2010} AS VARCHAR)) AS education2010_raw,
          trim(CAST({codmunres} AS VARCHAR)) AS municipality_residence,
          {uf_expr} AS uf_code,
          {uc_clean} AS underlying_cause,
          {cause_blob_expr} AS cause_blob
        FROM read_parquet('{str(infile).replace("'", "''")}')
        WHERE {death_ts} IS NOT NULL
          AND date_part('year', {death_ts}) BETWEEN {START_YEAR} AND {END_YEAR}
          {fetal_filter}
      ),
      derived AS (
        SELECT
          numero_do,
          CAST(death_ts AS DATE) AS death_date,
          CAST(date_part('year', death_ts) AS INTEGER) AS year,
          CASE
            WHEN age_raw = '999' THEN NULL
            -- SIM: 0=minutos, 1=horas, 2=dias, 3=meses; todos pertencem a 0 anos
            -- para as faixas etárias quinquenais usadas neste projeto.
            WHEN substr(age_raw,1,1) IN ('0','1','2','3') THEN 0
            WHEN substr(age_raw,1,1)='4' THEN try_cast(substr(age_raw,2,2) AS INTEGER)
            WHEN substr(age_raw,1,1)='5' THEN 100 + try_cast(substr(age_raw,2,2) AS INTEGER)
            ELSE NULL
          END AS age_years,
          CASE sex_raw WHEN '1' THEN 'Male' WHEN '2' THEN 'Female' ELSE NULL END AS sex,
          CASE race_raw
            WHEN '1' THEN 'White'
            WHEN '2' THEN 'Black'
            WHEN '3' THEN 'Asian'
            WHEN '4' THEN 'Brown'
            WHEN '5' THEN 'Indigenous'
            ELSE NULL
          END AS race_color,
          education_raw,
          education2010_raw,
          municipality_residence,
          uf_code,
          {UF_REGION} AS region,
          underlying_cause,
          cause_blob,
          list_unique(regexp_extract_all(cause_blob, '[A-Z][0-9]{{2}}[0-9A-Z]?')) AS n_causes
        FROM raw
      ),
      flags AS (
        SELECT
          *,
          CASE
            WHEN age_years IS NULL THEN 'Unknown'
            WHEN age_years < 60 THEN '<60'
            WHEN age_years BETWEEN 60 AND 69 THEN '60-69'
            WHEN age_years BETWEEN 70 AND 79 THEN '70-79'
            ELSE '80+'
          END AS age_group4,
          CASE
            WHEN age_years IS NULL THEN 'Unknown'
            WHEN age_years >= 100 THEN '100+'
            ELSE printf('%02d-%02d', floor(age_years/5)*5, floor(age_years/5)*5+4)
          END AS age_group5,
          CASE
            WHEN year BETWEEN 2000 AND 2004 THEN 'P1_2000_2004'
            WHEN year BETWEEN 2005 AND 2009 THEN 'P2_2005_2009'
            WHEN year BETWEEN 2010 AND 2014 THEN 'P3_2010_2014'
            WHEN year BETWEEN 2015 AND 2019 THEN 'P4_2015_2019'
            WHEN year BETWEEN 2020 AND 2024 THEN 'P5_2020_2024'
          END AS period5,
          {uc_flags},
          {any_flags}
        FROM derived
      )
      SELECT
        * EXCLUDE (cause_blob)
      FROM flags
    ) TO '{str(OUTFILE).replace("'", "''")}'
    (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000);
    """

    print("Construindo base-mãe...")
    print("Entrada :", infile.resolve())
    print("Saída   :", OUTFILE.resolve())
    con.execute(sql)

    n = con.execute("SELECT count(*) FROM read_parquet(?)", [str(OUTFILE)]).fetchone()[0]
    yr = con.execute(
        "SELECT min(year), max(year) FROM read_parquet(?)", [str(OUTFILE)]
    ).fetchone()
    print(f"Concluído: {n:,} registros; anos {yr[0]}–{yr[1]}.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Baixa e harmoniza as Projeções da População IBGE — Revisão 2024.

Fonte oficial:
https://ftp.ibge.gov.br/Projecao_da_Populacao/Projecao_da_Populacao_2024/
Arquivo:
projecoes_2024_tab2_grupo_quinquenal.xlsx

Saídas:
  data/processed/ibge_population_uf_sex_age_2000_2024.parquet
  data/processed/ibge_population_all_geographies_2000_2024.parquet
  outputs/qc/ibge_population_qc.csv

A planilha oficial tem uma aba por UF e as colunas:
Grupo de idade | Valor | Sexo | Ano
"""
from pathlib import Path
import argparse
import sys
import unicodedata
import urllib.request

try:
    import duckdb
except ImportError:
    duckdb = None
import pandas as pd

URL = (
    "https://ftp.ibge.gov.br/Projecao_da_Populacao/"
    "Projecao_da_Populacao_2024/projecoes_2024_tab2_grupo_quinquenal.xlsx"
)
RAW_DIR = Path("data/raw/ibge")
DEFAULT_XLSX = RAW_DIR / "projecoes_2024_tab2_grupo_quinquenal.xlsx"
OUT_UF = Path("data/processed/ibge_population_uf_sex_age_2000_2024.parquet")
OUT_ALL = Path("data/processed/ibge_population_all_geographies_2000_2024.parquet")
QC = Path("outputs/qc/ibge_population_qc.csv")
START_YEAR, END_YEAR = 2000, 2024

UF_REGION = {
    "RO":"North","AC":"North","AM":"North","RR":"North","PA":"North","AP":"North","TO":"North",
    "MA":"Northeast","PI":"Northeast","CE":"Northeast","RN":"Northeast","PB":"Northeast",
    "PE":"Northeast","AL":"Northeast","SE":"Northeast","BA":"Northeast",
    "MG":"Southeast","ES":"Southeast","RJ":"Southeast","SP":"Southeast",
    "PR":"South","SC":"South","RS":"South",
    "MS":"Central-West","MT":"Central-West","GO":"Central-West","DF":"Central-West",
}
EXPECTED_AGES = [f"{a:02d}-{a+4:02d}" for a in range(0, 90, 5)] + ["90+"]


def asciify(x):
    return "".join(c for c in unicodedata.normalize("NFKD", str(x)) if not unicodedata.combining(c)).strip()


def norm_sex(x):
    s = asciify(x).lower()
    if s in {"homens", "homem", "masculino", "male", "males"}:
        return "Male"
    if s in {"mulheres", "mulher", "feminino", "female", "females"}:
        return "Female"
    return None


def norm_age(x):
    s = asciify(x).upper().replace(" ", "").replace("–", "-").replace("—", "-")
    if s in {"TOTAL", "TODASASIDADES", "TODAS"}:
        return None
    if s in {"90+", "90EMAIS", "90E+", "90-MAIS", "90OU+", "90OU MAIS"}:
        return "90+"
    # aceita 00-04, 0-4, 05-09 etc.
    import re
    m = re.fullmatch(r"0*(\d{1,2})-0*(\d{1,2})", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi == lo + 4 and 0 <= lo <= 85 and lo % 5 == 0:
            return f"{lo:02d}-{hi:02d}"
    return None


def download(dest: Path, force=False):
    if dest.exists() and not force:
        print(f"IBGE já baixado: {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 research-script/1.0"})
    print("Baixando denominadores oficiais do IBGE (Revisão 2024)...")
    try:
        with urllib.request.urlopen(req, timeout=120) as src, open(dest, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
    except Exception as e:
        if dest.exists():
            dest.unlink(missing_ok=True)
        sys.exit(
            "Falha no download automático do IBGE.\n"
            f"Baixe manualmente:\n{URL}\n"
            f"e salve em: {dest}\nErro: {e}"
        )
    if dest.stat().st_size < 100_000:
        sys.exit("Arquivo IBGE baixado parece incompleto.")
    print(f"Salvo: {dest} ({dest.stat().st_size/1e6:.1f} MB)")


def parse_workbook(path: Path):
    xls = pd.ExcelFile(path, engine="openpyxl")
    missing_sheets = [uf for uf in UF_REGION if uf not in xls.sheet_names]
    if missing_sheets:
        sys.exit("Abas de UF ausentes na planilha IBGE: " + ", ".join(missing_sheets))

    pieces = []
    for uf in UF_REGION:
        d = pd.read_excel(path, sheet_name=uf, engine="openpyxl")
        d.columns = [asciify(c) for c in d.columns]
        lookup = {asciify(c).lower(): c for c in d.columns}
        required = ["grupo de idade", "valor", "sexo", "ano"]
        absent = [c for c in required if c not in lookup]
        if absent:
            sys.exit(f"Aba {uf}: colunas ausentes: {absent}; colunas={list(d.columns)}")
        d = d.rename(columns={
            lookup["grupo de idade"]: "age_raw",
            lookup["valor"]: "population",
            lookup["sexo"]: "sex_raw",
            lookup["ano"]: "year",
        })
        d["age_group5"] = d["age_raw"].map(norm_age)
        d["sex"] = d["sex_raw"].map(norm_sex)
        d["year"] = pd.to_numeric(d["year"], errors="coerce")
        d["population"] = pd.to_numeric(d["population"], errors="coerce")
        d = d[
            d["year"].between(START_YEAR, END_YEAR)
            & d["age_group5"].notna()
            & d["sex"].notna()
        ].copy()
        d["year"] = d["year"].astype(int)
        d["uf"] = uf
        d["region"] = UF_REGION[uf]
        d = d[["year","uf","region","sex","age_group5","population"]]
        pieces.append(d)

    out = pd.concat(pieces, ignore_index=True)
    out = out.groupby(["year","uf","region","sex","age_group5"], as_index=False)["population"].sum()
    if (out["population"] <= 0).any():
        sys.exit("Foram encontradas populações <= 0 no IBGE.")

    # Validação estrutural: 19 grupos de idade em cada UF × sexo × ano.
    chk = out.groupby(["year","uf","sex"])["age_group5"].nunique().reset_index(name="n_age_groups")
    bad = chk[chk["n_age_groups"] != len(EXPECTED_AGES)]
    if not bad.empty:
        print(bad.head(20).to_string(index=False))
        sys.exit("IBGE: combinações sem os 19 grupos etários esperados.")

    observed = set(out["age_group5"].unique())
    if observed != set(EXPECTED_AGES):
        sys.exit(f"Grupos etários inesperados. Observados={sorted(observed)}")
    return out


def make_all_geographies(ufdf):
    # UF, homens/mulheres
    uf = ufdf.copy()
    uf["geography_level"] = "UF"
    uf["geography"] = uf["uf"]

    # Região, homens/mulheres
    reg = ufdf.groupby(["year","region","sex","age_group5"], as_index=False)["population"].sum()
    reg["geography_level"] = "Region"
    reg["geography"] = reg["region"]
    reg["uf"] = None

    # Brasil, homens/mulheres
    bra = ufdf.groupby(["year","sex","age_group5"], as_index=False)["population"].sum()
    bra["geography_level"] = "Brazil"
    bra["geography"] = "Brazil"
    bra["region"] = None
    bra["uf"] = None

    allg = pd.concat([
        uf[["year","geography_level","geography","uf","region","sex","age_group5","population"]],
        reg[["year","geography_level","geography","uf","region","sex","age_group5","population"]],
        bra[["year","geography_level","geography","uf","region","sex","age_group5","population"]],
    ], ignore_index=True)

    # Ambos os sexos derivados como soma dos dois sexos oficiais.
    both = allg.groupby(
        ["year","geography_level","geography","age_group5"], as_index=False, dropna=False
    )["population"].sum()
    both["sex"] = "Both"
    both["uf"] = both["geography"].where(both["geography_level"].eq("UF"), None)
    both["region"] = both["geography"].where(both["geography_level"].eq("Region"), None)
    allg = pd.concat([allg, both[allg.columns]], ignore_index=True)
    return allg


def save_parquet(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.register("df", df)
    con.execute(f"COPY df TO '{path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_XLSX, help="XLSX IBGE local")
    ap.add_argument("--force-download", action="store_true")
    ap.add_argument("--no-download", action="store_true")
    args = ap.parse_args()

    if not args.input.exists() and not args.no_download:
        download(args.input, args.force_download)
    elif args.force_download and not args.no_download:
        download(args.input, True)
    if not args.input.exists():
        sys.exit(f"Arquivo IBGE ausente: {args.input}")

    ufdf = parse_workbook(args.input)
    allg = make_all_geographies(ufdf)
    save_parquet(ufdf, OUT_UF)
    save_parquet(allg, OUT_ALL)

    QC.parent.mkdir(parents=True, exist_ok=True)
    qc = allg[allg["sex"].eq("Both")].groupby(
        ["year","geography_level"], as_index=False
    )["population"].sum()
    # Para Region/UF, soma todas as geografias; Brazil é o total nacional uma vez.
    qc.to_csv(QC, index=False)

    nat = allg[(allg.geography_level=="Brazil") & (allg.sex=="Both")].groupby("year")["population"].sum()
    print("Concluído.")
    print(" ", OUT_UF.resolve())
    print(" ", OUT_ALL.resolve())
    print(f" População Brasil 2000: {nat.loc[2000]:,.0f}")
    print(f" População Brasil 2024: {nat.loc[2024]:,.0f}")

if __name__ == "__main__":
    main()
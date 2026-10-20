#!/usr/bin/env python3
"""
Inspeciona o schema real do Parquet do SIM antes de qualquer transformação.
Não carrega o arquivo inteiro na RAM.
"""
from pathlib import Path
import duckdb
import sys

TARGET = "declaracoes_de_obito_cid10.parquet"

def locate():
    hits = list(Path("data/raw").rglob(TARGET))
    if not hits:
        sys.exit(
            f"Não encontrei {TARGET} em data/raw.\n"
            "Execute primeiro: python 00_download_sim.py"
        )
    return hits[0]

def main():
    path = locate()
    con = duckdb.connect()

    print(f"\nARQUIVO\n{path.resolve()}\n")
    schema = con.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]
    ).fetchall()

    print("SCHEMA REAL")
    for col, typ, null, key, default, extra in schema:
        print(f"{col:22s} {typ}")

    cols = {r[0].upper() for r in schema}
    expected_core = {
        "DTOBITO", "IDADE", "SEXO", "CAUSABAS",
        "LINHAA", "LINHAB", "LINHAC", "LINHAD", "LINHAII"
    }
    missing = sorted(expected_core - cols)
    print("\nCHECAGEM")
    if missing:
        print("ATENÇÃO — colunas esperadas ausentes:", ", ".join(missing))
    else:
        print("Todas as colunas essenciais para os dois artigos estão presentes.")

    optional = ["NUMERODO", "TIPOBITO", "RACACOR", "ESC", "ESC2010", "CODMUNRES", "ATESTADO"]
    print("\nCOLUNAS OPCIONAIS")
    for c in optional:
        print(f"{c:12s}: {'OK' if c in cols else 'ausente'}")

    # Amostra das linhas causais para conferir o padrão de codificação.
    cause_cols = [c for c in ["CAUSABAS","LINHAA","LINHAB","LINHAC","LINHAD","LINHAII"]
                  if c in cols]
    select = ", ".join(f'"{c}"' for c in cause_cols)
    print("\nAMOSTRA DAS CAUSAS (20 REGISTROS)")
    rows = con.execute(
        f"SELECT {select} FROM read_parquet(?) "
        f"WHERE CAUSABAS IS NOT NULL LIMIT 20", [str(path)]
    ).fetchall()
    print("\t".join(cause_cols))
    for row in rows:
        print("\t".join("" if v is None else str(v) for v in row))

    # Distribuição dos primeiros caracteres de IDADE, útil para confirmar o layout.
    if "IDADE" in cols:
        print("\nCÓDIGO DE UNIDADE DA IDADE")
        q = """
        SELECT substr(lpad(CAST(try_cast(IDADE AS BIGINT) AS VARCHAR), 3, '0'),1,1) AS unidade,
               count(*) AS n
        FROM read_parquet(?)
        WHERE try_cast(IDADE AS BIGINT) IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
        for unidade, n in con.execute(q, [str(path)]).fetchall():
            print(unidade, n)

if __name__ == "__main__":
    main()
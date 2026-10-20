#!/usr/bin/env python3
"""Prepara arquivos ASCII tab-delimited para NCI Joinpoint 6.1.x."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

RATES = Path("outputs/article2/article2_standardized_rates.csv")
NTI = Path("outputs/article2/article2_nti.csv")
OUT = Path("outputs/article2/joinpoint")
CAUSES_PRIMARY = ["Cerebrovascular","Dementia","Alzheimer","Parkinson"]


def main():
    if not RATES.exists() or not NTI.exists():
        sys.exit("Execute primeiro: python 06_article2_rates.py")
    OUT.mkdir(parents=True, exist_ok=True)
    r = pd.read_csv(RATES)
    r = r[r["cause"].isin(CAUSES_PRIMARY) & (r["asmr_per_100k"]>0)].copy()

    bra = r[r["geography_level"].eq("Brazil")][["cause","sex","year","asmr_per_100k","asmr_se"]].copy()
    bra.columns = ["Cause","Sex","Year","Rate","StandardError"]
    bra = bra.sort_values(["Cause","Sex","Year"])
    bra.to_csv(OUT/"joinpoint_brazil_rates.txt", sep="\t", index=False, float_format="%.10g")

    reg = r[r["geography_level"].eq("Region")][["geography","cause","sex","year","asmr_per_100k","asmr_se"]].copy()
    reg.columns = ["Region","Cause","Sex","Year","Rate","StandardError"]
    reg = reg.sort_values(["Region","Cause","Sex","Year"])
    reg.to_csv(OUT/"joinpoint_regions_rates.txt", sep="\t", index=False, float_format="%.10g")

    n = pd.read_csv(NTI)
    n = n[(n["geography_level"]=="Brazil") & n["nti"].notna() & (n["nti"]>0)].copy()
    nt = n[["sex","year","nti","nti_se"]].copy()
    nt.columns = ["Sex","Year","NTI","StandardError"]
    nt = nt.sort_values(["Sex","Year"])
    nt.to_csv(OUT/"joinpoint_brazil_nti.txt", sep="\t", index=False, float_format="%.10g")

    instructions = OUT/"JOINPOINT_INSTRUCTIONS.md"
    instructions.write_text("""# NCI Joinpoint — configuração pré-especificada

Arquivos gerados:

- `joinpoint_brazil_rates.txt`
- `joinpoint_regions_rates.txt`
- `joinpoint_brazil_nti.txt`

## Taxas padronizadas

No Joinpoint Desktop 6.1.x:

1. Input Data File: arquivo `.txt` tab-delimited, com cabeçalhos.
2. Run type: dependent variable **provided in data file**.
3. Dependent variable: `Rate`.
4. Standard Error: `StandardError`.
5. Independent variable: `Year`.
6. By variables, Brasil: `Cause`, `Sex`.
7. By variables, regiões: `Region`, `Cause`, `Sex`.
8. Log transformation: **Yes**.
9. Interval: annual.
10. Minimum joinpoints: 0.
11. Maximum joinpoints: 4, conforme protocolo.
12. Model selection/significance: Monte Carlo permutation method.
13. Reportar APC de cada segmento e AAPC 2000–2024 com IC95%.

A análise primária utiliza `Sex=Both`. Male/Female são estratificações pré-especificadas.

## NTI

Use `NTI` como variável dependente fornecida, `StandardError` como erro-padrão, `Year` como variável independente e `Sex` como by-variable, com transformação logarítmica.

O NTI é a razão:

`ASMR dementia / ASMR cerebrovascular`.

Não chamar o NTI de taxa padronizada no texto; ele é um índice/razão entre duas taxas padronizadas.

## Importante

Não descrever resultados calculados fora do software como resultados do NCI Joinpoint. Após executar o Joinpoint oficial, exportar APC, AAPC, joinpoints e ICs para `outputs/article2/joinpoint/results/`.
""", encoding="utf-8")
    print("Arquivos Joinpoint gerados em:", OUT.resolve())

if __name__ == "__main__":
    main()
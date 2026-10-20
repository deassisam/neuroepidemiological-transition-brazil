#!/usr/bin/env bash
set -euo pipefail
python 05_get_ibge_population.py
python 06_article2_rates.py
python 07_prepare_joinpoint.py
python 08_article2_decomposition.py
python 09_article2_tables_figures.py
python tests/test_article2_methods.py
echo "Artigo 2: pipeline pós-QC concluído. Ver outputs/article2/"
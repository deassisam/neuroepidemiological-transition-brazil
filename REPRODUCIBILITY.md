# Reproducibility and independent verification

This document provides an audit-oriented map from data inputs to the principal results reported in the manuscript **The Neuroepidemiological Transition in Brazil: Nationwide Trends in Cerebrovascular, Dementia, Alzheimer’s, and Parkinson’s Mortality, 2000–2024**.

## What can be reproduced

The repository contains the scripts used for:

1. SIM mortality-data extraction and harmonization;
2. IBGE population-denominator retrieval and harmonization;
3. cause-of-death aggregation using fixed ICD-10 definitions;
4. direct age standardization to the WHO World Standard Population 2000–2025;
5. calculation of the study-specific Neuroepidemiological Transition Index (NTI);
6. exhaustive inverse-variance-weighted piecewise log-linear model selection;
7. APC and AAPC estimation;
8. residual diagnostics and Newey–West sensitivity analyses;
9. Shapley demographic decomposition;
10. regional SIM-quality analyses;
11. BIC/AICc model-selection sensitivity and breakpoint inclusion weights;
12. regional uncertainty estimates; and
13. publication tables and figures.

## Two reproducibility routes

### Route A — Full reconstruction from public source data

This route starts from the public mortality and population sources.

Requirements:

- Python environment from `requirements.txt`;
- R with the packages used by the repository scripts;
- Kaggle credentials for the DataHub Brasil technical mirror used by `00_download_sim.py`;
- internet access for the IBGE population workbook.

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash reproduce_main_results.sh --from-source
```

`00_download_sim.py` identifies and downloads the SIM CID-10 Parquet file from the public DataHub Brasil/Kaggle dataset. SIM/DATASUS remains the scientific data source; the Kaggle/DataHub layer is used only for reproducible file access. `05_get_ibge_population.py` downloads the official IBGE Population Projections, 2024 Revision.

### Route B — Reproduction from frozen analysis-ready aggregate inputs

For faster independent verification, the revision package is designed to include frozen, non-identifiable aggregate inputs derived from the public source data:

- `data/analysis_ready/article2_underlying_counts_2000_2024.parquet`
- `data/analysis_ready/ibge_population_all_geographies_2000_2024.parquet`

These contain aggregated cause-specific death counts and official population denominators, not individual death-certificate microdata. The repository script `reproduce_main_results.sh --from-analysis-ready` copies these frozen inputs into the expected pipeline locations and reproduces the downstream ASMR, NTI, decomposition, trend, sensitivity, table, and figure outputs.

## Principal generated outputs

The most important audit files are:

- `outputs/article2/article2_standardized_rates.csv`
- `outputs/article2/article2_nti.csv`
- `outputs/article2/article2_decomposition.csv`
- `outputs/article2/piecewise_bic_sensitivity/sensitivity_selected_models.csv`
- `outputs/article2/piecewise_bic_sensitivity/sensitivity_APC_by_segment.csv`
- `outputs/article2/piecewise_bic_sensitivity/sensitivity_AAPC.csv`
- `outputs/article2/final/table2_piecewise_trends.csv`
- `outputs/article2/reviewer_revision/model_selection_BIC_vs_AICc.csv`
- `outputs/article2/reviewer_revision/breakpoint_inclusion_weights.csv`
- `outputs/article2/reviewer_revision/Supplementary_Table_S6_regional_SIM_quality.csv`
- `outputs/article2/reviewer_revision/Supplementary_Table_S8_regional_uncertainty.csv`

## Independent numerical verification

After the pipeline has run, execute:

```bash
python verify_reported_results.py
```

The script compares the generated results with a frozen set of manuscript-level numerical checks stored under `expected_results/`. It exits with a non-zero status if a principal endpoint, breakpoint configuration, AAPC, or Shapley decomposition value fails the specified tolerance.

Key expected checks include:

- total non-fetal death records: **30,593,956**;
- cerebrovascular ASMR: **63.6921708** in 2000 and **36.8806941** in 2024;
- dementia ASMR: **1.7541702** in 2000 and **11.3852911** in 2024;
- Alzheimer’s disease ASMR: **1.2375944** in 2000 and **9.7437174** in 2024;
- Parkinson’s disease ASMR: **0.8146585** in 2000 and **2.1145467** in 2024;
- NTI: **0.0275413** in 2000 and **0.3087080** in 2024 (computed from the frozen component ASMRs);
- primary breakpoints: cerebrovascular **2008/2020**, dementia **2006/2010**, Alzheimer **2006/2011**, Parkinson **2006/2017**, NTI **2005/2010/2019**;
- AAPCs: cerebrovascular **−2.17%**, dementia **+8.04%**, Alzheimer **+9.18%**, Parkinson **+4.05%**, NTI **+10.59%** per year;
- Shapley decomposition reconstruction residual approximately zero.

## Model-selection uncertainty

The reported APC/AAPC confidence intervals are conditional on the selected breakpoint configuration. Selection uncertainty is separately characterized by rescoring the full admissible candidate space using both BIC and AICc and by calculating normalized model weights and breakpoint inclusion weights. These outputs are stored in `outputs/reviewer_revision/`.

## Data privacy and redistribution

Individual SIM death-certificate microdata are not redistributed in this repository. They are public, anonymized secondary data available through Brazilian public-data infrastructure and the DataHub Brasil technical mirror. The frozen analysis-ready files provided for reviewer verification are aggregated tables that contain no individual-level records or direct identifiers.

## Software environment

- Python 3.9+ (see `requirements.txt`)
- R 4.6.1 for the final temporal-trend analyses used in the revision

The scripts are deterministic given the same input files. No stochastic model fitting or random seed is involved in the primary analyses.
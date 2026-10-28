# The Neuroepidemiological Transition in Brazil — reproducibility repository

This repository contains the analytical code and supporting resources for the manuscript:

**The Neuroepidemiological Transition in Brazil: Nationwide Trends in Cerebrovascular, Dementia, Alzheimer’s, and Parkinson’s Mortality, 2000–2024**

## Scope

The repository provides the scripts and definitions required to reproduce the mortality-data preprocessing, direct age standardization, Neuroepidemiological Transition Index (NTI), segmented log-linear temporal models, Shapley demographic decomposition, regional data-quality analyses, reviewer-requested BIC/AICc model-selection sensitivity analyses, and regional uncertainty table.

Raw mortality microdata are not redistributed. They are obtained from the Brazilian Mortality Information System (SIM/DATASUS) through the DataHub Brasil/Kaggle technical access layer described in the pipeline. Population denominators are obtained from the official IBGE Population Projections, 2024 Revision.

## Main outcome definitions

See `resources/icd10_definitions.md`.

## WHO standard population

See `resources/who_world_standard_2000_2025_weights.csv` and the executable implementation in `06_article2_rates.py`. Published WHO percentages are normalized to sum exactly to 1.0; the terminal IBGE category 90+ combines the WHO 90-94, 95-99, and 100+ weights.

## Reproduction overview

Create the environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Build and QC the mortality dataset:

```bash
python 00_download_sim.py
python 01_inspect_schema.py
python 02_build_sim_master.py
python 03_quality_report.py
python 04_prepare_analysis_inputs.py
```

Prepare population denominators and calculate rates/NTI:

```bash
python 05_get_ibge_population.py
python 06_article2_rates.py
```

Run the demographic decomposition and temporal analyses:

```bash
python 08_article2_decomposition.py
Rscript 11e_sensitivity_piecewise_bic.R
python 12_article2_final_outputs.py
python 14_article2_final_figures_exact_v4.py
```

The final-figure script regenerates the exact-data national Figures 2 and 3 from the frozen analytical outputs and validates the reported endpoints and trend estimates before saving publication files.

Reviewer-requested analyses:

```bash
python 15_regional_sim_quality.py
Rscript 16_aicc_deltaBIC_breakpoint_stability.R
python 17_regional_uncertainty.py
```

The `17_regional_uncertainty.py` script extracts the Poisson-approximation 95% confidence intervals for regional age-standardized mortality rates and log-delta-method 95% confidence intervals for regional NTI values from the outputs of `06_article2_rates.py`.

## Key reviewer-revision outputs included

`outputs/reviewer_revision/` includes the regional SIM-quality table, BIC/AICc model-selection sensitivity outputs, breakpoint inclusion weights, and the regional uncertainty outputs used for Supplementary Table S8. The S8 files were generated directly from the frozen regional ASMR and NTI outputs using `17_regional_uncertainty.py`.

## Reproducibility notes

- The primary temporal model is inverse-variance-weighted piecewise log-linear regression.
- Candidate models contain 0-4 integer-year breakpoints with a minimum four-year segment length.
- The primary selection criterion is BIC; AICc is a reviewer-requested sensitivity analysis.
- APC/AAPC confidence intervals are conditional on the selected breakpoint configuration.
- Breakpoint inclusion weights summarize model-selection uncertainty and should not be interpreted as confidence intervals for exact event dates.
- The Shapley mortality-rate component represents changes in **age-specific recorded mortality rates** after accounting for population size and age structure; it is not an estimate of disease incidence.
- The NTI is a study-specific descriptive ratio and is not an externally validated epidemiological indicator.

## Data sources

- Brazilian Mortality Information System (SIM/DATASUS), accessed through DataHub Brasil/Kaggle for reproducible file handling.
- IBGE Population Projections, 2024 Revision.
- WHO World Standard Population 2000-2025.

## Repository status

This repository is the public reproducibility resource accompanying the manuscript revision. The revision snapshot can additionally be archived in an external preservation service (for example, Zenodo) to obtain a version-specific DOI if required by the journal.


## Independent verification

For reviewer-oriented replication and numerical auditing, see:

- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) — full-from-source and analysis-ready reproduction routes, output map, and numerical checks.
- [MODEL_SPECIFICATIONS.md](MODEL_SPECIFICATIONS.md) — formal model definitions, weights, uncertainty calculations, APC/AAPC, and Shapley decomposition.
- [verify_reported_results.py](verify_reported_results.py) — automated manuscript-level numerical verification.
- [expected_results/](expected_results/) — frozen principal-result checks used by the verification script.
- [prepare_reviewer1_bundle.sh](prepare_reviewer1_bundle.sh) — helper for packaging the frozen non-identifiable analysis-ready inputs and exact model outputs from the original analysis workspace.

The individual-level SIM microdata are not redistributed. Frozen analysis-ready files, when provided, contain only aggregated cause-specific death counts and official population denominators.

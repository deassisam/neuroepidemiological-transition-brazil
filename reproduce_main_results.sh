#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---from-source}"

case "$MODE" in
  --from-source)
    echo "[1/10] Downloading/locating public SIM source data"
    python 00_download_sim.py
    echo "[2/10] Inspecting source schema"
    python 01_inspect_schema.py
    echo "[3/10] Building harmonized mortality master"
    python 02_build_sim_master.py
    echo "[4/10] Running mortality-data QC"
    python 03_quality_report.py
    echo "[5/10] Preparing article-specific aggregate inputs"
    python 04_prepare_analysis_inputs.py
    ;;
  --from-analysis-ready)
    mkdir -p data/processed
    cp data/analysis_ready/article2_underlying_counts_2000_2024.parquet data/processed/
    cp data/analysis_ready/ibge_population_all_geographies_2000_2024.parquet data/processed/
    ;;
  *)
    echo "Usage: $0 [--from-source|--from-analysis-ready]" >&2
    exit 2
    ;;
esac

if [[ "$MODE" == "--from-source" ]]; then
  echo "[6/10] Downloading/harmonizing IBGE denominators"
  python 05_get_ibge_population.py
fi

echo "[7/10] Calculating ASMRs and NTI"
python 06_article2_rates.py

echo "[8/10] Running Shapley decomposition"
python 08_article2_decomposition.py

echo "[9/10] Running temporal-model sensitivity grid and final outputs"
Rscript 11e_sensitivity_piecewise_bic.R
python 12_article2_final_outputs.py
python 14_article2_final_figures_exact_v4.py

echo "[10/10] Running reviewer-requested analyses and numerical verification"
python 15_regional_sim_quality.py
Rscript 16_aicc_deltaBIC_breakpoint_stability.R
python 17_regional_uncertainty.py
python verify_reported_results.py

echo "Reproduction completed successfully."
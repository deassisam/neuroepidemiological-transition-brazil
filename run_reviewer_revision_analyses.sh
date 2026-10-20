#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] Regional SIM quality by macro-region and five-year period"
python3 15_regional_sim_quality.py

echo "[2/2] AICc sensitivity and breakpoint model-selection uncertainty"
Rscript 16_aicc_deltaBIC_breakpoint_stability.R

echo
printf '%s\n' "Done. Send back the files in outputs/article2/reviewer_revision/ (or paste model_selection_summary.txt) so the reviewer response and revised manuscript can be finalized."
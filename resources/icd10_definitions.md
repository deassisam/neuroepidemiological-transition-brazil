# ICD-10 outcome definitions used in the manuscript

Primary analyses use the **underlying cause of death** recorded in SIM.

- Cerebrovascular disease: I60-I69
- Dementia: F00-F03 and G30
- Alzheimer’s disease: F00 and G30 (nested within the broader dementia definition)
- Parkinson’s disease: G20
- Vascular dementia sensitivity exclusion: F01
- Ill-defined underlying causes used for data-quality assessment: R00-R99

The executable regular expressions are defined in `02_build_sim_master.py` and applied consistently across 2000-2024.
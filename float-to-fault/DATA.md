# Data used and where to get it

Third-party data are not redistributed here. Obtain them from the original sources and link them with `scripts/link_data.sh`.

| Data | Used for | Source | Placed at (see link script) |
|---|---|---|---|
| RCPLIB, "original" resource-constrained project instances (includes the PSPLIB sets) | Simulated delay experiments | Vanhoucke, M., Coelho, J. and Batselier, J. (2016), *Journal of Modern Project Management*, 3(2), 6-21; Vanhoucke, M. (2024), *A Quest for Projects with Scarce Resources*, Springer, https://doi.org/10.1007/978-3-031-71507-5; Kolisch and Sprecher (1997), *EJOR*, 96(1), 205-216 | `ALL/ALL.tar` and `RCPLIB (Parameters and BKS).xlsx` in one folder |
| DSLIB 3.4 (real construction project baselines and tracking sheets) | Real-schedule replay (Section 3.7) | Ghent University, Operations Research and Scheduling Group, https://www.projectmanagement.ugent.be/research/data/realdata ; Batselier and Vanhoucke (2015), *IJPM*, 33(3), 697-710 | folder `DSLIB 3.4` containing `Excel/` |
| NYC DOB NOW job application filings (approval lead times) | Empirical lead-time distribution for the authority event | NYC Open Data, resource w9ak-ipjd; retrieved 2026-10-25; the derived bins are already stored in `experiments/nyc_leads.json` | shipped |

The instance split is deterministic: SHA-256 of the instance name, even first byte = development, odd = held-out.
Check the licence terms of each data set before redistributing any derived file other than the summary results shipped here.

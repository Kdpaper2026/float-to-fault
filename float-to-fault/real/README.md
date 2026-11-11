Real-schedule replay and checks.
- dslib_replay.py: calendar-aware replay of DSLIB 3.4 baseline and tracking sheets; writes dslib_replay_out.json (run from this folder).
- dslib_analyze.py: pooled shares with bootstrap intervals, reads dslib_replay_out.json; output kept in dslib_analysis.txt.
- dslib_resource_check.py: resource-feasibility check of the baseline scheduler on parseable real plans; writes dslib_resource_check.json.
- huynh_reproduce.py: exact reproduction of Tables 14 and 15 of Huynh et al. (2023) with the Shapley rule used here (output huynh_reproduce.txt).
- shapley_crosscheck.py: cross-check of the engine's Shapley values against an independent permutation calculation.
- coder_agreement.py and SECOND_CODER_SHEET_COMPLETED.xlsx: second-coder agreement on the cause catalogue (output coder_agreement.txt).
DSLIB itself is not redistributed; see ../DATA.md.

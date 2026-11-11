# From Float to Fault: code, results and manuscript sources

Companion repository for "From Float to Fault: Causal Attribution of Construction Delay to Owners, Authorities and Contractors" (PregleAI Research & Smart Solutions).

The study tests whether Shapley attribution of delay days points to the fixes that recover the most time at a decision epoch, how that depends on the quality of the delay record, and what real baseline and tracking data say about waiting versus slow work.

## Layout

| Path | Content |
|---|---|
| `experiments/PROTOCOL.md` | Frozen protocol and its amendments (A1 to A3 and A6 before or without effect on the held-out runs; A4, A5 and A7 exploratory) |
| `experiments/exp_engine.py`, `exp_run.py`, `exp_analyze.py` | Frozen engine, run script and analysis (hashes below) |
| `experiments/exp_ext.py`, `exp_ext_analyze.py` | Extraction-error sweep and value test (exploratory) |
| `experiments/exp_lit.py`, `exp_lit_analyze.py` | Litigation extension (exploratory, amendment A7) |
| `experiments/exp_summary.py` | Held-out sensitivity table |
| `experiments/results/` | Raw result files of all reported runs |
| `experiments/analysis/` | Analysis outputs and run logs behind the manuscript tables |
| `real/` | DSLIB replay and resource check, reproduction of Huynh et al. (2023) tables, Shapley cross-check, second-coder sheet and agreement |
| `paper/` | Final manuscript (`.docx`), its build sources (`v2/` is the current version, `v1/` the earlier one), figure scripts and figure images (`figs_v2/`, `figs_v1/`) |
| `scripts/` | `link_data.sh`, `verify_hashes.sh`, `run_all.sh` |
| `DATA.md` | Third-party data sources |

## Quick start

```bash
pip install -r requirements.txt            # Python 3.13 was used; numpy 2.5, numba 0.68, openpyxl 3.1, scipy 1.18, matplotlib 3.11
bash scripts/verify_hashes.sh              # frozen code unchanged
python3 -I experiments/exp_analyze.py experiments/results/held_primary.json   # reproduces the main held-out tables
python3 -I experiments/exp_summary.py      # sensitivity table
python3 -I experiments/exp_lit_analyze.py  # litigation extension
python3 -I experiments/exp_ext_analyze.py experiments/results/ext_sweep.json
```

These analyses need no external data. Checked on this copy: the outputs of the four analysis scripts equal the files in `experiments/analysis/` (the only difference is the file path printed in one header line), and `real/dslib_analyze.py`, `real/huynh_reproduce.py` and `real/coder_agreement.py` reproduce their stored outputs.

## Re-running the experiments

1. Download RCPLIB and DSLIB (see `DATA.md`) and run `bash scripts/link_data.sh <rcplib_dir> "<DSLIB 3.4 dir>"`. The frozen engine reads data from fixed paths under `/tmp/claude-0/real`; the link script creates them, which keeps the frozen files, and so their hashes, unchanged. To use other paths, edit lines 7 and 8 of `exp_engine.py`, and note that its hash then changes.
2. `bash scripts/run_all.sh 4` (argument = worker processes). This is long. Runs are deterministic: eight held-out instances re-run on this copy gave rows identical to the shipped result file.
3. `cd real && python3 dslib_replay.py && python3 dslib_analyze.py` for the real-schedule replay.

## Frozen code hashes (md5)

```
2e9ea847a6c4343be5f3fb19c4bb2389  exp_run.py
ba64313971edd0f25d9abdaa05e6a976  exp_engine.py
b7590fbbb4d43751b2df647780d2acd0  exp_analyze.py
```
`exp_lit.py` has a recorded SHA-256 in `experiments/LIT_HASH.txt`.

## Build the manuscript

```bash
npm install -g docx@9.7.1
cd paper && python3 -I make_eqs.py          # equation images (needs pdflatex and pdftoppm)
python3 -I make_figs_v2.py                  # figures for v2 (make_figs_v1.py for the earlier version)
cd v2 && NODE_PATH=$(npm root -g) node build_v2.js   # writes From_Float_to_Fault_Manuscript_v2.docx
python3 fix_bookmarks.py From_Float_to_Fault_Manuscript_v2.docx   # unique bookmark ids for the clickable citations
NODE_PATH=$(npm root -g) node build_app.js && python3 fix_bookmarks.py From_Float_to_Fault_Supplementary_Appendices_v2.docx   # separate appendix file
```
Note: the figure script draws from values typed in from the result tables, not from the result files; if a table changes, update the script.

## Status and limits

- Held-out primary results are confirmatory under the frozen protocol. The extraction sweep, value test, litigation extension and DSLIB replay were run after those results were seen and are exploratory.
- The controlled experiment is simulated. Event sizes, mix, costs and extraction error rates are assumptions, and the analyst's model has the generating model's structure.
- `exp_summary.py` and `exp_lit_analyze.py` were changed only to read from `experiments/results/`; `real/shapley_crosscheck.py` only to find the engine by a relative path.
- Legal-case annotation work and earlier drafts are not part of this repository.
- No licence file is included. The authors should choose one before the repository is made public. The manuscript's data and code availability statement says the repository will be deposited before submission; add its address there once it exists.

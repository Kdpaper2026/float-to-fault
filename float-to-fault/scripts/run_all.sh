#!/usr/bin/env bash
# Full re-run of every experiment, then the analyses. W is the number of worker processes.
# Runtime is long (hours on a few cores). Results go to experiments/rerun/, the shipped results stay untouched.
set -euo pipefail
W=${1:-2}
cd "$(dirname "$0")/../experiments"; mkdir -p rerun
python3 exp_run.py test
# development split (100 instances per size) and held-out primary (200 per size)
python3 exp_run.py run dev  100 rerun/dev_primary.json primary $W
python3 exp_run.py run held 200 rerun/held_primary.json primary $W
# held-out sensitivity configurations (100 per size)
for c in size_lo size_hi mix_owner mix_contr partial; do python3 exp_run.py run held 100 rerun/held_$c.json $c $W; done
# exploratory: extraction sweep (80 per size) and litigation extension (100 per size primary, 50 per size sensitivities)
python3 exp_ext.py 80 rerun/ext_sweep.json $W
python3 exp_lit.py run held 100 rerun/lit_primary.json primary $W
for c in scale_lo scale_hi lead_lo lead_hi cost3; do python3 exp_lit.py run held 50 rerun/lit_$c.json $c $W; done
# analyses
python3 -I exp_analyze.py rerun/held_primary.json > rerun/held_analysis_primary.txt
python3 -I exp_ext_analyze.py rerun/ext_sweep.json > rerun/ext_analysis.txt
echo "done; compare rerun/*.txt with analysis/*.txt (exp_lit_analyze.py and exp_summary.py read files from their own folder: copy rerun/lit_*.json or held_*.json next to them first)"

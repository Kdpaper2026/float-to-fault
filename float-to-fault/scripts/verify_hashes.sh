#!/usr/bin/env bash
# Checks that the frozen protocol and code are unchanged (md5 values recorded before the held-out run).
set -euo pipefail
cd "$(dirname "$0")/../experiments"
md5sum -c <<'H'
2e9ea847a6c4343be5f3fb19c4bb2389  exp_run.py
ba64313971edd0f25d9abdaa05e6a976  exp_engine.py
b7590fbbb4d43751b2df647780d2acd0  exp_analyze.py
H
echo "protocol file (recorded md5 be21fb16ec98dd60a488a44cb64b515b is for the version frozen before the held-out run; later amendments were appended and are listed in the file):"
md5sum PROTOCOL.md
echo "recorded sha-256 of exp_lit.py (amendment A7):"; sha256sum exp_lit.py; cat LIT_HASH.txt

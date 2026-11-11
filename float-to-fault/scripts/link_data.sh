#!/usr/bin/env bash
# The frozen engine (experiments/exp_engine.py) and the DSLIB scripts read third-party data from fixed paths
# under /tmp/claude-0/real. They are kept unchanged so that their recorded hashes stay valid.
# Usage: scripts/link_data.sh /path/to/rcplib_dir "/path/to/DSLIB 3.4"
#   rcplib_dir must contain ALL/ALL.tar and "RCPLIB (Parameters and BKS).xlsx"
set -euo pipefail
[ $# -eq 2 ] || { echo "usage: $0 RCPLIB_DIR DSLIB_3.4_DIR"; exit 1; }
RC=$(readlink -f "$1"); DS=$(readlink -f "$2")
[ -f "$RC/ALL/ALL.tar" ] || { echo "missing $RC/ALL/ALL.tar"; exit 1; }
[ -f "$RC/RCPLIB (Parameters and BKS).xlsx" ] || { echo "missing RCPLIB parameter workbook"; exit 1; }
[ -d "$DS/Excel" ] || { echo "missing $DS/Excel"; exit 1; }
mkdir -p /tmp/claude-0/real/dslib
ln -sfn "$RC" /tmp/claude-0/real/rcplib
ln -sfn "$DS" "/tmp/claude-0/real/dslib/DSLIB 3.4"
echo "linked: /tmp/claude-0/real/rcplib -> $RC ; /tmp/claude-0/real/dslib/DSLIB 3.4 -> $DS"

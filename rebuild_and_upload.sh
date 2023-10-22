#!/bin/bash
set -ex
cd "$(dirname "$0")"

test -d .venv/ || { echo "No .venv/ found!"; exit 1; }
. .venv/bin/activate
test -d blob/ || { echo "Must first checkout branch 'blob' as blob/ directory!"; exit 1; }
sleep 5

mkdir -p intermediate_certs
./fetch_all.py
cp intermediate_certs/intermediate_certs.pem blob/

pushd blob/
    git add intermediate_certs.pem
    # Note: --reset-author refreshes the timestamp, which is important to check up-to-dateness!
    git commit --amend --no-edit --reset-author
    git push --force  # upstream must already be configured
popd

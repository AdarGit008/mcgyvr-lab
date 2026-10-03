#!/usr/bin/env bash
# rigprep.sh HOST BUNDLE — put the rig agent under test (product rig-head-slots
# abccb902) on HOST beside the checkout that is there, never in it:
#   ~/mcgyvr-pool-tmp/product-slots   a local clone of ~/mcgyvr-pool-tmp/product,
#                                     plus the two commits from BUNDLE, detached
#                                     at abccb902, with its own .venv
#   ~/mcgyvr-pool-tmp/e2e-slots/home  rig-sharing.json copied from the owner's
#                                     ~/mcgyvr-pool-tmp/home (credentials come
#                                     from the join)
# ~/mcgyvr-pool-tmp/product and ~/mcgyvr-pool-tmp/e2e are not touched.
# rigclean.sh removes all three things this creates.
set -euo pipefail
host=$1
bundle=$2
want=abccb9022935d8ac656f210388a40ff8d73c00dc
scp -q "$bundle" "$host:mcgyvr-pool-tmp/product-slots.bundle"
ssh -o BatchMode=yes "$host" "set -eu
cd ~/mcgyvr-pool-tmp
[ -e product-slots ] && { echo 'product-slots already there'; exit 1; }
git clone -q --no-checkout product product-slots
git -C product-slots fetch -q ../product-slots.bundle rig-head-slots:refs/heads/rig-head-slots
git -C product-slots -c advice.detachedHead=false checkout -q $want
echo \"checkout: \$(git -C product-slots rev-parse HEAD)\"
cd product-slots
UV_CACHE_DIR=\$HOME/mcgyvr-pool-tmp/uv-cache UV_PYTHON_INSTALL_DIR=\$HOME/mcgyvr-pool-tmp/uv-python \
  uv sync --frozen --python \$HOME/mcgyvr-pool-tmp/uv-python/cpython-3.12-linux-x86_64-gnu/bin/python3 -q
.venv/bin/python -c 'import importlib.metadata as m; print(\"mcgyvr\", m.version(\"mcgyvr\"))'
umask 077
mkdir -p ~/mcgyvr-pool-tmp/e2e-slots/home ~/mcgyvr-pool-tmp/e2e-slots/data
cp ~/mcgyvr-pool-tmp/home/rig-sharing.json ~/mcgyvr-pool-tmp/e2e-slots/home/
echo prepared
"

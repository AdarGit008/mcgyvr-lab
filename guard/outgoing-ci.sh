#!/usr/bin/env bash
# The outgoing gate for lab CI. Run from anywhere inside the lab checkout.
#
#   guard/outgoing-ci.sh [LAB_BASE]
#
# Compares the product commit recorded at LAB_BASE (the lab commit this change
# is measured against; empty or all zeros = none) with the one recorded at
# HEAD. If the pointer did not move, nothing leaves for the product: exit 0.
# If it moved, scan every product commit between the product's origin/main and
# the new pointer: exit 0 clean, 1 findings, 2 error.
#
# Fails closed: a shallow lab checkout, a base that is not present, a product
# history that cannot be made complete, or a pointer with no common history
# with origin/main is exit 2, never a pass.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${PYTHON:-python3}
fail() { echo "outgoing: $*" >&2; exit 2; }

lab=$(git rev-parse --show-toplevel) || fail "not inside a git checkout"
cd "$lab"
base=${1:-}

[ "$(git rev-parse --is-shallow-repository)" = false ] \
  || fail "the lab checkout is shallow; check it out with its full history (fetch-depth: 0)"

pointer() {  # the product commit recorded in lab commit $1 ("" if none)
  git ls-tree "$1" -- product | awk '$2 == "commit" { print $3 }'
}

new=$(pointer HEAD)
[ -n "$new" ] || fail "HEAD records no product commit"

old=""
if [ -n "$base" ] && ! [[ "$base" =~ ^0+$ ]]; then
  git cat-file -e "$base^{commit}" 2>/dev/null \
    || fail "base $base is not in this checkout"
  old=$(pointer "$base")
fi

if [ "$old" = "$new" ]; then
  echo "outgoing: the product pointer did not move ($new); nothing leaves for the product"
  exit 0
fi
echo "outgoing: the product pointer moved: ${old:-none} -> $new"

git submodule update --init -- product
if [ "$(git -C product rev-parse --is-shallow-repository)" = true ]; then
  git -C product fetch --quiet --unshallow origin
fi
git -C product fetch --quiet origin main
[ "$(git -C product rev-parse --is-shallow-repository)" = false ] \
  || fail "product/ is still shallow"
git -C product cat-file -e "$new^{commit}" 2>/dev/null \
  || fail "product/ does not have $new"
mb=$(git -C product merge-base origin/main "$new") \
  || fail "$new has no common history with the product's origin/main"

echo "outgoing: scanning product commits $mb..$new"
exec "$python" "$here/check_outgoing.py" --repo product --diff "$mb..$new"

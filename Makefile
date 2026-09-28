# The lab's entry points. Run them from the lab's root.
#   make check           the lab's own gate: lint, format, types, tests (guard self-tests included)
#   make product-check   the product's own `make check`, run inside product/ (see below for what it does not set up)
#   make guard           the outgoing gate: what product/'s branch adds on top of origin/main
#   make guard-baseline  informational: private words left in the product, staying paths and whole tree
#   make product-sync    move product/ to the latest origin/main (refuses over work on no branch)
.PHONY: setup check product-check guard guard-baseline product-sync product-present

LAB := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
PRODUCT ?= product
# The range `make guard` checks: what product/'s HEAD adds on top of this.
GUARD_BASE ?= origin/main
GUARD = uv run --no-sync --project $(LAB) python $(LAB)/guard/check_outgoing.py --repo $(PRODUCT)
# The paths that stay in the product once the lab-bound folders have moved.
STAYING = --only src --only tests --only data --only examples --only skills --only .github --only /

setup:  ## install the lab's environment, frozen against uv.lock
	uv sync --frozen --project $(LAB)

# The lab gate checks guard/ and tests/guard/, and lints pyproject.toml. The
# tests and tools copied from the product (tests/ outside tests/guard/,
# tools/) are not yet part of it; making them part of it is the next step.
# --confcutdir keeps pytest from loading the copied tests/conftest.py around
# the guard's self-tests.
LAB_GATE_PATHS = guard tests/guard

check: setup  ## the lab's own gate
	uv run --no-sync ruff check $(LAB_GATE_PATHS) pyproject.toml
	uv run --no-sync ruff format --check $(LAB_GATE_PATHS)
	uv run --no-sync mypy
	uv run --no-sync pytest --confcutdir=$(LAB)/tests/guard tests/guard

# product/ is a submodule. Uninitialised, it is an empty directory inside the
# lab, and a git command run there would act on the lab itself.
product-present:
	@test -e $(PRODUCT)/.git || { echo "$(PRODUCT)/ is not checked out: run 'git submodule update --init product'" >&2; exit 2; }

# Runs `make check` inside product/ (uv sync --frozen, ruff check, ruff format
# --check, mypy, docgen --check, pytest) with this shell's PATH and tools. The
# product's CI does more first, and this target does NOT: it does not install
# Node 24, run `npm ci`, or put product/node_modules/.bin on PATH (the pinned
# JS toolchain some product tests use), and it does not pin uv 0.11.28 or
# Python 3.12. Lab CI's product-check job sets all of that up.
product-check: product-present  ## the product's `make check`, inside product/
	$(MAKE) -C $(PRODUCT) check

# The gate before a pull request. The script exits 0 clean, 1 findings, 2
# could not scan or refused (uncommitted work, a detached HEAD with work on a
# branch, a wrong range); make turns any non-zero into its own failure (exit
# 2), so `make guard` passes or fails and the printed summary says why. The
# branch name is scanned too when product/ is on a branch.
guard: setup product-present  ## the outgoing gate over product/
	@branch=$$(git -C $(PRODUCT) symbolic-ref --quiet --short HEAD || true); \
	$(GUARD) --diff $(GUARD_BASE)..HEAD $${branch:+--branch "$$branch"}

# Informational: exit 0 when both scans ran, 2 when one could not; never 1.
guard-baseline: setup product-present  ## counts of private words left in product/
	@echo "== paths that stay in the product"
	@$(GUARD) --tree --quiet --count-only $(STAYING)
	@echo "== whole tree"
	@$(GUARD) --tree --quiet --count-only

product-sync: product-present  ## product/ to the latest origin/main
	@if [ -n "$$(git -C $(PRODUCT) status --porcelain --untracked-files=no)" ]; then \
		echo "product-sync: $(PRODUCT)/ has uncommitted changes; commit or stash them first" >&2; \
		exit 1; \
	fi
	@stray=$$(git -C $(PRODUCT) rev-list HEAD --not --branches --remotes --tags); \
	if [ -n "$$stray" ]; then \
		echo "product-sync: $(PRODUCT)/ HEAD has commits on no branch or remote ref:" >&2; \
		git -C $(PRODUCT) log --oneline --no-walk $$stray >&2; \
		echo "put them on a branch first (git -C $(PRODUCT) switch -c <name>)" >&2; \
		exit 1; \
	fi
	git -C $(PRODUCT) fetch origin main
	git -C $(PRODUCT) checkout --detach origin/main
	@echo "$(PRODUCT)/ is at $$(git -C $(PRODUCT) log --oneline -1)"
	@echo "Branches in $(PRODUCT)/ are untouched. The lab records the new commit only when you commit product/."

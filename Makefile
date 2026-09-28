# The lab's entry points. Run them from the lab's root.
#   make check           the lab's own gate: lint, format, types, tests (guard self-tests included)
#   make product-check   the product's full gate, run inside product/ exactly as its CI runs it
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

check: setup  ## the lab's own gate
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .
	uv run --no-sync mypy
	uv run --no-sync pytest tests

# product/ is a submodule. Uninitialised, it is an empty directory inside the
# lab, and a git command run there would act on the lab itself.
product-present:
	@test -e $(PRODUCT)/.git || { echo "$(PRODUCT)/ is not checked out: run 'git submodule update --init product'" >&2; exit 2; }

product-check: product-present  ## the product's full gate, inside product/
	$(MAKE) -C $(PRODUCT) check

# The gate before a pull request: its exit code is the verdict (0 clean,
# 1 findings, 2 could not scan or uncommitted work). The branch name is
# scanned too when product/ is on a branch.
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

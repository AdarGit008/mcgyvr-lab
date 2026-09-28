# The lab's entry points. Run them from the lab's root.
#   make check          the lab's own gate: lint, format, types, tests (guard self-tests included)
#   make product-check  the product's full gate, run inside product/ exactly as its CI runs it
#   make guard          the outgoing guard over product/: lines its branch adds, then the whole tree
#   make product-sync   move product/ to the latest origin/main (refuses over uncommitted work)
.PHONY: setup check product-check guard product-sync product-present

# The range `make guard` checks: what product/'s HEAD adds on top of this.
GUARD_BASE ?= origin/main
GUARD = uv run --no-sync python guard/check_outgoing.py --repo product

setup:  ## install the lab's environment, frozen against uv.lock
	uv sync --frozen

check: setup  ## the lab's own gate
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .
	uv run --no-sync mypy
	uv run --no-sync pytest tests

# product/ is a submodule. Uninitialised, it is an empty directory inside the
# lab, and a git command run there would act on the lab itself.
product-present:
	@test -e product/.git || { echo "product/ is not checked out: run 'git submodule update --init product'" >&2; exit 2; }

product-check: product-present  ## the product's full gate, inside product/
	$(MAKE) -C product check

# Both scans always run; the exit status is the worse of the two (2 over 1
# over 0). The first is what a pull request must keep clean; the second stays
# non-zero until the product's clean-up is complete.
guard: setup product-present  ## the outgoing guard over product/
	@rc=0; \
	echo "== lines added by $(GUARD_BASE)..HEAD in product/"; \
	$(GUARD) --diff $(GUARD_BASE)..HEAD || rc=$$?; \
	echo "== whole tree of product/ at HEAD"; \
	$(GUARD) --tree --quiet || { r=$$?; [ $$r -gt $$rc ] && rc=$$r; }; \
	exit $$rc

product-sync: product-present  ## product/ to the latest origin/main
	@if [ -n "$$(git -C product status --porcelain --untracked-files=no)" ]; then \
		echo "product-sync: product/ has uncommitted changes; commit or stash them first" >&2; \
		exit 1; \
	fi
	git -C product fetch origin main
	git -C product checkout --detach origin/main
	@echo "product/ is at $$(git -C product log --oneline -1)"
	@echo "Branches in product/ are untouched. The lab records the new commit only when you commit product/."

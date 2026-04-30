.PHONY: lint security fmt

SHELL := /bin/bash

# ── Lint ──────────────────────────────────────────────────────────────────────
# Runs ruff (linting + formatting check), codespell, basedpyright,
# and the emoji detector used across secops repos.
#
# Usage:
#   make lint           # check only (CI-safe, no writes)
#   make fmt            # auto-fix formatting and import order
# ─────────────────────────────────────────────────────────────────────────────

lint: _install-lint-deps
	@echo ">>> ruff: linting"
	ruff check .
	@echo ">>> ruff: formatting check"
	ruff format --check .
	@echo ">>> codespell"
	codespell --skip="./.git,./.tox,./.venv,venv,*.json,*.ndjson,*.log,*.yaml,*.yml" .
	# TODO: basedpyright is commented out pending discussion.
	# It requires project dependencies to be installed to resolve imports,
	# which makes it hard to run generically across repos with different deps.
	# @echo ">>> basedpyright"
	# basedpyright .
	@echo ">>> emoji detector"
	@out=$$(for ext in py sh go c cpp; do \
		LC_ALL=C find . -name "*.$$ext" -not -path './.*' -exec grep -nHP "[\x80-\xFF]" {} \;; \
	done); \
	if [ -n "$$out" ]; then \
		printf "Emojis detected in code:\n$$out\n"; \
		exit 1; \
	fi
	@echo ">>> lint: all checks passed"

fmt: _install-lint-deps
	@echo ">>> ruff: auto-fix and format"
	ruff check --fix .
	ruff format .
	@echo ">>> codespell: auto-fix"
	codespell -w --skip="./.git,./.tox,./.venv,venv,*.json,*.ndjson,*.log,*.yaml,*.yml" .

# ── Security ──────────────────────────────────────────────────────────────────
# Runs ruff bandit rules (S prefix), opengrep, trivy, and trufflehog.
#
# Usage:
#   make security
# ─────────────────────────────────────────────────────────────────────────────

security: _install-security-deps
	@echo ">>> ruff: bandit rules (S)"
	ruff check --select S --config 'lint.per-file-ignores={"tests/**"=["S101","S104","S105"]}' .
	@echo ">>> opengrep"
	# TODO: opengrep has no official docker image yet, using pinned install
	# script commit hash instead.
	opengrep scan --config auto .
	@echo ">>> trivy: filesystem scan"
	# trivy v0.70.0
	docker run --rm \
		-v "$(PWD):/scan" \
		aquasec/trivy@sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e \
		fs --exit-code 1 --severity HIGH,CRITICAL /scan
	@echo ">>> trufflehog: secret scan"
	# trufflehog v3.95.2
	docker run --rm \
		-v "$(PWD):/pwd" \
		ghcr.io/trufflesecurity/trufflehog@sha256:49d1c4fbbc580aac487ac7cb0517bb085826bd352d7578d62bb4c0c6b7205075 \
		filesystem /pwd --only-verified --fail
	@echo ">>> security: all checks passed"

# ── Internal install targets ──────────────────────────────────────────────────

_install-lint-deps:
	@echo ">>> installing lint dependencies"
	pip install --quiet ruff==0.15.12 codespell basedpyright --break-system-packages

_install-security-deps:
	@echo ">>> installing security dependencies"
	pip install --quiet ruff==0.15.12 --break-system-packages
	# TODO: remove this block once opengrep has an official docker image
	@echo ">>> installing opengrep (pinned commit)"
	# opengrep v1.20.0 commit hash verified
	@if ! command -v opengrep &>/dev/null; then \
		HASH="19a2dd0a3c964370d58ebc67e8ad7ce42079b665"; \
		curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/$${HASH}/install.sh | bash; \
	fi

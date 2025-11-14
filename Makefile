SHELL := /bin/bash
PY ?= python
MIE := $(PY) cli/mie.py
LOGDIR := logs
TS := $(shell date +'%Y%m%d_%H%M')

.PHONY: logs
logs:
	@mkdir -p $(LOGDIR)

.PHONY: test-fast
test-fast: logs ## Pytest fail fast, short tb
	pytest -q --maxfail=1 --tb=short -rE | tee $(LOGDIR)/pytest_fast_$(TS).log

.PHONY: streamlit
streamlit: ## Run Streamlit app (use ARGS to pass through options after --)
	streamlit run app.py $(if $(ARGS),$(ARGS),)

.PHONY: pipeline
pipeline: logs ## Tests + features + analytics, logs captured
	{ \
	pytest -q --maxfail=1 --tb=short; \
	ls data/features || true; \
	$(MIE) build-features --mode full; \
	$(MIE) update-features --lookback $(if $(LOOKBACK),$(LOOKBACK),90); \
	$(MIE) ensure-markov-available --ticker $(if $(TICKER),$(TICKER),SPY) --window $(if $(WINDOW),$(WINDOW),2Y); \
	$(MIE) update-all-analytics; \
	ls data/analytics/markov/$${TICKER:-SPY}/matrices/*/*/$${WINDOW:-2Y}*; \
	} > $(LOGDIR)/pipeline_$(TS).log 2>&1; \
	echo "Log: $(LOGDIR)/pipeline_$(TS).log"

# --- New convenience targets ---
.PHONY: rebuild-all update-all integrity test
rebuild-all:
	$(PY) cli/mie.py rebuild-everything

update-all:
	$(PY) cli/mie.py update-everything

integrity:
	$(PY) scripts/check_data_integrity.py

test:
	pytest -q

# Cron convenience targets
.PHONY: cron-install cron-remove cron-smoke cron-run-once
cron-install:
	bash scripts/install_cron.sh

cron-remove:
	- crontab -l | grep -v 'MIE_NIGHTLY_UPDATE' | crontab - || echo "No matching entry"; true

cron-smoke:
	bash scripts/cron_smoke.sh

cron-run-once:
	bash scripts/nightly_update.sh

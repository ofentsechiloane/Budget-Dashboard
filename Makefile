.RECIPEPREFIX := >
PY    := .venv/bin/python
INPUT ?= data/sample
PORT  ?= 8000

.DEFAULT_GOAL := help
.PHONY: help setup sample run run-raw reset test check all serve clean

help:
> @grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup:      ## Create venv and install dependencies
> python3 -m venv .venv
> $(PY) -m pip install -r requirements.txt

sample:     ## Generate synthetic bank exports
> $(PY) src/generate_sample.py

run:        ## Run pipeline on INPUT (default data/sample)
> $(PY) src/run_pipeline.py --input $(INPUT)

run-raw:    ## Run pipeline on your real statements
> $(PY) src/run_pipeline.py --input data/raw

reset:      ## Rebuild warehouse from scratch
> $(PY) src/run_pipeline.py --input $(INPUT) --reset

test:       ## Run the tests
> $(PY) -m pytest -q

check:      ## Syntax-check all Python files
> $(PY) -m compileall -q src tests

all: setup sample reset test   ## Full clean build

serve:      ## Serve dashboard on http://localhost:8000/budget-dashboard.html
> cd dashboard && python3 -m http.server $(PORT)

clean:      ## Remove warehouse, logs and caches
> rm -rf warehouse.db logs .pytest_cache
> find . -name __pycache__ -type d -prune -exec rm -rf {} +

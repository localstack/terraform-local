VENV_DIR ?= .venv
VENV_RUN = . $(VENV_DIR)/bin/activate
PIP_CMD ?= pip
TEST_PATH ?= tests
TF_CMD ?= terraform 

usage:        ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

install:      ## Install dependencies in local virtualenv folder
	(test `which virtualenv` || $(PIP_CMD) install --user virtualenv) && \
		(test -e $(VENV_DIR) || virtualenv $(VENV_OPTS) $(VENV_DIR)) && \
		($(VENV_RUN); $(PIP_CMD) install -e .[test])

lint:         ## Run code linter
	$(VENV_RUN); flake8 --ignore=E501,W503 bin/tflocal tests

test:         ## Run unit/integration tests
	$(VENV_RUN); TF_CMD=$(TF_CMD) pytest $(PYTEST_ARGS) -sv $(TEST_PATH)

publish:      ## Publish the library to the central PyPi repository
	# build and upload archive
	($(VENV_RUN) && pip install build twine && python3 -m build && twine upload dist/*)

clean:        ## Clean up
	rm -rf $(VENV_DIR)
	rm -rf dist
	rm -rf *.egg-info

.PHONY: clean publish install usage lint test

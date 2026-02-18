# Makefile

define HELP_MESSAGE
flexitac

# Installing

1. Create a new Conda environment: `conda create --name flexitac python=3.11`
2. Activate the environment: `conda activate flexitac`
3. Install the package: `make install-dev`

# Running Tests

1. Run autoformatting: `make format`
2. Run static checks: `make static-checks`
3. Run unit tests: `make test`

endef
export HELP_MESSAGE

all:
	@echo "$$HELP_MESSAGE"
.PHONY: all

# ------------------------ #
#        PyPI Build        #
# ------------------------ #

build-for-pypi:
	@pip install --verbose build wheel twine
	@python -m build --sdist --wheel --outdir dist/ .
	@twine upload dist/*
.PHONY: build-for-pypi

push-to-pypi: build-for-pypi
	@twine upload dist/*
.PHONY: push-to-pypi

# ------------------------ #
#       Static Checks      #
# ------------------------ #

excluded := ./.venv ./references
exclude_args := $(foreach d,$(excluded),-path "$(d)" -prune -o)

py-files := $(shell find . $(exclude_args) -name '*.py' -print)

format:
	@ruff format $(py-files)
	@ruff check --fix $(py-files)
.PHONY: format

static-checks:
	@ruff format --check $(py-files)
	@ruff check $(py-files)
	@mypy $(py-files)
.PHONY: static-checks

# ------------------------ #
#        Unit tests        #
# ------------------------ #

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest
.PHONY: test

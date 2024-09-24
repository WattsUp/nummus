#!/bin/sh
# Run every linter
ruff check .
djlint . --check --lint
codespell .
pyright # No dot cause it gets included files from pyproject.toml

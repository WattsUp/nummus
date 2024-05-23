#!/bin/sh
# Run every linter
ruff check .
djlint .
codespell .
pyright # No dot cause it gets included files from pyproject.toml

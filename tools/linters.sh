#!/bin/sh
# Run every linter
ruff check .
djlint .
codespell .

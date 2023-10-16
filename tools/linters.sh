#!/bin/sh
# Run every linter
ruff .
djlint .
codespell .

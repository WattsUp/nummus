#!/bin/sh
# Run every formatter
isort .
black .
djlint . --reformat

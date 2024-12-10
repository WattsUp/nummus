#!/bin/sh
# Run every formatter
isort .
black .
djlint . --reformat
find nummus/static/src -name "*.js" -not -path "nummus/static/src/3rd-party/*" -exec clang-format -i {} \;
clang-format -i nummus/static/tailwind.config.js
taplo fmt .

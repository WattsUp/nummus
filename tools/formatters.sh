#!/bin/sh
# Run every formatter
isort .
black .
prettier nummus/templates nummus/static/src/css -w
find nummus/static/src -name "*.js" -not -path "nummus/static/src/3rd-party/*" -exec clang-format -i {} \;
taplo fmt .

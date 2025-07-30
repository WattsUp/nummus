#!/bin/sh

PY_VERSION=$(python -m setuptools_scm)

WHL=dist/nummus_financial-$PY_VERSION-py3-none-any.whl
if [ ! -f $WHL ]; then
  echo "Building python wheel"
  python -m build -w
fi

# Build docker image
docker build --build-arg WHL=$WHL --tag nummus-financial .

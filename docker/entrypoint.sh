#!/bin/sh

set -e

# Clear prometheus dir
prom_dir=${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}
rm -rf $prom_dir
mkdir $prom_dir

key_file=${NUMMUS_KEY_PATH:-/data/.key.secret}
portfolio=${NUMMUS_PORTFOLIO:-/data/portfolio.db}

if [ ! -f $portfolio ]; then
  if [ ! -f $key_file ]; then
    python3 -c "import secrets;print(secrets.token_hex())" >$key_file
  fi

  web_key=${NUMMUS_WEB_KEY:-nummus-admin}

  nummus --portfolio $portfolio --pass-file $key_file create

  # TODO (WattsUp): Add args to change-password
  # nummus --portfolio $portfolio --pass-file $key_file change-password
fi

# Start server
export PROMETHEUS_MULTIPROC_DIR=$prom_dir
export NUMMUS_PORTFOLIO=$portfolio
export NUMMUS_KEY_PATH=$key_file
gunicorn -c gunicorn.conf.py "nummus.web:create_app()"

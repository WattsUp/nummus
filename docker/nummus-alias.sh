#!/bin/sh

set -e

key_file=${NUMMUS_KEY_PATH:-/data/.key.secret}
portfolio=${NUMMUS_PORTFOLIO:-/data/portfolio.db}

/home/python/.local/bin/nummus --portfolio $portfolio --pass-file $key_file $@

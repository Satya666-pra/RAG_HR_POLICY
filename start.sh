#!/bin/sh
# Container entrypoint for Render (and `docker compose up`).
#
# Render "Secret Files" are mounted at /etc/secrets/<name>. Streamlit reads its
# [auth] login config from .streamlit/secrets.toml, so copy it into place if it
# was provided. Without it, app.py either runs in open mode (local) or refuses
# to start (REQUIRE_AUTH=true, as set in render.yaml).
set -e

if [ -f /etc/secrets/secrets.toml ]; then
  mkdir -p .streamlit
  cp /etc/secrets/secrets.toml .streamlit/secrets.toml
fi

exec streamlit run app.py \
  --server.port="${PORT:-10000}" \
  --server.address=0.0.0.0 \
  --server.headless=true

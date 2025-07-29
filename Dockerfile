# syntax=docker/dockerfile:1

FROM python:3.12-slim-bullseye
LABEL maintainer="Bradley Davis <me@bradleydavis.tech>"

WORKDIR /nummus
ARG UID=1000
ARG GID=1000

RUN apt-get update \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${GID}" python \
  && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" python \
  && chown python:python -R /nummus

USER python

ARG PY_VERSION=
ARG WHL=

COPY --chown=python:python docker/* .

RUN --mount=type=bind,target=. pip3 install --no-cache-dir "${WHL}[deploy,encrypt]"

RUN mkdir /tmp/prometheus

ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus \
  PYTHONUNBUFFERED="true" \
  PYTHONPATH="." \
  PATH="${PATH}:/home/python/.local/bin" \
  USER="python"

EXPOSE 8000

CMD [ "gunicorn", "-c", "gunicorn.conf.py", "nummus.web:create_app()" ]

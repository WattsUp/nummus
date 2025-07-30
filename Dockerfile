# syntax=docker/dockerfile:1

# TODO (WattsUp): workflow action to build this
FROM python:3.12-slim-bullseye
LABEL maintainer="Bradley Davis <me@bradleydavis.tech>"

WORKDIR /app
ARG UID=1000
ARG GID=1000

RUN apt-get update \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${GID}" python \
  && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" python \
  && chown python:python -R /app \
  && mkdir /data \
  && chown python:python -R /data
VOLUME /data

USER python

ARG WHL=

COPY --chown=python:python docker/* .
RUN chmod +x ./*.sh

RUN --mount=type=bind,target=. pip3 install --no-cache-dir "${WHL}[deploy,encrypt]"

ENV PYTHONUNBUFFERED="true" \
  PYTHONPATH="." \
  PATH="${PATH}:/home/python/.local/bin" \
  USER="python"

EXPOSE 8000
EXPOSE 8001

ENTRYPOINT [ "/app/entrypoint.sh" ]

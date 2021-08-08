#!/bin/sh
set -eu

if command -v podman; then
  CONTAINER=podman
else
  CONTAINER=docker
fi

$CONTAINER run --rm --name localstack -p 4566:4566 \
  -e SERVICES=ec2,iam,sts \
  -v ./patch-entrypoint.sh:/usr/local/bin/patch-entrypoint.sh:ro,z \
  --entrypoint patch-entrypoint.sh "$@" localstack/localstack:0.12.16
